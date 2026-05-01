import streamlit as st
import pandas as pd
from app_pages.utils import require_data, get_scored_questions

st.title("📚 評分標準參考")

if not require_data():
    st.stop()

rubric = st.session_state.rubric
tag_display = st.session_state.tag_display
tag_taxonomy = rubric.get("tag_taxonomy", {})
scored_qs = get_scored_questions(rubric)

# ── Section A: Topic Summary ──────────────────────────────────────────────────
topic_summary = rubric.get("topic_summary", "")
if topic_summary:
    st.subheader("本週議題摘要")
    st.markdown(topic_summary)
    st.divider()

# ── Section B: Scoring Criteria ──────────────────────────────────────────────
st.subheader("各題評分標準")

rubrics_data = rubric.get("rubrics", {})

if not scored_qs:
    st.info("無評分題資料。")
else:
    for q in scored_qs:
        qid = q["id"]
        label = q["label"]
        format_checklist = q.get("format_checklist", [])
        scoring_criteria = q.get("scoring_criteria", {})

        with st.expander(label, expanded=False):
            if format_checklist:
                st.markdown("**格式檢查清單：**")
                for item in format_checklist:
                    st.markdown(f"- {item}")

            if scoring_criteria:
                st.markdown("**分段評分標準：**")
                rows = []
                # sort by score range descending
                for score_range, desc in scoring_criteria.items():
                    rows.append({"分數段": score_range, "描述": desc})
                if rows:
                    st.dataframe(
                        pd.DataFrame(rows),
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "分數段": st.column_config.TextColumn(width="small"),
                            "描述": st.column_config.TextColumn(width="large"),
                        }
                    )

st.divider()

# ── Section C: Tag Reference ──────────────────────────────────────────────────
st.subheader("Tag 對照表")

if not scored_qs:
    st.info("無評分題資料。")
    st.stop()

tab_labels = [q["label"] for q in scored_qs]
tabs = st.tabs(tab_labels)

for i, q in enumerate(scored_qs):
    qid = q["id"]
    with tabs[i]:
        q_taxonomy = tag_taxonomy.get(qid, {})
        error_tags = q_taxonomy.get("error_tags", {})
        quality_tags = q_taxonomy.get("quality_tags", {})
        arg_types = q_taxonomy.get("argument_types", q_taxonomy.get("critique_types", []))
        q_display = rubric.get("tag_display", {}).get(qid, {})

        t_cols = st.columns(3)

        with t_cols[0]:
            st.markdown("**錯誤 Tags**")
            if error_tags and isinstance(error_tags, dict):
                rows = []
                for tag, cn_desc in error_tags.items():
                    cn_name = q_display.get(tag, tag_display.get(tag, tag))
                    rows.append({"英文名稱": tag, "中文名稱": cn_name, "說明": cn_desc})
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info("無資料")

        with t_cols[1]:
            st.markdown("**品質 Tags**")
            if quality_tags and isinstance(quality_tags, dict):
                rows = []
                for tag, cn_desc in quality_tags.items():
                    cn_name = q_display.get(tag, tag_display.get(tag, tag))
                    rows.append({"英文名稱": tag, "中文名稱": cn_name, "說明": cn_desc})
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info("無資料")

        with t_cols[2]:
            st.markdown("**論證類型**")
            if arg_types:
                for at in arg_types:
                    cn_name = q_display.get(at, tag_display.get(at, at))
                    st.markdown(f"- **{cn_name}** `{at}`")
            else:
                st.info("無資料")
