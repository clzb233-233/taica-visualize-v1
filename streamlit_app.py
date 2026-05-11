import glob
import pathlib
import streamlit as st
from app_pages.load_data import load_default_data

REPO_ROOT = pathlib.Path(__file__).parent  # repo 根目錄


def detect_week_label() -> str:
    """Read the CSV filename from the data folder to determine the current week."""
    candidates = sorted(REPO_ROOT.glob("W*/"))
    if not candidates:
        return "週次未知"
    base_path = candidates[-1]             # 最新一週的資料夾
    csv_files = list(base_path.glob("*.csv"))
    if not csv_files:
        return "週次未知"
    stem = csv_files[0].stem              # e.g. "W11"
    if stem.upper().startswith("W") and stem[1:].isdigit():
        return f"第 {stem[1:]} 週"
    return stem

st.set_page_config(
    page_title="課堂分析視覺化工具",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize global session state
st.session_state.setdefault("rubric", None)
st.session_state.setdefault("wf1", None)
st.session_state.setdefault("wf2", None)
st.session_state.setdefault("csv_df", None)
st.session_state.setdefault("tag_display", {})
st.session_state.setdefault("wf1_by_index", {})
st.session_state.setdefault("jump_to_student", None)
st.session_state.setdefault("viz_config", None)

# Auto-load default data on first run
if st.session_state.get("rubric") is None:
    result = load_default_data()
    if result is not None:
        rubric, wf1, wf2, csv_df, tag_display, config = result
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

# ── Week badge (sidebar top, above navigation) ────────────────────────────────
with st.sidebar:
    week_label = detect_week_label()
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #1a73e8, #0d47a1);
            border-radius: 10px;
            padding: 10px 16px;
            margin-bottom: 8px;
            text-align: center;
        ">
            <div style="color: #a8c8ff; font-size: 11px; letter-spacing: 1px; text-transform: uppercase;">分析週次</div>
            <div style="color: #ffffff; font-size: 22px; font-weight: 700; line-height: 1.3;">{week_label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Define pages
overview_page = st.Page("app_pages/overview.py", title="全班概覽", icon=":material/bar_chart:")
question_page = st.Page("app_pages/question_analysis.py", title="逐題分析", icon=":material/edit_note:")
student_page = st.Page("app_pages/student_detail.py", title="個別學生", icon=":material/manage_search:")
rubric_page = st.Page("app_pages/rubric_reference.py", title="評分標準參考", icon=":material/menu_book:")

page = st.navigation(
    {
        "分析": [overview_page, question_page, student_page, rubric_page],
    },
    position="sidebar",
)

page.run()

with st.sidebar:
    st.divider()
    config = st.session_state.get("viz_config")
    if config:
        st.caption("**題目說明**")
        mapping = config.get("csv_column_mapping", {})
        for qid, info in mapping.items():
            st.caption(f"{qid}：{info['description']}")
    else:
        st.caption("**題目欄位對照**")
        st.caption("Q1 → B 欄　Q2 → C 欄　Q3 → D 欄　Q4 → E 欄　Q5 → F 欄　Q6 → G 欄　Q7 → H 欄　Q8 → I 欄")
