@echo off
call ".venv\Scripts\activate.bat"
echo.
echo YouTubeFactory Streamlit starting...
echo Same Wi-Fi mobile access: http://localhost:8501 or http://YOUR-PC-IP:8501
echo.
streamlit run "streamlit_app.py" --server.address 0.0.0.0 --server.port 8501 --server.fileWatcherType none
pause
