import {useEffect, useRef, useState} from "react";
import "./../styles/ProjectTable.css";
import {toast} from "react-toastify";

export default function ProjectTable({onChange, onConfirm}) {

    const [ProjectName, setProjectName] = useState("");
    const [selectedOption, setSelectedOption] = useState(null);
    const [options, setOptions] = useState([]);
    const [isOpen, setIsOpen] = useState(false);

    const containerRef = useRef(null);

    // -------------------------------
    // Projekte laden
    // -------------------------------
    async function fetchProjects() {
        try {
            const res = await fetch("http://localhost:9999/api/projects");
            const data = await res.json();

            const formatted = data.map(p => ({
                id: p.id,
                name: p.name,
                room: "-",
                person: p.creator,
                path: p.path,
                available: p.available
            }));

            setOptions(formatted);

        } catch (err) {
            console.error("🔥 Fehler beim Laden der Projekte:", err);
            toast.error("Fehler beim Laden der Projekte ❌");
        }
    }

    useEffect(() => {
        fetchProjects();
    }, []);

    // -------------------------------
    // Projekt erstellen (FIXED)
    // -------------------------------
    async function createDirectory(name) {
        try {
            const formData = new FormData();
            formData.append("projektverzeichnis", name);
            formData.append("creator", "User");
            const response = await fetch("http://localhost:9999/vz_anlegen", {
                method: "POST",
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                toast.success("Projekt erfolgreich erstellt");

                await fetchProjects();

                // 🔥 WICHTIG: echtes Projekt zurückgeben
                return data.project;
            }

            toast.error(data.message || "Fehler ❌");
            return null;

        } catch (err) {
            console.error("🔥 Netzwerk/JS Fehler:", err);
            toast.error("Netzwerkfehler ❌");
            return null;
        }
    }

    // -------------------------------
    // Outside Click
    // -------------------------------
    useEffect(() => {
        function handleClickOutside(e) {
            if (containerRef.current && !containerRef.current.contains(e.target)) {
                setIsOpen(false);
            }
        }

        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    // -------------------------------
    // Filter + Sort
    // -------------------------------
    const filteredOptions = options
        .filter(opt => {
            const search = ProjectName.toLowerCase();
            return [opt.name, opt.person, opt.room]
                .some(value => String(value).toLowerCase().includes(search));
        })
        .sort((a, b) => {
            if (a.available !== b.available) {
                return b.available - a.available;
            }
            return a.name.localeCompare(b.name);
        });

    // -------------------------------
    // Render
    // -------------------------------
    return (
        <div className="project-dropdown" ref={containerRef}>
            <h2> Projekte </h2>

            <input
                type="text"
                placeholder="Wählen oder erstellen Sie ein Projekt..."
                value={ProjectName}
                onFocus={() => setIsOpen(true)}
                onChange={(e) => {
                    const val = e.target.value;

                    setProjectName(val);
                    setSelectedOption(null);
                    setIsOpen(true);

                    onChange?.({name: val});
                }}
                className="input"
            />

            {isOpen && (
                <ul className="dropdown">
                    {filteredOptions.map((opt) => (
                        <li
                            key={opt.id}
                            className={!opt.available ? "disabled" : ""}
                            onClick={() => {
                                if (!opt.available) {
                                    toast.error("Projekt ist nicht verfügbar ❌");
                                    return;
                                }

                                setProjectName(opt.name);
                                setSelectedOption(opt);
                                setIsOpen(false);

                                onChange?.(opt);
                            }}
                        >
                            <div className="row">
                                <div className="left">
                                    <span className="name">{opt.name}</span>
                                </div>

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

            <button
                className="continue-button"
                disabled={
                    !ProjectName ||
                    (selectedOption && !selectedOption.available)
                }
                onClick={async () => {

                    const finalValue = selectedOption?.name || ProjectName;
                    let projectToConfirm = selectedOption;

                    // 🔥 FIX: neues Projekt korrekt behandeln
                    if (!selectedOption) {
                        const newProject = await createDirectory(finalValue);

                        if (!newProject) return;

                        projectToConfirm = {
                            id: newProject.id,
                            name: newProject.name,
                            path: newProject.path,
                            creator: newProject.creator,
                            available: newProject.available
                        };
                    }

                    console.log("✅ CONFIRM PROJECT:", projectToConfirm);

                    // 🔥 IMMER mit ID
                    onConfirm?.(projectToConfirm);
                }}
            >
                Weiter
            </button>
        </div>
    );
}