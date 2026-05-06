import streamlit as st
import pandas as pd
from app_pages.utils import (
    require_data, display_tag, get_scored_questions, get_all_questions,
    get_student_eval, get_student_tags, get_student_score
)

st.title("🔍 個別學生")

if not require_data():
    st.stop()

rubric = st.session_state.rubric
wf1: list = st.session_state.wf1
wf1_by_index: dict = st.session_state.wf1_by_index
csv_df = st.session_state.get("csv_df")

scored_qs = get_scored_questions(rubric)
all_qs = get_all_questions(rubric, wf1[0] if wf1 else None)

# ── Build dataframe ───────────────────────────────────────────────────────────
rows = []
for record in wf1:
    idx = record.get("student_index")
    overall = record.get("overall", {})

    position = str(record.get("Q1_position", "—") or "—")

    row = {"#": f"#{idx}", "_idx": idx, "立場": position}
    scores_list = []
    for q in scored_qs:
        qid = q["id"]
        sc = get_student_score(record, qid)
        row[qid] = sc
        if sc is not None:
            scores_list.append(sc)

    avg = overall.get("average_score")
    if avg is None and scores_list:
        avg = round(sum(scores_list) / len(scores_list), 2)
    row["平均分"] = avg

    # Q4 consistency
    q4 = record.get("Q4_consistency", {})
    row["一致性"] = "✅" if q4.get("is_consistent", True) else "⚠️"

    row["_exceptional"] = overall.get("exceptional", False)

    rows.append(row)

all_df = pd.DataFrame(rows)

# ── Filters ───────────────────────────────────────────────────────────────────
st.subheader("篩選條件")

filter_cols = st.columns([2, 2, 2, 2])
positions = sorted(all_df["立場"].dropna().unique().tolist())
with filter_cols[0]:
    selected_positions = st.multiselect("立場", positions, default=positions, key="filter_pos")
with filter_cols[1]:
    score_range = st.slider("平均分範圍", 0.0, 10.0, (0.0, 10.0), step=0.5, key="filter_score")
with filter_cols[2]:
    exceptional_filter = st.selectbox("特殊學生", ["全部", "只看特別出色", "只看特別差"], key="filter_exceptional")
with filter_cols[3]:
    consistency_filter = st.selectbox("一致性", ["全部", "只看不一致"], key="filter_consistency")

# Apply filters
filtered_df = all_df.copy()
if selected_positions:
    filtered_df = filtered_df[filtered_df["立場"].isin(selected_positions)]

filtered_df = filtered_df[
    filtered_df["平均分"].apply(
        lambda x: (score_range[0] <= x <= score_range[1]) if x is not None else True
    )
]

if exceptional_filter == "只看特別出色":
    filtered_df = filtered_df[filtered_df["_exceptional"].astype(bool)]
elif exceptional_filter == "只看特別差":
    filtered_df = filtered_df[~filtered_df["_exceptional"].astype(bool)]

if consistency_filter == "只看不一致":
    filtered_df = filtered_df[filtered_df["一致性"] == "⚠️"]

st.caption(f"顯示 {len(filtered_df)} / {len(all_df)} 位學生")
st.divider()

# ── Student Table ─────────────────────────────────────────────────────────────
display_cols = ["#", "立場"] + [q["id"] for q in scored_qs] + ["平均分", "一致性"]
if show_ai:
    display_cols.append("AI 疑似")

display_df = filtered_df[display_cols].copy()

selected = st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key="student_table",
)

# ── Student Detail Panel ──────────────────────────────────────────────────────
selection = selected.get("selection", {}) if selected else {}
selected_rows = selection.get("rows", [])

# Handle jump_to_student
jump_idx = st.session_state.get("jump_to_student")
if jump_idx is not None and not selected_rows:
    match = filtered_df[filtered_df["_idx"] == jump_idx]
    if not match.empty:
        # Can't programmatically select rows in dataframe; just scroll to top
        pass
    st.session_state["jump_to_student"] = None

