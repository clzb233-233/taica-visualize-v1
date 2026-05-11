import json
import io
import os
import pandas as pd
import streamlit as st


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
