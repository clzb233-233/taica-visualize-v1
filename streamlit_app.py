import streamlit as st

st.set_page_config(
    page_title="課堂分析視覺化工具",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    [data-testid="stToolbarActions"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize global session state
st.session_state.setdefault("rubric", None)
st.session_state.setdefault("wf1", None)
st.session_state.setdefault("wf2", None)
st.session_state.setdefault("csv_df", None)
st.session_state.setdefault("tag_display", {})
st.session_state.setdefault("wf1_by_index", {})
st.session_state.setdefault("jump_to_student", None)

# Check if data is loaded
data_loaded = (
    st.session_state.rubric is not None
    and st.session_state.wf1 is not None
    and st.session_state.wf2 is not None
)

# Define pages
load_page = st.Page("app_pages/load_data.py", title="載入資料", icon=":material/folder_open:")
overview_page = st.Page("app_pages/overview.py", title="全班概覽", icon=":material/bar_chart:")
question_page = st.Page("app_pages/question_analysis.py", title="逐題分析", icon=":material/edit_note:")
student_page = st.Page("app_pages/student_detail.py", title="個別學生", icon=":material/manage_search:")
rubric_page = st.Page("app_pages/rubric_reference.py", title="評分標準參考", icon=":material/menu_book:")

page = st.navigation(
    {
        "": [load_page],
        "分析": [overview_page, question_page, student_page, rubric_page],
    },
    position="sidebar",
)

page.run()
