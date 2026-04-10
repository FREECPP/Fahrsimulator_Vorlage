@echo off
cd /d "%~dp0"
:: ALT cd "C:\PycharmProjects\Fahrsimulator"
:: Beachte richtige venv, wenn venv genutzt wird!
:: CALL .venv1\Scripts\activate
set PORT=9999
:: Starte Standard Browser
start http://127.0.0.1:%PORT%
:: Starte Applikation
python3.10 flask_app.py
:: CMD Fenster geöffnet lassen
pause

:: cd ist das Projektverzeichnis
:: über die Bat-File lässt sich das programm ohne konsole starten
