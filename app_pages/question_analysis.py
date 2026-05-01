import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from app_pages.utils import (
    require_data, display_tag, get_scored_questions, jump_to_student,
    get_student_eval, get_student_tags, get_student_score
)

st.title("📝 逐題分析")

if not require_data():
    st.stop()

rubric = st.session_state.rubric
wf1: list = st.session_state.wf1
wf2: dict = st.session_state.wf2
wf1_by_index: dict = st.session_state.wf1_by_index

quant = wf2.get("quantitative", {})
llm = wf2.get("llm_analysis", {})
per_q_patterns = llm.get("per_question_patterns", {})
score_stats = quant.get("score_stats", {})
scored_qs = get_scored_questions(rubric)

if not scored_qs:
    st.info("無評分題資料。")
    st.stop()

# ── Question Selector ─────────────────────────────────────────────────────────
q_options = {q["label"]: q for q in scored_qs}
selected_label = st.selectbox("選擇題目", list(q_options.keys()))
selected_q = q_options[selected_label]
qid = selected_q["id"]

st.divider()

# ── Section A: Score Distribution ────────────────────────────────────────────
st.subheader(f"分數分佈 — {selected_label}")

q_stat = score_stats.get(qid, {})
bin_keys = ["9-10", "7-8", "5-6", "3-4", "0-2"]
bin_colors_bar = ["#1a7f37", "#2ca02c", "#f1c40f", "#ff7f0e", "#d62728"]
bin_counts = [q_stat.get(k, 0) for k in bin_keys]
mean_score = q_stat.get("mean")

