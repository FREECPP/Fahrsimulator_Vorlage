@echo off
cd /d "%~dp0"
:: ALT cd "C:\PycharmProjects\Fahrsimulator"
:: Beachte richtige venv, wenn venv genutzt wird!
:: CALL .venv1\Scripts\activate
:: Starte Standard Browser
::start http://127.0.0.1:9999
start http://localhost:4173/
:: Starte Applikation
start cmd /c "python3.10 flask_app.py"
cd react_app
call npm run build
call npm run preview
:: CMD Fenster geöffnet lassen
pause

:: cd ist das Projektverzeichnis
:: über die Bat-File lässt sich das programm ohne konsole starten
