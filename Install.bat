@echo off
cd /d "%~dp0"
echo Installing the Python packages for Montage Uploader...
python -m pip install --user -r requirements.txt
echo.
python app.py --check
echo.
pause
