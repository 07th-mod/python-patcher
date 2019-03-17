@echo off
cd install_data
IF NOT EXIST "python/python.exe" 7za x -aoa python_archive.7z
"python/python.exe" main.py

echo ----------------------------------------------------------- 
echo ------------ Batch file has finished executing ------------
echo ------------ Press any key to close this window -----------  
echo ----------------------------------------------------------- 
pause