import json
import streamlit as st
import pandas as pd
import os


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
    import io
    return pd.read_csv(io.BytesIO(content))


@st.cache_data
def load_default_data():
    """Load data from W{N} folder."""
    base_path = "W11"
    rubric_path = os.path.join(base_path, "rubric.json")
    wf1_path = os.path.join(base_path, "wf1_results.json")
    wf2_path = os.path.join(base_path, "wf2_report.json")
    csv_path = os.path.join(base_path, "W11.csv")
    config_path = os.path.join(base_path, "config.json")

    rubric = wf1 = wf2 = csv_df = config = None
    tag_display = {}

    if os.path.exists(rubric_path):
        with open(rubric_path, "r", encoding="utf-8") as f:
            rubric = json.load(f)
        tag_display = build_tag_display(rubric)

    if os.path.exists(wf1_path):
        with open(wf1_path, "r", encoding="utf-8") as f:
            wf1 = json.load(f)

    if os.path.exists(wf2_path):
        with open(wf2_path, "r", encoding="utf-8") as f:
            wf2 = json.load(f)

    if os.path.exists(csv_path):
        with open(csv_path, "rb") as f:
            csv_df = parse_csv(f.read())

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

    return rubric, wf1, wf2, csv_df, tag_display, config


# ── Auto-load data ────────────────────────────────────────────────────────────
if st.session_state.get("rubric") is None:
    rubric, wf1, wf2, csv_df, tag_display, config = load_default_data()
    if rubric is not None:
        st.session_state.rubric = rubric
        st.session_state.tag_display = tag_display
    if wf1 is not None:
        st.session_state.wf1 = wf1
        st.session_state.wf1_by_index = {r["student_index"]: r for r in wf1}
    if wf2 is not None:
        st.session_state.wf2 = wf2
    if csv_df is not None:
        st.session_state.csv_df = csv_df
    if config is not None:
        st.session_state.viz_config = config

# ── Page ──────────────────────────────────────────────────────────────────────
st.title("📂 資料狀態")

rubric = st.session_state.get("rubric")
wf1 = st.session_state.get("wf1")
wf2 = st.session_state.get("wf2")
csv_df = st.session_state.get("csv_df")

if rubric is not None:
    week_num = rubric.get("week", "?")
    st.success(f"✅ rubric.json 已載入（第 {week_num} 週）")
else:
    st.error("❌ rubric.json 載入失敗")

if wf1 is not None:
    st.success(f"✅ wf1_results.json 已載入（{len(wf1)} 位學生）")
else:
    st.error("❌ wf1_results.json 載入失敗")

if wf2 is not None:
    st.success("✅ wf2_report.json 已載入")
else:
    st.error("❌ wf2_report.json 載入失敗")

if csv_df is not None:
    st.success(f"✅ CSV 已載入（{len(csv_df)} 列）")
else:
    st.info("⬜ CSV 未載入（個別學生頁將無法顯示原始回答）")

if rubric is not None and wf1 is not None and wf2 is not None:
    st.divider()
    st.success("🎉 核心資料已全部載入！請從左側選單切換至各分析頁面。")
