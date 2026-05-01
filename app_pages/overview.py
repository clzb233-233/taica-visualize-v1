import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from app_pages.utils import (
    require_data, display_tag, get_scored_questions, jump_to_student, get_ai_score
)

st.title("📊 全班概覽")

if not require_data():
    st.stop()

rubric = st.session_state.rubric
wf1: list = st.session_state.wf1
wf2: dict = st.session_state.wf2

quant = wf2.get("quantitative", {})
llm = wf2.get("llm_analysis", {})
scored_qs = get_scored_questions(rubric)

# ── Section A: Key Metrics ────────────────────────────────────────────────────
st.subheader("關鍵數字")

total_students = quant.get("total_students", len(wf1))
overall_mean = quant.get("overall_mean")

# exceptional_count from wf2 (positive); negative from students_worth_highlighting length
exceptional_count = quant.get("exceptional_count", 0)
swh = llm.get("students_worth_highlighting", {})
exceptional_neg = len(swh.get("exceptional_negative", []))

# inconsistent from consistency_stats
c_stats = quant.get("consistency_stats", {})
q4_stats = c_stats.get("Q4", {})
inconsistent_count = q4_stats.get("inconsistent", 0)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("總學生數", total_students)
c2.metric("全班平均分", f"{overall_mean:.2f}" if overall_mean else "N/A")
c3.metric("特別出色", exceptional_count)
c4.metric("特別需關注", exceptional_neg)
c5.metric("一致性問題", inconsistent_count)

st.divider()

# ── Section B: Position Distribution ─────────────────────────────────────────
st.subheader("立場分佈")

q1_dist = quant.get("Q1_distribution", {})
if q1_dist:
    labels = list(q1_dist.keys())
    values = list(q1_dist.values())
    fig_pie = go.Figure(go.Pie(
        labels=labels,
        values=values,
        textinfo="label+percent+value",
        hole=0.3,
    ))
    fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
    st.plotly_chart(fig_pie, use_container_width=True)
else:
    st.info("無立場分佈資料。")

st.divider()

# ── Section C: Score Distribution Per Question ────────────────────────────────
st.subheader("各題分數分佈")

score_stats = quant.get("score_stats", {})
bin_keys = ["9-10", "7-8", "5-6", "3-4", "0-2"]
bin_colors = ["#1a7f37", "#2ca02c", "#f1c40f", "#ff7f0e", "#d62728"]

for q in scored_qs:
    qid = q["id"]
    q_label = q["label"]
    q_stat = score_stats.get(qid, {})
    mean_score = q_stat.get("mean")

    bin_counts = [q_stat.get(k, 0) for k in bin_keys]
    if sum(bin_counts) == 0:
        continue

    fig = go.Figure()
    for count, color, blabel in zip(bin_counts, bin_colors, bin_keys):
        fig.add_trace(go.Bar(
            name=blabel,
            x=[count],
            y=[q_label],
            orientation="h",
            marker_color=color,
            text=str(count) if count > 0 else "",
            textposition="inside",
            showlegend=True,
        ))
    title = f"{q_label}"
    if mean_score:
        title += f"（平均：{mean_score:.2f}）"
    fig.update_layout(
        barmode="stack",
        title=title,
        height=100,
        margin=dict(t=30, b=0, l=0, r=10),
        xaxis=dict(title="人數"),
        yaxis=dict(visible=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

st.caption("分數色段：🌲 9-10 ｜ 🟢 7-8 ｜ 🟡 5-6 ｜ 🟠 3-4 ｜ 🔴 0-2")

st.divider()

# ── Section D: Teaching Priorities ───────────────────────────────────────────
st.subheader("教學優先事項")

priorities = llm.get("teaching_priorities", [])
if priorities:
    for item in priorities:
        priority_num = item.get("priority", "?")
        issue = item.get("issue", "")
        recommendation = item.get("recommendation", "")
        with st.expander(f"優先 {priority_num}：{issue}"):
            st.markdown(recommendation)
else:
    st.info("無教學優先事項資料。")

st.divider()

# ── Section E: Notable Students ───────────────────────────────────────────────
st.subheader("值得關注的學生")

outstanding = swh.get("exceptional_positive", swh.get("outstanding", []))
needs_attention = swh.get("exceptional_negative", swh.get("needs_attention", []))
interesting = swh.get("interesting_trajectories", swh.get("interesting_trajectory", swh.get("interesting", [])))

tab1, tab2, tab3 = st.tabs(["🌟 表現優秀", "⚠️ 需要關注", "🔍 有趣軌跡"])

def render_student_cards(students, reason_key="reason"):
    if not students:
        st.info("無資料")
        return
    for s in students:
        idx = s.get("student_index", "?")
        reason = s.get(reason_key) or s.get("reason") or s.get("concern") or s.get("note", "")
        with st.container(border=True):
            col_l, col_r = st.columns([3, 1])
            col_l.markdown(f"**#{idx}** — {reason}")
            if col_r.button("查看詳情", key=f"notable_{reason_key}_{idx}"):
                jump_to_student(idx)

with tab1:
    render_student_cards(outstanding, "reason")
with tab2:
    render_student_cards(needs_attention, "concern")
with tab3:
    render_student_cards(interesting, "note")

# ── Section F: AI Detection (hidden) ─────────────────────────────────────────
if st.session_state.show_ai_detect:
    st.divider()
    st.subheader("🔒 AI 疑似偵測統計")

    ai_stats = quant.get("ai_detection_stats", {})
    low_count = ai_stats.get("low_0to3", 0)
    mid_count = ai_stats.get("medium_4to6", 0)
    high_count = ai_stats.get("high_suspicion_7plus", 0)

    c1, c2, c3 = st.columns(3)
    c1.metric("低疑似（0-3）", low_count)
    c2.metric("無法判斷（4-6）", mid_count)
    c3.metric("高度疑似（7-10）", high_count)

    fig_ai = go.Figure(go.Bar(
        x=[low_count, mid_count, high_count],
        y=["低疑似", "無法判斷", "高度疑似"],
        orientation="h",
        marker_color=["#2ca02c", "#f1c40f", "#d62728"],
    ))
    fig_ai.update_layout(height=150, margin=dict(t=0, b=0, l=0, r=0))
    st.plotly_chart(fig_ai, use_container_width=True)

    ai_summary = llm.get("ai_detection_summary", {})
    pattern_text = ai_summary.get("high_suspicion_pattern", "")
    if pattern_text:
        st.markdown(f"**LLM 摘要：** {pattern_text}")

    notable_cases = ai_summary.get("notable_cases", [])
    if notable_cases:
        st.markdown("**值得注意的案例：**")
        cases_df = pd.DataFrame(notable_cases)
        if "student_index" in cases_df.columns:
            cases_df["student_index"] = cases_df["student_index"].apply(lambda x: f"#{x}")
        st.dataframe(cases_df, use_container_width=True, hide_index=True)
