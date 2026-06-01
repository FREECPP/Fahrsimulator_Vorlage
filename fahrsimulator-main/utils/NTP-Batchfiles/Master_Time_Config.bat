@echo off
echo === NTP Master Konfiguration ===

:: 1. Dienst starten
echo Starte Zeitdienst...
net start w32time 2>nul

:: 2. Rechner als NTP-Server aktivieren
echo Aktiviere NTP-Server in der Registry...
reg add "HKLM\SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\NtpServer" /v "Enabled" /t REG_DWORD /d 1 /f

:: 3. AnnounceFlags auf 5 setzen (Verlässliche Zeitquelle)
echo Setze AnnounceFlags auf 5...
reg add "HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Config" /v "AnnounceFlags" /t REG_DWORD /d 5 /f

:: 4. Dienst neu starten um Änderungen zu übernehmen
echo Starte Dienst neu...
net stop w32time
net start w32time

:: 5. Status abfragen
echo.
echo Konfiguration abgeschlossen. Aktueller Status:
w32tm /query /configuration
w32tm /query /status

pause