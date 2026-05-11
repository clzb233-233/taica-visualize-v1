import json
import io
import pathlib
import pandas as pd
import streamlit as st

# repo 根目錄的絕對路徑（不管在哪個環境執行都正確）
REPO_ROOT = pathlib.Path(__file__).parent.parent


def build_tag_display(rubric: dict) -> dict:
    """Flatten tag_display from rubric into {tag: Chinese_name}."""
    result = {}
    tag_display = rubric.get("tag_display", {})
    for question_tags in tag_display.values():
        if isinstance(question_tags, dict):
            for tag, value in question_tags.items():
                result[tag] = value
    return result


@st.cache_data
def parse_csv(content: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(content))


@st.cache_data
def load_default_data():
    """自動找 repo 根目錄下的 W* 資料夾並載入資料。"""
    # 自動偵測 W* 資料夾（例如 W11/），不需要 hardcode 週次
    candidates = sorted(REPO_ROOT.glob("W*/"))
    if not candidates:
        return None, None, None, None, {}, None
    base_path = candidates[-1]  # 取最新一週（資料夾名稱最大）

    rubric_path  = base_path / "rubric.json"
    wf1_path     = base_path / "wf1_results.json"
    wf2_path     = base_path / "wf2_report.json"
    config_path  = base_path / "config.json"

    # CSV 檔名與資料夾同名（例如 W11/W11.csv）
    csv_candidates = list(base_path.glob("*.csv"))
    csv_path = csv_candidates[0] if csv_candidates else None

    rubric = wf1 = wf2 = csv_df = config = None
    tag_display = {}

    if rubric_path.exists():
        rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
        tag_display = build_tag_display(rubric)

    if wf1_path.exists():
        wf1 = json.loads(wf1_path.read_text(encoding="utf-8"))

    if wf2_path.exists():
        wf2 = json.loads(wf2_path.read_text(encoding="utf-8"))

    if csv_path and csv_path.exists():
        csv_df = parse_csv(csv_path.read_bytes())

    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))

    return rubric, wf1, wf2, csv_df, tag_display, config
