@echo off
set /p MASTER_IP="Geben Sie die IP des Masters ein (Standard: 10.1.0.101): " || set MASTER_IP=10.1.0.101

echo === NTP Client Konfiguration (Master: %MASTER_IP%) ===

:: 1. Dienst starten
echo Starte Zeitdienst...
net start w32time 2>nul

:: 2. Master-Server und Synchronisations-Modus festlegen
:: 0x8 bedeutet: Sendet Anfragen in den vom Server empfohlenen Intervallen
echo Setze Master-IP und Sync-Flags...
w32tm /config /manualpeerlist:"%MASTER_IP%,0x8" /syncfromflags:MANUAL /update

:: 3. Dienst neu starten
echo Starte Dienst neu...
net stop w32time
net start w32time

:: 4. Sofortige Synchronisation erzwingen
echo Erzwinger Resync...
w32tm /resync

:: 5. Testlauf (Offset-Prüfung)
echo.
echo Teste Verbindung zu %MASTER_IP% (5 Samples)...
w32tm /stripchart /computer:%MASTER_IP% /samples:5 /dataonly

echo.
echo Client-Setup abgeschlossen.
pause