#!/usr/bin/env python3
"""
課堂回覆分析 Agent v3（Config 驅動版）
=======================================
★ 本檔案永遠不需要修改 ★
所有週次相關的設定（問題結構、選項、API 設定）都從 config.json 讀取。
每週只需要用 skill 生成新的 config.json。

使用方式：
    python agent.py [config.json 路徑]   # 預設讀 ./config.json

依賴套件：
    pip install openai pandas json-repair
"""

import json
import json_repair
import sys
import time
from pathlib import Path
from collections import Counter

import pandas as pd
from openai import OpenAI

# ================================================================
# Config 載入
# ================================================================

CONFIG_PATH = sys.argv[1] if len(sys.argv) > 1 else "config.json"


def load_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"❌ 找不到 {path}，請先用 skill 生成 config.json")
        sys.exit(1)
    cfg = json.loads(p.read_text(encoding="utf-8"))
    print(f"📂 已載入設定：{path}（{cfg['meta'].get('week_label', '')}）")
    return cfg


CFG = load_config(CONFIG_PATH)

# ================================================================
# 從 Config 建立執行時常數
# ================================================================

_api  = CFG["api"]
_qs   = CFG["questions"]

API_KEY       = _api["key"]
API_BASE      = _api["base"]
RUBRIC_MODEL  = _api["models"]["rubric"]
ANALYSIS_MODEL  = _api["models"]["analysis"]
AGGREGATE_MODEL = _api["models"]["aggregate"]
BATCH_SIZE    = _api.get("batch_size", 3)
SLEEP_BETWEEN = _api.get("sleep_between", 1.0)
FORCE_JSON    = _api.get("force_json_mode", False)

CSV_PATH    = CFG["meta"]["csv_path"]
RUBRIC_PATH = "rubric.json"
WF1_OUTPUT  = "wf1_results.json"
WF2_OUTPUT  = "wf2_report.json"

# 問題查找表：id → 設定
Q_BY_ID  = {q["id"]: q for q in _qs}
# 依欄位索引排序的問題清單（排除時間戳記欄）
Q_LIST   = sorted(_qs, key=lambda q: q["col"])
# 需要評分的問題 id 清單
SCORED_QS = [q["id"] for q in Q_LIST if q.get("score")]


def mc_keys(q_id: str) -> list[str]:
    """取某道 MC 題的所有短標籤"""
    q = Q_BY_ID.get(q_id, {})
    opts = q.get("mc_options") or {}
    return list(opts.keys())


def mc_label_string(q_id: str) -> str:
    """建構 WF1 schema 用的選項字串，例如 '「A」優先 | 「B」優先 | ...' """
    keys = mc_keys(q_id)
    return " | ".join(keys) if keys else "（未知選項）"


def normalize_mc_answer(q_id: str, raw_value: str) -> str:
    """
    將 MC 欄位的原始完整文字對應回 config 中定義的短標籤。
    優先做完整字串比對，其次做短標籤包含比對，最後 fallback 回原始值。
    這確保傳給 LLM 的 MC 答案永遠是短標籤，不含中英混雜的說明文字。
    """
    q = Q_BY_ID.get(q_id, {})
    opts = q.get("mc_options") or {}
    raw_stripped = raw_value.strip()
    # 1. 完整比對
    for short_label, full_text in opts.items():
        if raw_stripped == full_text.strip():
            return short_label
    # 2. 短標籤包含比對（處理截斷或細微差異）
    for short_label in opts:
        if short_label in raw_stripped:
            return short_label
    # 3. fallback
    return raw_value


def get_tag_display(rubric: dict, q_id: str, tag: str) -> str:
    """
    從 rubric 的 tag_display 查出 tag 的中文顯示名稱。
    若查無對應則回傳原始 tag 名稱（確保向後相容）。

    使用範例（可視化端）：
        rubric = load_json("rubric.json")
        label = get_tag_display(rubric, "Q2", "missing_normative_premise")
        # → "缺乏規範前提"
    """
    display_map = rubric.get("tag_display", {})
    q_map = display_map.get(q_id, {})
    return q_map.get(tag, tag)