if sum(bin_counts) > 0:
    fig = go.Figure()
    for count, color, blabel in zip(bin_counts, bin_colors_bar, bin_keys):
        fig.add_trace(go.Bar(
            name=blabel,
            x=[blabel],
            y=[count],
            marker_color=color,
            text=[str(count)],
            textposition="inside",
        ))
    title = f"平均分：{mean_score:.2f}" if mean_score else ""
    fig.update_layout(
        barmode="group",
        title=title,
        height=300,
        margin=dict(t=30, b=0, l=0, r=0),
        yaxis_title="人數",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("無分數統計資料（wf2 score_stats 中無此題）。")

st.divider()

# ── Section B: Common Errors ──────────────────────────────────────────────────
st.subheader("最常見錯誤")

q_pattern = per_q_patterns.get(qid, {})
if not q_pattern:
    st.info("LLM 分析未生成（此題無 per_question_patterns 資料）。")
else:
    common_errors = q_pattern.get("most_common_errors", [])
    rare_errors = q_pattern.get("rare_but_notable_errors", [])
    csv_df = st.session_state.get("csv_df")

    if common_errors:
        for err in common_errors:
            tag = err.get("tag", "")
            tag_cn = display_tag(tag)
            count = err.get("count", err.get("frequency", "?"))
            impact = err.get("impact", "中")
            desc = err.get("description", "")
            teaching_fix = err.get("teaching_fix", "")
            example_indices = err.get("example_indices", [])
            impact_color = {"高": "red", "中": "orange", "低": "blue"}.get(str(impact), "gray")

            with st.container(border=True):
                h1, h2 = st.columns([4, 1])
                h1.markdown(
                    f"**{tag_cn}** <span style='color:gray;font-size:0.85em'>({tag})</span>",
                    unsafe_allow_html=True
                )
                h2.markdown(f":{impact_color}[影響：{impact}] · {count} 人")
                if desc:
                    st.markdown(f"📋 {desc}")
                if teaching_fix:
                    st.markdown(f"💡 **教學建議：** {teaching_fix}")
                if example_indices:
                    with st.expander("查看範例學生"):
                        for idx in example_indices[:5]:
                            student = wf1_by_index.get(idx, {})
                            ev = get_student_eval(student, qid)
                            comment = ev.get("comment", "無評語")
                            st.markdown(f"**#{idx}：** {comment}")
                            if st.button("查看完整詳情", key=f"err_jump_{qid}_{idx}_{tag}"):
                                jump_to_student(idx)
    else:
        st.info("無常見錯誤資料。")

    if rare_errors:
        with st.expander("罕見但值得注意的錯誤"):
            for err in rare_errors:
                tag = err.get("tag", "")
                tag_cn = display_tag(tag)
                desc = err.get("description", "")
                count = err.get("count", err.get("frequency", "?"))
                example_indices = err.get("example_indices", [])
                with st.container(border=True):
                    st.markdown(
                        f"**{tag_cn}** <span style='color:gray;font-size:0.85em'>({tag})</span> · {count} 人",
                        unsafe_allow_html=True
                    )
                    if desc:
                        st.markdown(desc)
                    if example_indices:
                        with st.expander("查看範例"):
                            for idx in example_indices[:3]:
                                student = wf1_by_index.get(idx, {})
                                ev = get_student_eval(student, qid)
                                st.markdown(f"**#{idx}：** {ev.get('comment', '無評語')}")

st.divider()

# ── Section C: Common Strengths ───────────────────────────────────────────────
st.subheader("最常見優點")

if q_pattern:
    strengths = q_pattern.get("most_common_strengths", [])
    if strengths:
        for strength in strengths:
            tag = strength.get("tag", "")
            tag_cn = display_tag(tag)
            count = strength.get("count", strength.get("frequency", "?"))
            desc = strength.get("description", "")
            best_examples = strength.get("best_examples", [])

            with st.container(border=True):
                h1, h2 = st.columns([4, 1])
                h1.markdown(
                    f"**{tag_cn}** <span style='color:gray;font-size:0.85em'>({tag})</span>",
                    unsafe_allow_html=True
                )
                h2.markdown(f":green[✓] {count} 人")
                if desc:
                    st.markdown(f"📋 {desc}")
                if best_examples:
                    with st.expander("最佳範例"):
                        for idx in best_examples[:5]:
                            student = wf1_by_index.get(idx, {})
                            ev = get_student_eval(student, qid)
                            comment = ev.get("comment", "無評語")
                            st.markdown(f"**#{idx}：** {comment}")
                            if st.button("查看完整詳情", key=f"str_jump_{qid}_{idx}_{tag}"):
                                jump_to_student(idx)
    else:
        st.info("無優點資料。")

st.divider()

# ── Section D: Argument Type Distribution ────────────────────────────────────
st.subheader("論證類型分佈")

type_freq = quant.get("type_frequency", {}).get(qid, {})
type_insight = q_pattern.get("type_distribution_insight", "") if q_pattern else ""

if type_freq:
    type_labels = [display_tag(t) for t in type_freq.keys()]
    type_values = list(type_freq.values())
    fig_type = go.Figure(go.Pie(
        labels=type_labels,
        values=type_values,
        textinfo="label+percent+value",
        hole=0.3,
    ))
    fig_type.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
    st.plotly_chart(fig_type, use_container_width=True)
    if type_insight:
        st.markdown(f"**LLM 分析：** {type_insight}")
else:
    st.info("無論證類型資料。")

st.divider()

# ── Section E: Best Responses ─────────────────────────────────────────────────
st.subheader("最值得課堂引用的回答")

if q_pattern:
    insightful = q_pattern.get("most_insightful_responses", [])
    best_overall = q_pattern.get("best_overall_responses", [])
    csv_df = st.session_state.get("csv_df")

    tab1, tab2 = st.tabs(["💡 最有洞見", "🏆 最佳整體"])

    def render_response_cards(responses, tab_key):
        if not responses:
            st.info("無資料")
            return
        for resp in responses:
            idx = resp.get("student_index", "?")
            reason = resp.get("reason", resp.get("note", ""))
            student = wf1_by_index.get(idx, {})
            ev = get_student_eval(student, qid)
            comment = ev.get("comment", "")
            with st.expander(f"#{idx} — {reason}"):
                if comment:
                    st.markdown(f"**分析評語：** {comment}")
                if csv_df is None:
                    st.caption("（未上傳填答紀錄，無法顯示原始回答）")
                if st.button("查看完整學生詳情", key=f"best_{tab_key}_{qid}_{idx}"):
                    jump_to_student(idx)

    with tab1:
        render_response_cards(insightful, "insightful")
    with tab2:
        render_response_cards(best_overall, "best")

st.divider()
st.divider()

# ── Section F: Cross Analysis ─────────────────────────────────────────────────
st.subheader("全班交叉分析")

cross = llm.get("cross_analysis", {})
if cross:
    pos_vs_quality = cross.get("position_vs_quality", "")
    consistency = cross.get("consistency_analysis", "")
    high_profile = cross.get("high_scorer_profile", "")
    low_profile = cross.get("low_scorer_profile", "")

    if pos_vs_quality:
        st.markdown("**立場 vs. 分數：**")
        st.markdown(pos_vs_quality)
    if consistency:
        st.markdown("**一致性分析：**")
        st.markdown(consistency)
    if high_profile or low_profile:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**高分群畫像：**")
            st.markdown(high_profile or "—")
        with c2:
            st.markdown("**低分群畫像：**")
            st.markdown(low_profile or "—")
else:
    st.info("無交叉分析資料。")

st.divider()

# ── Section G: Confusion Analysis ────────────────────────────────────────────
st.subheader("困惑點分析")

confusion = llm.get("confusion_analysis", {})
if confusion:
    # support both "major_themes" and "themes" keys
    themes = confusion.get("major_themes", confusion.get("themes", confusion.get("confusion_themes", [])))
    deepest = confusion.get("deepest_confusions", [])

    if themes:
        st.markdown("**主題清單：**")
        for theme in themes:
            name = theme.get("theme", theme.get("name", ""))
            count = theme.get("count", "?")
            core_q = theme.get("core_question", "")
            teaching_suggestion = theme.get("teaching_suggestion", theme.get("recommendation", ""))
            with st.container(border=True):
                st.markdown(f"**{name}** — {count} 人")
                if core_q:
                    st.markdown(f"核心問題：{core_q}")
                if teaching_suggestion:
                    st.markdown(f"💡 教學建議：{teaching_suggestion}")

    if deepest:
        st.markdown("**最深層困惑的學生：**")
        for item in deepest:
            idx = item.get("student_index", "?")
            content = item.get("confusion", item.get("content", ""))
            with st.expander(f"#{idx}"):
                st.markdown(content)
                if st.button("查看學生詳情", key=f"conf_{qid}_{idx}"):
                    jump_to_student(idx)
else:
    st.info("無困惑點分析資料。")
