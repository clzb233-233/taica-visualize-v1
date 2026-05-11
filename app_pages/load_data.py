import json
import io
import os
import pandas as pd
import pathlib
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
    base_dir = pathlib.Path(__file__).parent.parent   # app_pages/ 的上一層 = repo 根目錄
    base_path = next(base_dir.glob("W*/"), None)      # 自動找 W* 資料夾，不 hardcode "W11"
    if base_path is None:
        return None, None, None, None, {}, None
