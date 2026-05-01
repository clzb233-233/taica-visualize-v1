# 課堂分析視覺化工具

## 安裝

```bash
uv venv
uv pip install "streamlit>=1.45.0" plotly pandas
```

## 啟動

```bash
.venv/bin/streamlit run streamlit_app.py
```

## 檔案結構

```
streamlit_app.py          # 入口，導覽設定
app_pages/
    load_data.py          # 載入資料頁
    overview.py           # 全班概覽頁
    question_analysis.py  # 逐題分析頁
    student_detail.py     # 個別學生頁
    rubric_reference.py   # 評分標準參考頁
    utils.py              # 共用工具函式
```

## 輸入檔案

| 檔案 | 必填 |
|---|---|
| `rubric.json` | ✅ |
| `wf1_results.json` | ✅ |
| `wf2_report.json` | ✅ |
| `W{N}.csv` | 選填 |
