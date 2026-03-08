@echo off
echo Starting Invoice Auditor Web App...
cd /d "%~dp0"
streamlit run web_app.py --server.port 8501
