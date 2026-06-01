Das NTP-Protokoll(Network Time Protocool) synchronisiert die Uhrzeit von Computern über Netzwerke. Der Hintergrund des Einsatztes beim Fahrsimuolator, ist es eine allgemeine Zeitbasis zu schaffen, auf Grundlage welcher die einzelnen Sensoren Logs erstellen können. 
Aktuell sind alle Sensoren an einem Gerät angeschlossen. Für die Zukunft soll ermöglicht werden Sensoren auch über andere Geräte anzuschließen damit diese externen Geräte teil der gemeinsamen Zeitbasis werden. 
Das NTP-Protokoll ist ein Client-Server-Protokoll. Das bedeutet, das es einen oder mehrere Zeitserver gibt, welche Zeitanfragen der Clients bearbeiten. Gleichzeitig wird dabei bereits die Latenz herausgerechnet. Ein Client kann sich nun auch mit mehreren Zeitservern verbinden, über Mehrheitsentscheid kann er dann fehlerhafte Zeitserver finden und ignorieren. 
Da der Fahrsimulator keine Verbindung zum Internet erlaubt, können die Rechner nicht auf öffentliche Zeitserver zugreifen. NTP bietet jedoch die Möglichkeit 

Master_Time_Config.bat :

Dieses Batch-Skript konfiguriert das lokale Windows-System so, dass es als autoritativer NTP-Server (Master) im Netzwerk fungiert. Andere Clients können sich danach die Uhrzeit von diesem Rechner holen.

Das Skript führt generell 5 Schritte aus: 
1. Dienst-Aktivierung (net start) Der Windows-Zeitdienst (w32time) wird gestartet, falls er gestoppt war. Fehlermeldungen (z. B. wenn der Dienst bereits läuft) werden via 2>nul unterdrückt.

2. Server-Rolle aktivieren (NtpServer\Enabled = 1) In der Windows-Registry wird der integrierte NTP-Server-Provider eingeschaltet. Ohne diesen Schritt akzeptiert Windows keine eingehenden Zeitabfragen von außen.

3. Status als verlässliche Quelle setzen (AnnounceFlags = 5) Dies ist der wichtigste Schritt für einen autarken Master-Server. Das Flag 5 (Kombination aus 0x01 und 0x04) zwingt Windows dazu, sich selbst als verlässliche Zeitquelle (Reliable Time Source) zu deklarieren – und zwar unabhängig davon, ob dieser Rechner selbst Zugang zu einem übergeordneten Internet-Zeitserver hat.(In unserem Fall haben wir keinen Zugang zu einem übergeordneten Zeitserver)

4. Konfigurations-Reload (net stop / net start) Der Zeitdienst liest seine Registry-Werte nur beim Starten ein. Ein Neustart des Dienstes erzwingt die Übernahme der neuen Parameter.

5. Validierung (w32tm /query) Gibt die aktuelle Konfiguration und den Synchronisationsstatus direkt im Terminal aus, um die erfolgreiche Umsetzung zu prüfen.



Systemvoraussetzungen: 


1. Administratorrechte zwingend erforderlich: Befehle wie net start und Änderungen an HKLM (HKEY_LOCAL_MACHINE) schlagen ohne explizite Administratorrechte fehl. Das Skript sollte in der Doku mit dem Hinweis "Rechtsklick -> Als Administrator ausführen" versehen werden.

2. Windows-Firewall: Das Skript öffnet nicht automatisch den benötigten Netzwerkport. Wenn Clients keine Verbindung herstellen können, muss der UDP-Port 123 in der Windows-Firewall für eingehende Verbindungen freigegeben werden:

Client_Time_Config.bat : 

Dieses Batch-Skript konfiguriert ein Windows-System als NTP-Client, der seine Systemzeit aktiv von einem definierten Master-Server im Netzwerk bezieht und sich mit diesem synchronisiert.

Eingabe-Abfrage: Das Skript bittet den Nutzer um die IP-Adresse des Masters. Drückt der Nutzer einfach Enter, greift ein Fallback (|| set MASTER_IP=...) und setzt automatisch die Standard-IP 10.1.0.101.

Schritte: 
1. Dienst-Aktivierung (net start) Der Windows-Zeitdienst (w32time) wird gestartet, falls er inaktiv war. Fehlermeldungen werden via 2>nul unterdrückt.

2. Zielserver & Modus definieren (w32tm /config) Der Befehl verknüpft den Client mit der eingegebenen IP.
	- /syncfromflags:MANUAL zwingt den Client, ausschließlich die manuell angegebene IP-Liste zu nutzen (und nicht z. B. die Active-Directory-Domäne)
	- Das Flag ,0x8 (NTP_Attribute_SpecialInterval) sorgt dafür, dass der Client die Abfrageintervalle nutzt, die der NTP-Server in seinen Antworten vorschlägt
	- /update signalisiert dem Dienst, dass sich die Konfiguration geändert hat

3. Dienst-Neustart (net stop / net start) Erzwingt das Einlesen der neuen Konfigurationsparameter aus der Registry

4. Sofortige Synchronisation (w32tm /resync) Windows-Clients synchronisieren sich normalerweise nur in großen Abständen. Dieser Befehl bricht das Wartemuster auf und erzwingt augenblicklich den Abgleich mit dem Master

5. Verbindungstest (w32tm /stripchart) Sendet 5 Test-Abfragen an den Master. In der Konsole wird die Zeitdifferenz (Offset) zwischen Client und Master live angezeigt. Das dient als direkter Funktionsbeweis


Systemvoraussetzungen: 

Administratorrechte: Wie beim Master gilt: Ohne "Als Administrator ausführen" schlägt das Skript fehl.

Fehlermeldung bei /resync: Wenn Schritt 4 meldet: "Der Computer wurde nicht synchronisiert, da keine Zeitdaten verfügbar waren", liegt das meistens daran, dass:

    Der Master-Server noch nicht bereit ist (oder dessen Dienst nicht läuft).

    Die Firewall auf dem Master oder Client den UDP-Port 123 blockiert.

