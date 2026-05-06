// Import von React Hooks:
// useState → für State-Management
// useEffect → für Lifecycle (z. B. beim Laden)
// useRef → für Referenzen auf DOM-Elemente
import { useEffect, useRef, useState } from "react";

// Import der CSS-Datei für Styling des Dropdowns
import "./../styles/ProjectTable.css";

// Import von Toast für Benachrichtigungen (Success/Error)
import { toast } from "react-toastify";

// Hauptkomponente für das Projekt-Dropdown
export default function ProjectTable({ onChange, onConfirm }) {

    // State für den eingegebenen Projektnamen (Input-Feld)
    const [ProjectName, setProjectName] = useState("");

    // State für das ausgewählte Projekt-Objekt
    const [selectedOption, setSelectedOption] = useState(null);

    // State für alle geladenen Projekte (Dropdown-Liste)
    const [options, setOptions] = useState([]);

    // State, ob das Dropdown geöffnet ist
    const [isOpen, setIsOpen] = useState(false);

    // Referenz auf das gesamte Dropdown (für Outside-Click-Erkennung)
    const containerRef = useRef(null);

    // Funktion zum Laden der Projekte vom Backend
    async function fetchProjects() {
        try {
            // API-Request an Backend
            const res = await fetch("http://localhost:9999/api/projects");

            // JSON-Antwort parsen
            const data = await res.json();

            // Daten in gewünschtes Format umwandeln
            const formatted = data.map(p => ({
                id: p.id,           // eindeutige ID
                name: p.name,       // Projektname
                room: "-",          // aktuell statisch (könnte erweitert werden)
                person: p.creator,  // Ersteller
                path: p.path,       // Speicherpfad
                available: p.available // Verfügbarkeit
            }));

            // Optionen im State speichern
            setOptions(formatted);

        } catch (err) {
            // Fehlerhandling bei Netzwerk/API-Problemen
            console.error("🔥 Fehler beim Laden der Projekte:", err);
            toast.error("Fehler beim Laden der Projekte ❌");
        }
    }

    // useEffect wird einmal beim Mounten der Komponente ausgeführt
    useEffect(() => {
        fetchProjects();
    }, []);

    // Funktion zum Erstellen eines neuen Projektverzeichnisses
    async function createDirectory(name) {
        try {
            // FormData erstellen (für POST-Request)
            const formData = new FormData();
            formData.append("projektverzeichnis", name);

            // Anfrage an Backend senden
            const response = await fetch("http://localhost:9999/vz_anlegen", {
                method: "POST",
                body: formData
            });

            // Antwort parsen
            const data = await response.json();

            if (data.success) {
                // Erfolgsmeldung anzeigen
                toast.success("Projekt erfolgreich erstellt ✅");

                // Projektliste neu laden
                await fetchProjects();
                return true;

            } else {
                // Fehler vom Backend anzeigen
                toast.error(data.message || "Fehler ❌");
                return false;
            }

        } catch (err) {
            // Fehler bei Netzwerk/JS
            console.error("🔥 Netzwerk/JS Fehler:", err);
            toast.error("Netzwerkfehler ❌");
            return false;
        }
    }

    // useEffect für Klick außerhalb des Dropdowns
    useEffect(() => {

        function handleClickOutside(e) {
            // Wenn Klick NICHT innerhalb des Dropdowns → schließen
            if (containerRef.current && !containerRef.current.contains(e.target)) {
                setIsOpen(false);
            }
        }

        // Event Listener hinzufügen
        document.addEventListener("mousedown", handleClickOutside);

        // Cleanup beim Unmount
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    // Filter + Sortierung der Optionen
    const filteredOptions = options

        // Filter nach Suchtext
        .filter(opt => {
            const search = ProjectName.toLowerCase();

            // Prüft Name, Person oder Raum
            return [opt.name, opt.person, opt.room]
                .some(value =>
                    String(value).toLowerCase().includes(search)
                );
        })

        // Sortierung:
        // 1. Verfügbare Projekte zuerst
        // 2. Alphabetisch nach Name
        .sort((a, b) => {
            if (a.available !== b.available) {
                return b.available - a.available;
            }
            return a.name.localeCompare(b.name);
        });

    // JSX Rendering
    return (
        <div className="project-dropdown" ref={containerRef}>
            <h2> Projekte </h2>

            {/* Eingabefeld für Projektauswahl */}
            <input
                type="text"
                placeholder="Select or type project..."
                value={ProjectName}

                // Öffnet Dropdown beim Fokus
                onFocus={() => setIsOpen(true)}

                // Aktualisiert State bei Eingabe
                onChange={(e) => {
                    const val = e.target.value;

                    setProjectName(val);       // Text setzen
                    setSelectedOption(null);  // Auswahl zurücksetzen
                    setIsOpen(true);          // Dropdown öffnen

                    // Callback nach außen (optional)
                    onChange?.({ name: val });
                }}

                className="input"
            />

            {/* Dropdown-Liste */}
            {isOpen && (
                <ul className="dropdown">

                    {/* Alle gefilterten Optionen anzeigen */}
                    {filteredOptions.map((opt) => (
                        <li
                            key={opt.id}

                            // Wenn nicht verfügbar → disabled Style
                            className={!opt.available ? "disabled" : ""}

                            onClick={() => {

                                // Klick auf nicht verfügbares Projekt blockieren
                                if (!opt.available) {
                                    toast.error("Projekt ist nicht verfügbar ❌");
                                    return;
                                }

                                // Auswahl übernehmen
                                setProjectName(opt.name);
                                setSelectedOption(opt);
                                setIsOpen(false);

                                // Callback nach außen
                                onChange?.(opt);
                            }}
                        >

                            {/* Zeilenlayout */}
                            <div className="row">
                                <div className="left">
                                    <span className="name">{opt.name}</span>
                                </div>

                                {/* Statusanzeige */}
                                <div className="status">
                                    <div
                                        className="status-dot"
                                        style={{
                                            backgroundColor: opt.available ? "green" : "red"
                                        }}
                                    />
                                    <span className="status-text">
                                        {opt.available ? "Verfügbar" : "Nicht verfügbar"}
                                    </span>
                                </div>
                            </div>
                        </li>
                    ))}
                </ul>
            )}

            {/* Weiter-Button */}
            <button
                className="continue-button"

                // Button deaktivieren wenn:
                // - kein Name eingegeben
                // - oder ausgewähltes Projekt nicht verfügbar
                disabled={
                    !ProjectName ||
                    (selectedOption && !selectedOption.available)
                }

                onClick={async () => {

                    // Finaler Wert: entweder Auswahl oder eingegebener Text
                    const finalValue = selectedOption?.name || ProjectName;

                    // Falls KEIN bestehendes Projekt gewählt → neues erstellen
                    if (!selectedOption) {
                        const success = await createDirectory(finalValue);

                        // Abbrechen bei Fehler
                        if (!success) return;
                    }

                    // Bestätigung an Parent-Komponente senden
                    onConfirm?.(selectedOption || { name: finalValue });
                }}
            >
                Weiter
            </button>
        </div>
    );
}