@echo off
cd install_data
IF NOT EXIST "python/python.exe" 7za x -aoa python_archive.7z
aria2c --allow-overwrite=true --auto-file-renaming=false https://raw.githubusercontent.com/07th-mod/python-patcher/master/scriptDownloadList.txt
aria2c --allow-overwrite=true --auto-file-renaming=false --input-file=scriptDownloadList.txt
"python/python.exe" main.py

echo ----------------------------------------------------------- 
echo ------------ Batch file has finished executing ------------
echo ------------ Press any key to close this window -----------  
echo ----------------------------------------------------------- 
pause