## GUI integration

### Layout Dashboard
|            |  |  |
|------------|--------------|--------------------|
| 1 TOF Bild | 2 Silab Bild | 3 RGB Bild         |
| 4 HR/HFV   | 5 Lenkrad    | 6 Blickpunkte      |
| 7 Modell   | 8 Pedale     | 9 Km/h             |

- 1: TOF Bild mit Tiefenanzeige
- 2: Simulatorbild aus Silab
- 3: RGB Kamera Bild
- 4: Liniendiagramm für Anzeige der Herzfrequenz und/oder Herzratenvariabilität
- 5: Lenkrad Anzeige mit Balkendiagramm und Grad-Angabe
- 6: Kamera mit Blickpunktüberlagerung
- 7: Ggf live anzeige des Modells für "radikale Fahrweise" oder "Aufmerksamkeitsanalyse"
- 8: Brems- und Gaspedalanzeige mit Balkendiagramm für Pedaldruckanzeige
- 9: Liniendiagramm für Geschwindigkeitsanzeige

#### Benötigte Daten fürs Dashboard:
- HR/HRV
- Silab Bild
- RGB Kamera 0 Bild + Mediapipe
- TOF Bild + Mediapipe
- RGB Kamera 1 Bild + Blickpunktüberlagerung
- Werte Silab: 
  - m/h, 
  - Bremspedaldruck, 
  - Gaspedaldruck,
  - Lenkradrotation
- Live Modell-Analyse der Fahrweise oder Aufmerksamkeit
- Link zur Dokumentation im Footer
- 
#### Benötigte Eingabefelder:
- Stop-Button für den Simulator
- Mit ggf. Rückkehr zur Home-Seite

### Layout Home
- Dropdown Menü für Projektauswahl
- Eingabefeld für neues Projekt anlegen
- Button zur Auswahl bestätigen
- Button Simulator starten -> weiterleitung zum Dashboard
- Link zur Dokumentation im Footer

### Programm start
Programm start über Batch Datei mit der sich das Programm startet und die Website/GUI öffnet.

### Verwendete Libries
- Flask
- Flask-SocketIO
- chart.js / chart.umd.js