def build_display_lookup(rubric: dict) -> dict:
    """
    將 tag_display 展平為 {tag_name: 中文名稱} 的全域查找表（跨題唯一時適用）。
    若不同題有同名 tag 但顯示名稱不同，請改用 get_tag_display() 指定 q_id。

    使用範例：
        lookup = build_display_lookup(rubric)
        df["error_tags_zh"] = df["error_tags"].map(lambda tags: [lookup.get(t, t) for t in tags])
    """
    lookup = {}
    for q_map in rubric.get("tag_display", {}).values():
        lookup.update(q_map)
    return lookup


# ================================================================
# LLM 工具函數
# ================================================================

client = OpenAI(api_key=API_KEY, base_url=API_BASE)
_JSON_MODE_SUPPORTED: bool | None = None  # 快取：API 是否支援 response_format


def call_llm(
    messages: list[dict],
    model: str,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    force_json: bool = False,
) -> str:
    """
    呼叫 LLM。
    force_json=True 時嘗試 response_format=json_object；
    若 API 不支援則靜默降級（只用提示詞約束 + json_repair）。
    """
    global _JSON_MODE_SUPPORTED

    kwargs = dict(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    if force_json and _JSON_MODE_SUPPORTED is not False:
        try:
            resp = client.chat.completions.create(
                **kwargs,
                response_format={"type": "json_object"},
            )
            if _JSON_MODE_SUPPORTED is None:
                print("  ✅ response_format=json_object 支援確認")
                _JSON_MODE_SUPPORTED = True
            return resp.choices[0].message.content
        except Exception as e:
            if "response_format" in str(e).lower() or "unsupported" in str(e).lower():
                print("  ⚠️  API 不支援 response_format，改用 json_repair fallback")
                _JSON_MODE_SUPPORTED = False
            else:
                raise

    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content


def _fix_control_chars(text: str) -> str:
    result, in_string, escape_next = [], False, False
    _ESC = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}
    for ch in text:
        if escape_next:
            result.append(ch); escape_next = False
        elif ch == "\\" and in_string:
            result.append(ch); escape_next = True
        elif ch == '"':
            result.append(ch); in_string = not in_string
        elif in_string and ch in _ESC:
            result.append(_ESC[ch])
        elif in_string and ord(ch) < 0x20:
            pass
        else:
            result.append(ch)
    return "".join(result)


def safe_json(text: str):
    """三段式 JSON 解析：直接 → 修 control chars → json_repair"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()

    for attempt, fn in enumerate([
        lambda t: json.loads(t),
        lambda t: json.loads(_fix_control_chars(t)),
        lambda t: json_repair.repair_json(t, return_objects=True),
    ]):
        try:
            result = fn(text)
            if result not in ("", None, {}, []):
                return result
        except Exception:
            if attempt == 2:
                tail = text.rstrip()
                is_truncated = not (tail.endswith("}") or tail.endswith("]"))
                suffix = "（可能是 max_tokens 不足導致截斷）" if is_truncated else "（格式錯誤且 json_repair 無法修復）"
                raise ValueError(f"JSON 解析全部失敗 {suffix}\n末尾 200 字：\n{text[-200:]}")


def load_json(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def save_json(data, path):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ================================================================
# Phase 0：生成評分標準 + Tag Taxonomy
# ================================================================

PHASE0_SYSTEM = """你是一位批判性思考課程的資深助教。
根據本週議題和問題結構：
1. 設計每道評分題的評分標準（rubric）
2. 設計每道評分題的 tag taxonomy（受控詞彙表）

Tag taxonomy 要求：
- error_tags：5-10 個具名的錯誤模式（名稱用英文底線，一眼看出錯誤是什麼）
- quality_tags：3-6 個具名的優點模式
- 類型標籤（argument_types / critique_types 等）：3-8 種預期出現的類型

