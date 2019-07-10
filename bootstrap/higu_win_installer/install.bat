@echo off
cd install_data
where python >nul 2>&1
if errorlevel 1 (
    IF NOT EXIST "python/python.exe" 7za x -aoa python_archive.7z
    echo Using bundled Python
    "python/python.exe" main.py
) else (
    echo Python found on path - using system Python
    python main.py
)

echo ----------------------------------------------------------- 
echo ------------ Batch file has finished executing ------------
echo ------------ Press any key to close this window -----------  
echo ----------------------------------------------------------- 
pause