setlocal

@echo off
cd install_data

echo Extracting files...
IF NOT EXIST "httpGUI" 7za x -aoa httpGUI_archive.7z -ppassword
IF NOT EXIST "python/python.exe" 7za x -aoa python_archive.7z -ppassword

:: Print whether the user already has python installed on path
where python >nul 2>&1
if errorlevel 1 (
    echo INFORMATION: No Python found on path
) else (
    echo WARNING: An existing Python was found on path
)

:: Running with -E disables checking of environment variables for python libs
:: This should prevent conflicts with any Python dists already on the user's computer.
echo INFORMATION: Using bundled Python to run installer
"python/python.exe" -E main.py

echo ----------------------------------------------------------- 
echo ------------ Batch file has finished executing ------------
echo ------------ Press any key to close this window -----------  
echo ----------------------------------------------------------- 
pause