只輸出 JSON，不含任何說明文字。"""


def phase0_generate_rubric(topic_context: str, df: pd.DataFrame) -> dict:
    # 動態建構問題描述（從 config 讀取）
    q_desc_lines = []
    for q in Q_LIST:
        line = f"  {q['id']}（{q['label']}）[type={q['type']}, role={q['role']}, score={q.get('score', False)}]"
        if q.get("format_hint"):
            line += f"\n    格式要求：{q['format_hint']}"
        if q.get("mc_options"):
            for short_label, full_text in q["mc_options"].items():
                line += f"\n    - {short_label}：{full_text}"
        if q.get("consistency_target_id"):
            line += f"\n    一致性對照：{q['consistency_target_id']}"
        q_desc_lines.append(line)

    q_desc = "\n".join(q_desc_lines)
    scored_ids = ", ".join(SCORED_QS)

    # 為每道評分題生成對應的 schema 區塊
    rubric_schema_parts = []
    for qid in SCORED_QS:
        rubric_schema_parts.append(f'''    "{qid}": {{
      "scoring_criteria": {{
        "9-10": "...", "7-8": "...", "5-6": "...", "3-4": "...", "0-2": "..."
      }},
      "format_checklist": ["（從格式要求衍生的 bool 檢查項目）"]
    }}''')

    taxonomy_schema_parts = []
    tag_display_schema_parts = []
    for q in Q_LIST:
        qid = q["id"]
        if q.get("score"):
            taxonomy_schema_parts.append(f'''    "{qid}": {{
      "error_tags": {{"tag_name": "說明"}},
      "quality_tags": {{"tag_name": "說明"}},
      "argument_types": ["type1", "type2"]
    }}''')
            tag_display_schema_parts.append(f'    "{qid}": {{"（error/quality tag 英文名稱）": "（中文顯示名稱，2-6字）"}}')
        elif q["role"] == "insight_collection":
            taxonomy_schema_parts.append(f'''    "{qid}": {{
      "theme_clusters": ["主題1", "主題2"]
    }}''')
            tag_display_schema_parts.append(f'    "{qid}": {{"（theme_clusters 名稱）": "（中文顯示名稱，2-6字）"}}')

    prompt = f"""
本週課程主題與背景：
{topic_context}

問題結構：
{q_desc}

需要評分的問題：{scored_ids}

請輸出以下格式的 JSON：
{{
  "topic_summary": "（本週議題核心，一段話）",
  "rubrics": {{
{chr(10).join(rubric_schema_parts)}
  }},
  "tag_taxonomy": {{
{chr(10).join(taxonomy_schema_parts)}
  }},
  "tag_display": {{
    （將 tag_taxonomy 中所有 tag 名稱對應到 2-6 字的中文顯示名稱，供視覺化呈現使用）
{chr(10).join(tag_display_schema_parts)}
  }}
}}
"""
    msgs = [{"role": "system", "content": PHASE0_SYSTEM},
            {"role": "user",   "content": prompt}]
    print("  呼叫 LLM 生成評分標準 + Tag Taxonomy...")
    response = call_llm(msgs, model=RUBRIC_MODEL, max_tokens=8000,
                        force_json=FORCE_JSON)
    rubric = safe_json(response)
    save_json(rubric, RUBRIC_PATH)
    print(f"  ✅ 評分標準已儲存至 {RUBRIC_PATH}")
    return rubric


# ================================================================
# Phase 1：個別學生分析
# ================================================================

WF1_SYSTEM = """你是一位嚴格、公正的批判性思考課堂助教。

任務：
1. 根據評分標準對每位學生的回答進行評分與評論
2. 從 tag taxonomy 中選出符合的標籤（只用預設標籤，不自創）

評分原則：
- 嚴格執行評分標準，不因同情放寬
- 評論具體（指出問題的確切位置）
- 一致性檢查：批評越有力，回應就越不應該選「保守」選項；若不一致需指出

標籤選取規則（嚴格執行）：
- 每道題的 error_tags 與 quality_tags 各自【最多 3 個】，選最能代表該答案特徵的
- 超過 3 個視為格式錯誤，多選不會增加資訊，只選最重要的
- 標籤只能來自 tag_taxonomy，不得自創新標籤

