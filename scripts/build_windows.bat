@echo off
setlocal
set PYTHON=python
set APPNAME=Selune
set ZIPNAME=Selune-Windows.zip

%PYTHON% -m pip install --upgrade pyinstaller || exit /b 1
%PYTHON% -m pip install --upgrade -r requirements.txt || exit /b 1

%PYTHON% -m PyInstaller --clean --noconfirm spec/Selune-windows.spec

if exist "%ZIPNAME%" del "%ZIPNAME%"
powershell -NoProfile -Command "Compress-Archive -Path \"dist\\%APPNAME%\\*\" -DestinationPath \"%ZIPNAME%\""
echo Created %ZIPNAME%
endlocal
