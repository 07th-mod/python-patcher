@echo off
cd install_data

echo Extracting web files
7za x -aoa httpGUI_archive.7z -ppassword

where python >nul 2>&1
if errorlevel 1 (
    IF NOT EXIST "python/python.exe" 7za x -aoa python_archive.7z -ppassword
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
