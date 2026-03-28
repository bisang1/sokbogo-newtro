@echo off
call ".venv\Scripts\activate.bat"
streamlit run "sokbogo-newtro\streamlit_app.py" --server.fileWatcherType none
pause