只輸出 JSON 陣列，不含任何說明文字。"""


def _build_q1_position_schema() -> str:
    """動態生成 Q1_position 欄位的 schema 字串"""
    context_qs = [q for q in Q_LIST if q["role"] == "context" and q["type"] == "mc"]
    if not context_qs:
        return '"Q1_position": "<學生的初始選擇>"'
    q = context_qs[0]
    opts = " | ".join(q.get("mc_options", {}).keys())
    return f'"Q1_position": "<{opts}>"'


def _build_consistency_schema() -> str:
    """為每道 consistency_check 題生成 schema 欄位"""
    lines = []
    for q in Q_LIST:
        if q["role"] == "consistency_check":
            opts = " | ".join(q.get("mc_options", {}).keys())
            target = q.get("consistency_target_id", "前一題")
            lines.append(f"""  "{q['id']}_consistency": {{
    "choice": "<{opts}>",
    "is_consistent": <bool>,
    "note": "<{q['id']} 選擇與 {target} 批評強度是否邏輯一致>"
  }}""")
    return ",\n".join(lines)


def _build_scored_schema() -> str:
    """為每道評分題生成 schema 欄位"""
    lines = []
    for q in Q_LIST:
        qid = q["id"]
        if not q.get("score"):
            continue
        fmt = q.get("format_hint", "")
        fmt_checks = ""
        if fmt:
            fmt_checks = f'\n    "format_ok": <bool, 是否符合格式：{fmt}>,'
        lines.append(f"""  "{qid}_eval": {{
    "score": <0-10>,{fmt_checks}
    "strengths":  ["<具體優點>"],
    "weaknesses": ["<具體缺點，指出哪裡出問題>"],
    "comment":    "<給學生的建議（中文，2-3句，可執行）>"
  }},
  "{qid}_tags": {{
    "error_tags":   ["<從 tag_taxonomy.{qid}.error_tags 選取>"],
    "quality_tags": ["<從 tag_taxonomy.{qid}.quality_tags 選取>"],
    "type_tag":     "<從 tag_taxonomy.{qid} 的類型清單選一個>"
  }}""")
    return ",\n".join(lines)


def _build_insight_schema() -> str:
    """為每道 insight_collection 題生成 schema 欄位"""
    lines = []
    for q in Q_LIST:
        if q["role"] == "insight_collection":
            lines.append(f"""  "{q['id']}_eval": {{
    "theme": "<一個簡短標籤>",
    "notable": <bool>,
    "note": "<若 notable=true，說明為何值得課堂關注>"
  }},
  "{q['id']}_tags": {{
    "theme_cluster": "<從 tag_taxonomy.{q['id']}.theme_clusters 選最接近的>"
  }}""")
    return ",\n".join(lines)


def build_wf1_prompt(batch: pd.DataFrame, rubric: dict) -> str:
    rubric_text = json.dumps(rubric, ensure_ascii=False, indent=2)

    students = []
    for _, row in batch.iterrows():
        s = {"student_index": int(row.name)}
        for q in Q_LIST:
            if q["type"] == "mc":
                s[q["id"]] = normalize_mc_answer(q["id"], str(row.iloc[q["col"]]))
            else:
                s[q["id"]] = str(row.iloc[q["col"]])
        students.append(s)

    students_block = "\n---\n".join(json.dumps(s, ensure_ascii=False) for s in students)

    avg_formula = " + ".join(f"{qid}.score" for qid in SCORED_QS)
    avg_note = f"({avg_formula}) ÷ {len(SCORED_QS)}"

    schema = f"""{{
  "student_index": <int>,
  {_build_q1_position_schema()},

  // ── 評分題 ──
  {_build_scored_schema()},

  // ── 一致性檢查題 ──
  {_build_consistency_schema()},

  // ── 收集題 ──
  {_build_insight_schema()},

  "overall": {{
    "average_score": <float, {avg_note}，取一位小數>,
    "summary":       "<3-4句整體評語>",
    "top_strength":  "<最值得肯定的一點>",
    "top_weakness":  "<最需要改進的一點>",
    "exceptional":   <bool>
  }}
}}"""

    return f"""評分標準與 Tag Taxonomy：
{rubric_text}

