"""Shared utility functions for the classroom analysis viz tool."""
import streamlit as st


def require_data() -> bool:
    rubric = st.session_state.get("rubric")
    wf1 = st.session_state.get("wf1")
    wf2 = st.session_state.get("wf2")
    if rubric is None or wf1 is None or wf2 is None:
        st.info("📂 請先至「載入資料」頁面上傳所需的 JSON 檔案。")
        if st.button("前往載入資料"):
            st.switch_page("app_pages/load_data.py")
        return False
    return True


def display_tag(tag: str) -> str:
    tag_display = st.session_state.get("tag_display", {})
    return tag_display.get(tag, tag)


def get_scored_questions(rubric: dict) -> list:
    """Return scored question list from rubric['rubrics']."""
    rubrics = rubric.get("rubrics", {})
    result = []
    for qid, data in rubrics.items():
        result.append({
            "id": qid,
            "label": qid,
            "type": "scored",
            "scoring_criteria": data.get("scoring_criteria", {}),
            "format_checklist": data.get("format_checklist", []),
        })
    result.sort(key=lambda q: int(q["id"][1:]) if q["id"][1:].isdigit() else 99)
    return result


def get_all_questions(rubric: dict, wf1_record: dict = None) -> list:
    """Return all question dicts inferred from rubric + optional wf1 record."""
    scored_ids = set(rubric.get("rubrics", {}).keys())

    # Infer q-ids from wf1 record
    all_q_ids = set()
    if wf1_record:
        for key in wf1_record.keys():
            for suffix in ("_eval", "_position", "_consistency", "_tags"):
                if key.endswith(suffix):
                    qid = key[:-(len(suffix))]
                    if qid.startswith("Q") and qid[1:].isdigit():
                        all_q_ids.add(qid)
    if not all_q_ids:
        all_q_ids = {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"}

    rubrics = rubric.get("rubrics", {})
    result = []
    for qid in sorted(all_q_ids, key=lambda x: int(x[1:])):
        if qid in scored_ids:
            q_type = "scored"
        elif qid == "Q4":
            q_type = "consistency"
        elif qid == "Q1":
            q_type = "mc"
        else:
            q_type = "collect"
        rubric_data = rubrics.get(qid, {})
        result.append({
            "id": qid,
            "label": qid,
            "type": q_type,
            "scoring_criteria": rubric_data.get("scoring_criteria", {}),
            "format_checklist": rubric_data.get("format_checklist", []),
        })
    return result


def get_student_eval(record: dict, qid: str) -> dict:
    return record.get(f"{qid}_eval", {})


def get_student_tags(record: dict, qid: str) -> dict:
    return record.get(f"{qid}_tags", {})


def get_student_score(record: dict, qid: str):
    ev = get_student_eval(record, qid)
    sc = ev.get("score")
    return float(sc) if sc is not None else None


def get_ai_score(record: dict):
    ai = record.get("ai_detection", {})
    v = ai.get("score", ai.get("ai_score"))
    return int(v) if v is not None else None


def jump_to_student(student_index: int):
    st.session_state["jump_to_student"] = student_index
    st.switch_page("app_pages/student_detail.py")