if selected_rows:
    row_pos = selected_rows[0]
    if row_pos < len(filtered_df):
        actual_idx = int(filtered_df.iloc[row_pos]["_idx"])
        record = wf1_by_index.get(actual_idx, {})
        overall = record.get("overall", {})

        st.divider()
        st.subheader(f"學生詳情 — #{actual_idx}")

        # Top summary
        avg_score = overall.get("average_score", filtered_df.iloc[row_pos]["平均分"])
        st.markdown(f"**平均分：** {avg_score}")
        summary = overall.get("summary", "")
        if summary:
            st.info(summary)

        col_s, col_w = st.columns(2)
        if overall.get("top_strength"):
            col_s.success(f"✅ 優點：{overall['top_strength']}")
        if overall.get("top_weakness"):
            col_w.error(f"❌ 弱點：{overall['top_weakness']}")

        if overall.get("exceptional"):
            st.info("🌟 特別出色（exceptional）")

        st.divider()

        # Per-question tabs
        q_tabs = st.tabs([q["label"] for q in all_qs])

        for i, q in enumerate(all_qs):
            qid = q["id"]
            q_type = q["type"]

            with q_tabs[i]:
                # Column reference caption + CSV index from config
                viz_config = st.session_state.get("viz_config")
                if viz_config:
                    col_info = viz_config.get("csv_column_mapping", {}).get(qid)
                    if col_info:
                        st.caption(f"題目說明：{col_info['description']}")
                    csv_col_index = col_info["index"] if col_info else None
                else:
                    # Fallback: Q1->index1, Q2->index2, etc.
                    q_num = int(qid[1:]) if qid.startswith("Q") and qid[1:].isdigit() else None
                    csv_col_index = q_num if q_num else None

                # Original answer from CSV
                csv_answer_displayed = False
                if csv_df is not None:
                    try:
                        if csv_col_index is not None and actual_idx < len(csv_df):
                            raw_ans = csv_df.iloc[actual_idx, csv_col_index]
                            if pd.notna(raw_ans) and str(raw_ans).strip():
                                with st.expander("📄 原始回答", expanded=True):
                                    st.write(str(raw_ans))
                                csv_answer_displayed = True
                            else:
                                st.caption("(此題無原始回答)")
                        elif csv_col_index is None:
                            pass  # No mapping for this question
                        else:
                            st.caption(f"(學生索引 {actual_idx} 超出 CSV 範圍 {len(csv_df)})")
                    except Exception as e:
                        st.caption(f"（原始回答讀取失敗: {str(e)}）")
                
                if not csv_answer_displayed and csv_df is None:
                    st.caption("（未上傳填答紀錄，無法顯示原始回答）")

                if q_type == "mc":
                    position_val = record.get("Q1_position", "—")
                    st.markdown(f"**Q1 立場：** {position_val}")

                elif q_type == "scored":
                    ev = get_student_eval(record, qid)
                    tags = get_student_tags(record, qid)
                    if not ev:
                        st.info("分析資料不存在")
                        continue

                    score = ev.get("score")
                    format_ok = ev.get("format_ok")
                    comment = ev.get("comment", "")
                    strengths = ev.get("strengths", [])
                    weaknesses = ev.get("weaknesses", [])
                    error_tags = tags.get("error_tags", [])
                    quality_tags = tags.get("quality_tags", [])
                    type_tag = tags.get("type_tag", "")

                    # Score and format - using container for better visual grouping
                    with st.container(border=True):
                        m1, m2 = st.columns([1, 1])
                        m1.metric("分數", score)
                        if format_ok is not None:
                            m2.markdown(f"格式：{'✅' if format_ok else '❌'}")

                    st.divider()

                    # Comment section
                    if comment:
                        with st.container(border=True):
                            st.markdown("### 💬 評語")
                            st.markdown(comment)

                    st.divider()

                    # Strengths and Weaknesses
                    if strengths or weaknesses:
                        with st.container(border=True):
                            t1, t2 = st.columns(2)
                            if strengths:
                                with t1:
                                    st.markdown("### ✅ 優點")
                                    for s in strengths:
                                        st.markdown(f"- {s}")
                            if weaknesses:
                                with t2:
                                    st.markdown("### ❌ 弱點")
                                    for w in weaknesses:
                                        st.markdown(f"- {w}")

                    st.divider()

                    # Tags section
                    if error_tags or quality_tags or type_tag:
                        with st.container(border=True):
                            r1, r2, r3 = st.columns(3)
                            if error_tags:
                                with r1:
                                    st.markdown("### 🔴 錯誤 Tags")
                                    for t in error_tags:
                                        st.markdown(f"- :red[{display_tag(t)}]")
                            if quality_tags:
                                with r2:
                                    st.markdown("### 🟢 品質 Tags")
                                    for t in quality_tags:
                                        st.markdown(f"- :green[{display_tag(t)}]")
                            if type_tag:
                                with r3:
                                    st.markdown(f"**論證類型：** :blue[{display_tag(type_tag)}]")

                elif q_type == "consistency":
                    q4 = record.get("Q4_consistency", {})
                    if not q4:
                        st.info("分析資料不存在")
                        continue
                    choice = q4.get("choice", "")
                    is_consistent = q4.get("is_consistent", True)
                    note = q4.get("note", "")
                    
                    with st.container(border=True):
                        st.markdown(f"**選擇：** {choice}")
                        st.markdown(f"**一致性：** {'✅ 一致' if is_consistent else '⚠️ 不一致'}")
                        if note:
                            st.markdown(f"**備注：** {note}")

                else:  # collect / Q7
                    ev = get_student_eval(record, qid)
                    tags = get_student_tags(record, qid)
                    if not ev and not tags:
                        st.info("分析資料不存在")
                        continue
                    theme = ev.get("theme", "") if ev else ""
                    notable = ev.get("notable", False) if ev else False
                    note = ev.get("note", "") if ev else ""
                    theme_cluster = tags.get("theme_cluster", "") if tags else ""
                    
                    if theme:
                        with st.container(border=True):
                            st.markdown(f"**主題：** {theme}")
                    if theme_cluster:
                        with st.container(border=True):
                            st.markdown(f"**主題群：** {display_tag(theme_cluster)}")
                    if notable:
                        st.info("✨ 值得注意")
                    if note:
                        with st.container(border=True):
                            st.markdown(f"**備注：** {note}")

        # AI Detection
        if show_ai:
            st.divider()
            ai_det = record.get("ai_detection", {})
            ai_score = ai_det.get("score", ai_det.get("ai_score", 0)) or 0
            ai_reason = ai_det.get("reason", "")
            st.markdown("**🔒 AI 疑似偵測**")
            color = "green" if ai_score <= 3 else ("orange" if ai_score <= 6 else "red")
            st.markdown(f"分數：**:{color}[{ai_score}/10]**")
            bar_color = "#2ca02c" if ai_score <= 3 else ("#f39c12" if ai_score <= 6 else "#d62728")
            bar_pct = int(ai_score * 10)
            st.markdown(
                f"""<div style='background:#eee;border-radius:6px;height:14px;width:100%'>
                <div style='background:{bar_color};border-radius:6px;height:14px;width:{bar_pct}%'></div>
                </div>""",
                unsafe_allow_html=True,
            )
            if ai_reason:
                st.markdown(f"說明：{ai_reason}")