每位學生的輸出格式（所有學生組成 JSON 陣列）：
{schema}

學生回答（共 {len(batch)} 位）：
{students_block}

輸出 JSON 陣列："""


def sanitize_result(r: dict, rubric: dict) -> dict:
    """
    後處理單筆 WF1 結果：
    1. 截斷超標 tags（error_tags / quality_tags 各自最多 3 個）
    2. 移除不合法 tag（不在 rubric taxonomy 內的自創 tag）
    3. 移除 tag 欄位污染（error tag 混入 quality_tags，或反之）
    4. 用 Python 重算 average_score（不依賴 LLM 的算術）
    """
    taxonomy = rubric.get("tag_taxonomy", {})

    for qid in SCORED_QS:
        tags = r.get(f"{qid}_tags", {})
        if not tags:
            continue

        q_tax = taxonomy.get(qid, {})
        valid_error  = set(q_tax.get("error_tags",   {}).keys())
        valid_quality = set(q_tax.get("quality_tags", {}).keys())

        # 1+2+3：過濾合法性 + 污染 + 截斷
        raw_error   = tags.get("error_tags",   [])
        raw_quality = tags.get("quality_tags", [])

        clean_error   = [t for t in raw_error   if t in valid_error][:3]
        clean_quality = [t for t in raw_quality if t in valid_quality][:3]

        tags["error_tags"]   = clean_error
        tags["quality_tags"] = clean_quality

    # 4：Python 重算 average_score
    scores = [r.get(f"{qid}_eval", {}).get("score") for qid in SCORED_QS]
    scores = [s for s in scores if isinstance(s, (int, float))]
    if scores and r.get("overall"):
        r["overall"]["average_score"] = round(sum(scores) / len(scores), 1)

    return r


def phase1_individual(df: pd.DataFrame, rubric: dict) -> list:
    existing  = load_json(WF1_OUTPUT) or []
    processed = {r["student_index"] for r in existing}
    results   = list(existing)

    unprocessed = df[~df.index.isin(processed)]
    total = len(unprocessed)
    print(f"\n📊 學生總數：{len(df)} | 已處理：{len(processed)} | 待處理：{total}")
    if total == 0:
        print("  ✅ 所有學生已處理完畢")
        return results

    done = errors = 0
    for start in range(0, total, BATCH_SIZE):
        batch = unprocessed.iloc[start: start + BATCH_SIZE]
        bn = start // BATCH_SIZE + 1
        tb = (total + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"  [{bn}/{tb}] 學生 {batch.index[0]}-{batch.index[-1]}...", end=" ", flush=True)
        msgs = [{"role": "system", "content": WF1_SYSTEM},
                {"role": "user",   "content": build_wf1_prompt(batch, rubric)}]
        try:
            resp = call_llm(msgs, model=ANALYSIS_MODEL, max_tokens=7000,
                            force_json=FORCE_JSON)
            batch_res = safe_json(resp)
            if isinstance(batch_res, dict):
                batch_res = [batch_res]
            batch_res = [sanitize_result(r, rubric) for r in batch_res]
            results.extend(batch_res)
            save_json(results, WF1_OUTPUT)
            done += len(batch_res)
            print(f"✅ ({done}/{total})")
        except Exception as e:
            errors += 1
            print(f"❌ {e}")
        time.sleep(SLEEP_BETWEEN)

    print(f"\n✅ Phase 1 完成：{done} 位學生，{errors} 批失敗 → {WF1_OUTPUT}")
    return results


# ================================================================
# Phase 2：全局班級分析
# ================================================================

def extract_compact_tags(results: list) -> list:
    """
    從 WF1 結果提取壓縮標籤，每人約 100-150 tokens。
    全班 546 人 ≈ 65,000-80,000 tokens，在 260K context window 內。
    """
    compact = []
    for r in results:
        entry = {
            "i":   r.get("student_index"),
            "Q1":  r.get("Q1_position", ""),
            "avg": r.get("overall", {}).get("average_score"),
            "exc": r.get("overall", {}).get("exceptional", False),
        }
        # 一致性檢查題
        for q in Q_LIST:
            if q["role"] == "consistency_check":
                key = f"{q['id']}_consistency"
                entry[f"{q['id']}_ch"] = r.get(key, {}).get("choice", "")
                entry[f"{q['id']}_ok"] = r.get(key, {}).get("is_consistent", True)
        # 評分題：分數 + 標籤
        for qid in SCORED_QS:
            entry[f"{qid}_sc"] = r.get(f"{qid}_eval", {}).get("score")
            entry[f"{qid}_e"]  = r.get(f"{qid}_tags", {}).get("error_tags",   [])
            entry[f"{qid}_q"]  = r.get(f"{qid}_tags", {}).get("quality_tags", [])
            entry[f"{qid}_t"]  = r.get(f"{qid}_tags", {}).get("type_tag", "")
        # 收集題
        for q in Q_LIST:
            if q["role"] == "insight_collection":
                entry[f"{q['id']}_th"] = r.get(f"{q['id']}_tags", {}).get("theme_cluster", "")
        # AI 疑似偵測（已移除）
        compact.append(entry)
    return compact


def python_frequency_analysis(compact_tags: list) -> dict:
    """2a：Python 精確計算頻率統計"""
    n = len(compact_tags)

    def count_list(key): return Counter(t for r in compact_tags for t in r.get(key, []))
    def count_single(key): return Counter(r.get(key, "") for r in compact_tags if r.get(key))

    # Q1 立場分佈（從 config 的 mc_options 取短標籤）
    context_qs = [q for q in Q_LIST if q["role"] == "context" and q["type"] == "mc"]
    q1_keys = mc_keys(context_qs[0]["id"]) if context_qs else []
    q1_dist = count_single("Q1")

    # 一致性分佈
    consistency_stats = {}
    for q in Q_LIST:
        if q["role"] == "consistency_check":
            consistency_stats[q["id"]] = {
                "choices": dict(count_single(f"{q['id']}_ch").most_common()),
                "inconsistent": sum(1 for r in compact_tags if not r.get(f"{q['id']}_ok", True)),
            }

    # 評分分佈
    score_stats = {}
    for qid in SCORED_QS:
        scores = [r[f"{qid}_sc"] for r in compact_tags if r.get(f"{qid}_sc") is not None]
        if scores:
            score_stats[qid] = {
                "mean":  round(sum(scores) / len(scores), 2),
                "9-10":  sum(1 for s in scores if s >= 9),
                "7-8":   sum(1 for s in scores if 7 <= s < 9),
                "5-6":   sum(1 for s in scores if 5 <= s < 7),
                "3-4":   sum(1 for s in scores if 3 <= s < 5),
                "0-2":   sum(1 for s in scores if s < 3),
            }

    # Tag 頻率
    error_freq   = {qid: dict(count_list(f"{qid}_e").most_common()) for qid in SCORED_QS}
    quality_freq = {qid: dict(count_list(f"{qid}_q").most_common()) for qid in SCORED_QS}
    type_freq    = {qid: dict(count_single(f"{qid}_t").most_common()) for qid in SCORED_QS}

    avg_scores = [r["avg"] for r in compact_tags if r.get("avg") is not None]

    return {
        "total_students":        n,
        "Q1_distribution":       dict(q1_dist.most_common()),
        "consistency_stats":     consistency_stats,
        "score_stats":           score_stats,
        "overall_mean":          round(sum(avg_scores) / len(avg_scores), 2) if avg_scores else None,
        "error_tag_frequency":   error_freq,
        "quality_tag_frequency": quality_freq,
        "type_frequency":        type_freq,
        "exceptional_count":     sum(1 for r in compact_tags if r.get("exc")),
    }


WF2_SYSTEM = """你是一位課程設計師，正在分析全班學生的學習狀況。
資料涵蓋班級所有學生（不是抽樣）。
你的任務：識別常見/罕見的錯誤與優點模式，找出有洞見的學生，提出教學建議。
只輸出 JSON，不含說明文字。"""


def _data_header(compact_tags, freq_stats, rubric):
    return (
        f"頻率統計（Python 精確計算）：\n{json.dumps(freq_stats, ensure_ascii=False, indent=2)}\n\n"
        f"Tag Taxonomy：\n{json.dumps(rubric.get('tag_taxonomy', {}), ensure_ascii=False, indent=2)}\n\n"
        f"全班 {len(compact_tags)} 位學生的壓縮標籤：\n"
        f"（格式：i=index, Q1=初始立場, avg=平均分, exc=是否特別出色/差, "
        f"Qx_sc=分數, Qx_e=錯誤標籤, Qx_q=優點標籤, Qx_t=類型標籤, Qx_th=主題）\n"
        f"{json.dumps(compact_tags, ensure_ascii=False)}"
    )


_PER_Q = """{
  "most_common_errors": [{"tag": "...", "count": <int>, "impact": "<高/中/低>",
    "description": "...", "teaching_fix": "...", "example_indices": [<int>]}],
  "rare_but_notable_errors": [{"tag": "...", "count": <int>, "why_notable": "...", "indices": [<int>]}],
  "most_common_strengths": [{"tag": "...", "count": <int>, "description": "...", "best_examples": [<int>]}],
  "type_distribution_insight": "...",
  "most_insightful_responses": [{"student_index": <int>, "reason": "..."}],
  "best_overall_responses": [{"student_index": <int>, "reason": "..."}]
}"""


def _call(prompt, model, max_tokens):
    msgs = [{"role": "system", "content": WF2_SYSTEM},
            {"role": "user",   "content": prompt}]
    return safe_json(call_llm(msgs, model=model, max_tokens=max_tokens,
                              force_json=FORCE_JSON))


def phase2_llm_global(compact_tags, freq_stats, rubric):
    header = _data_header(compact_tags, freq_stats, rubric)
    per_q_results = {}

    for idx, qid in enumerate(SCORED_QS):
        print(f"       [2b-{idx+1}] {qid}...", end=" ", flush=True)
        schema = {qid: _PER_Q}
        prompt = f"{header}\n\n只分析 {qid}，輸出：{json.dumps(schema, ensure_ascii=False)}"
        try:
            result = _call(prompt, AGGREGATE_MODEL, 8000)
            per_q_results.update(result)
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
        time.sleep(SLEEP_BETWEEN)

    print(f"       [2b-{len(SCORED_QS)+1}] 交叉分析 + 困惑點...", end=" ", flush=True)
    insight_ids = [q["id"] for q in Q_LIST if q["role"] == "insight_collection"]
    confusion_note = f"分析 {insight_ids} 的困惑主題聚類" if insight_ids else ""
    cross_prompt = f"""{header}

