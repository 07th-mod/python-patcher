@echo off
IF NOT EXIST "python/python.exe" 7za x -aoa python_archive.7z
aria2c --allow-overwrite=true --auto-file-renaming=false https://github.com/07th-mod/resources/raw/master/higurashiInstaller.py
"python/python.exe" higurashiInstaller.py
echo ----------------------------------------------------------- 
echo ------------ Batch file has finished executing ------------
echo ------------ Press any key to close this window -----------  
echo ----------------------------------------------------------- 
pause