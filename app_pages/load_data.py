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
                result[tag] = value  # value is already a Chinese string
    return result


@st.cache_data
def parse_json(content: bytes):
    return json.loads(content)


@st.cache_data
def parse_csv(content: bytes) -> pd.DataFrame:
    import io
    return pd.read_csv(io.BytesIO(content))


def load_default_data():
    """Load sample data from W10 folder if available."""
    base_path = "W10"
    # Try to load rubric
    rubric_path = os.path.join(base_path, "rubric.json")
    wf1_path = os.path.join(base_path, "wf1_results.json")
    wf2_path = os.path.join(base_path, "wf2_report.json")
    csv_path = os.path.join(base_path, "W10.csv")
    
    rubric = None
    wf1 = None
    wf2 = None
    csv_df = None
    tag_display = {}
    
    # Load rubric
    if os.path.exists(rubric_path):
        try:
            with open(rubric_path, "r", encoding="utf-8") as f:
                rubric = json.load(f)
            tag_display = build_tag_display(rubric)
        except Exception as e:
            st.error(f"載入預設 rubric.json 失敗：{e}")
    
    # Load wf1
    if os.path.exists(wf1_path):
        try:
            with open(wf1_path, "r", encoding="utf-8") as f:
                wf1 = json.load(f)
        except Exception as e:
            st.error(f"載入預設 wf1_results.json 失敗：{e}")
    
    # Load wf2
    if os.path.exists(wf2_path):
        try:
            with open(wf2_path, "r", encoding="utf-8") as f:
                wf2 = json.load(f)
        except Exception as e:
            st.error(f"載入預設 wf2_report.json 失敗：{e}")
    
    # Load CSV
    if os.path.exists(csv_path):
        try:
            with open(csv_path, "rb") as f:
                csv_data = f.read()
            csv_df = parse_csv(csv_data)
        except Exception as e:
            st.error(f"載入預設 W10.csv 失敗：{e}")
    
    return rubric, wf1, wf2, csv_df, tag_display


st.title("📂 載入資料")
st.markdown("請上傳分析所需的 JSON 檔案，CSV 為選填。")

col1, col2 = st.columns(2)

with col1:
    rubric_file = st.file_uploader("rubric.json *", type=["json"], key="rubric_upload")
    wf2_file = st.file_uploader("wf2_report.json *", type=["json"], key="wf2_upload")

with col2:
    wf1_file = st.file_uploader("wf1_results.json *", type=["json"], key="wf1_upload")
    csv_file = st.file_uploader("W{N}.csv（選填）", type=["csv"], key="csv_upload")

# Process uploads
if rubric_file is not None:
    try:
        rubric_data = parse_json(rubric_file.read())
        st.session_state.rubric = rubric_data
        st.session_state.tag_display = build_tag_display(rubric_data)
    except Exception as e:
        st.error(f"rubric.json 解析失敗：{e}")

if wf1_file is not None:
    try:
        wf1_data = parse_json(wf1_file.read())
        st.session_state.wf1 = wf1_data
        st.session_state.wf1_by_index = {r["student_index"]: r for r in wf1_data}
    except Exception as e:
        st.error(f"wf1_results.json 解析失敗：{e}")

if wf2_file is not None:
    try:
        wf2_data = parse_json(wf2_file.read())
        st.session_state.wf2 = wf2_data
    except Exception as e:
        st.error(f"wf2_report.json 解析失敗：{e}")

if csv_file is not None:
    try:
        csv_data = parse_csv(csv_file.read())
        st.session_state.csv_df = csv_data
    except Exception as e:
        st.error(f"CSV 解析失敗：{e}")

# If any core data missing, try to load defaults
if "rubric" not in st.session_state or st.session_state.rubric is None:
    default_rubric, default_wf1, default_wf2, default_csv, default_tag = load_default_data()
    if default_rubric is not None:
        st.session_state.rubric = default_rubric
        st.session_state.tag_display = default_tag
        st.info("🔄 已載入預設 rubric.json（來自 W10 資料夾）")
    else:
        st.warning("⬜ 無法載入預設 rubric.json")

if "wf1" not in st.session_state or st.session_state.wf1 is None:
    default_rubric, default_wf1, default_wf2, default_csv, default_tag = load_default_data()
    if default_wf1 is not None:
        st.session_state.wf1 = default_wf1
        st.session_state.wf1_by_index = {r["student_index"]: r for r in default_wf1}
        st.info("🔄 已載入預設 wf1_results.json（來自 W10 資料夾）")
    else:
        st.warning("⬜ 無法載入預設 wf1_results.json")

if "wf2" not in st.session_state or st.session_state.wf2 is None:
    default_rubric, default_wf1, default_wf2, default_csv, default_tag = load_default_data()
    if default_wf2 is not None:
        st.session_state.wf2 = default_wf2
        st.info("🔄 已載入預設 wf2_report.json（來自 W10 資料夾）")
    else:
        st.warning("⬜ 無法載入預設 wf2_report.json")

if "csv_df" not in st.session_state or st.session_state.csv_df is None:
    default_rubric, default_wf1, default_wf2, default_csv, default_tag = load_default_data()
    if default_csv is not None:
        st.session_state.csv_df = default_csv
        st.info("🔄 已載入預設 W10.csv（來自 W10 資料夾）")
    else:
        st.info("⬜ 未上傳 CSV 檔案（個別學生頁將無法顯示原始回答）")

# Status summary
st.divider()
st.subheader("載入狀態")

rubric = st.session_state.get("rubric")
wf1 = st.session_state.get("wf1")
wf2 = st.session_state.get("wf2")
csv_df = st.session_state.get("csv_df")

if rubric is not None:
    week_num = rubric.get("week", "?")
    st.success(f"✅ rubric.json 已載入（第 {week_num} 週）")
else:
    st.warning("⬜ rubric.json 尚未上傳")

if wf1 is not None:
    st.success(f"✅ wf1_results.json 已載入（{len(wf1)} 位學生）")
else:
    st.warning("⬜ wf1_results.json 尚未上傳")

if wf2 is not None:
    st.success("✅ wf2_report.json 已載入")
else:
    st.warning("⬜ wf2_report.json 尚未上傳")

if csv_df is not None:
    st.success(f"✅ CSV 已載入（{len(csv_df)} 列）")
else:
    st.info("⬜ CSV 未上傳（個別學生頁將無法顯示原始回答）")

if rubric is not None and wf1 is not None and wf2 is not None:
    st.divider()
    st.success("🎉 核心資料已全部載入！請從左側選單切換至各分析頁面。")