只輸出以下 JSON（不含其他欄位）：
{{
  "cross_analysis": {{
    "position_vs_quality": "...",
    "consistency_analysis": "...",
    "high_scorer_profile": "...",
    "low_scorer_profile": "..."
  }},
  "confusion_analysis": {{
    "major_themes": [{{"theme": "...", "count": <int>, "core_question": "...", "teaching_suggestion": "..."}}],
    "deepest_confusions": [{{"student_index": <int>, "theme": "...", "reason": "..."}}]
  }},
  "students_worth_highlighting": {{
    "exceptional_positive": [{{"student_index": <int>, "reason": "..."}}],
    "exceptional_negative": [{{"student_index": <int>, "concern": "..."}}],
    "interesting_trajectories": [{{"student_index": <int>, "note": "..."}}]
  }},
  "teaching_priorities": [
    {{"priority": 1, "issue": "...", "recommendation": "..."}}
  ]
}}
{confusion_note}"""
    try:
        cross = _call(cross_prompt, AGGREGATE_MODEL, 8000)
        print("✅")
    except Exception as e:
        print(f"❌ {e}")
        cross = {}
    time.sleep(SLEEP_BETWEEN)

    return {"per_question_patterns": per_q_results, **cross}


def retrieve_examples(results, indices, fields=None):
    idx_map = {r["student_index"]: r for r in results}
    out = []
    for i in indices:
        r = idx_map.get(i)
        if r:
            out.append({f: r.get(f) for f in fields} if fields else r)
    return out


def phase2_class_analysis(results, rubric):
    print(f"\n📊 開始 Phase 2（全班 {len(results)} 位學生）...")

    compact = extract_compact_tags(results)
    freq    = python_frequency_analysis(compact)
    est     = len(json.dumps(compact, ensure_ascii=False)) // 4
    print(f"  [2a] 壓縮標籤：{est:,} tokens | 整體平均分：{freq.get('overall_mean')}")

    n_calls = len(SCORED_QS) + 1
    print(f"  [2b] 全局 LLM 分析（共 {n_calls} 次呼叫）...")
    try:
        llm_ana = phase2_llm_global(compact, freq, rubric)
    except Exception as e:
        print(f"  [2b] ❌ {e}")
        llm_ana = {"error": str(e)}

    print("  [2c] 取回代表性學生...")
    indices = set()
    for pat in llm_ana.get("per_question_patterns", {}).values():
        for section in pat.values():
            if isinstance(section, list):
                for item in section:
                    if isinstance(item, dict):
                        for k in ["example_indices", "indices", "best_examples", "student_index"]:
                            v = item.get(k)
                            if isinstance(v, list): indices.update(v)
                            elif isinstance(v, int): indices.add(v)
    for section in llm_ana.get("students_worth_highlighting", {}).values():
        for item in section:
            if isinstance(item, dict): indices.add(item.get("student_index"))
    indices.discard(None)

    examples = retrieve_examples(results, list(indices),
        fields=["student_index"] + [f"{q['id']}_eval" for q in Q_LIST if q.get("score")] + ["overall"])
    print(f"       取回 {len(examples)} 位代表性學生")

    report = {
        "meta":             {"total": len(results), "topic": rubric.get("topic_summary", "")},
        "quantitative":     freq,
        "llm_analysis":     llm_ana,
        "examples":         {str(r["student_index"]): r for r in examples},
    }
    save_json(report, WF2_OUTPUT)
    print(f"\n✅ Phase 2 完成 → {WF2_OUTPUT}")
    return report


# ================================================================
# 主程式
# ================================================================

MENU = f"""
╔══════════════════════════════════════════════╗
║     課堂回覆分析 Agent v3（Config 驅動）     ║
╠══════════════════════════════════════════════╣
║  週次：{CFG['meta'].get('week_label', '（未設定）'):<36}║
║  CSV：{CFG['meta'].get('csv_path', '（未設定）'):<37}║
╠══════════════════════════════════════════════╣
║  0. Phase 0：生成評分標準 + Tag Taxonomy     ║
║  1. Phase 1：個別學生分析（含標籤）          ║
║  2. Phase 2：全局班級分析                    ║
║  3. 完整流程（0 → 1 → 2）                   ║
║  q. 離開                                     ║
╚══════════════════════════════════════════════╝
"""


def main():
    print(MENU)
    mode = input("選擇模式：").strip().lower()
    if mode == "q":
        return

    if not Path(CSV_PATH).exists():
        print(f"❌ 找不到 {CSV_PATH}")
        sys.exit(1)

    df = pd.read_csv(CSV_PATH)
    print(f"📂 已載入 {CSV_PATH}：{len(df)} 位學生，{len(df.columns)} 欄")

    rubric = None

    if mode in ("0", "3"):
        print("\n📝 請輸入本週議題背景（輸入 END 結束）：")
        lines = []
        while (line := input()) != "END":
            lines.append(line)
        rubric = phase0_generate_rubric("\n".join(lines), df)

    if mode in ("1", "3"):
        rubric = rubric or load_json(RUBRIC_PATH)
        if not rubric:
            print("❌ 找不到 rubric.json，請先執行 Phase 0")
            sys.exit(1)
        phase1_individual(df, rubric)

    if mode in ("2", "3"):
        results = load_json(WF1_OUTPUT)
        if not results:
            print("❌ 找不到 wf1_results.json，請先執行 Phase 1")
            sys.exit(1)
        rubric = rubric or load_json(RUBRIC_PATH) or {}
        phase2_class_analysis(results, rubric)

    print("\n🎉 完成！")


if __name__ == "__main__":
    main()
