@echo off
rem Drop a montage .mp4 onto this file (or onto its desktop shortcut). Double-click opens the window.
cd /d "%~dp0"
where pythonw >nul 2>nul && (start "" pythonw "%~dp0app.py" %*) || (python "%~dp0app.py" %*)
