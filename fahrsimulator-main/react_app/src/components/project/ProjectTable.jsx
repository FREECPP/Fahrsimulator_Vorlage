import {useEffect, useRef, useState} from "react";
import {toast} from "react-toastify";

import "../../styles/ProjectTable.css";


function validateProjectName(name) {
    const reservedNames = [
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5",
        "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5",
        "LPT6", "LPT7", "LPT8", "LPT9"
    ];

    return {
        minLength: name.length >= 4,
        noInvalidChars: !/[<>:"/\\|?*]/.test(name),
        noSpecialChars: !/[.,!#@()\[\]]/.test(name),
        noSpaces: !/\s/.test(name),
        noTrailingDotOrSpace: !/[ .]$/.test(name),
        notReserved: !reservedNames.includes(
            name.toUpperCase()
        ),
        maxLength: name.length <= 255
    };
}
export default function ProjectTable({onChange, onConfirm}) {

    const [ProjectName, setProjectName] = useState("");
    const [selectedOption, setSelectedOption] = useState(null);
    const [options, setOptions] = useState([]);
    const [isOpen, setIsOpen] = useState(false);
    const [showAll, setShowAll] = useState(false);

    const containerRef = useRef(null);


const rules = validateProjectName(ProjectName);

const isValidProjectName =
    rules.minLength &&
    rules.noInvalidChars &&
    rules.noSpecialChars &&
    rules.noSpaces &&
    rules.noTrailingDotOrSpace &&
    rules.notReserved &&
    rules.maxLength;
    // ===== Load Projects =====
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

    // ===== Create Project =====
    async function createDirectory(name) {
        try {
            const formData = new FormData();

            formData.append("projektverzeichnis", name);
            formData.append("creator", "User");

            const response = await fetch(
                "http://localhost:9999/vz_anlegen",
                {
                    method: "POST",
                    body: formData
                }
            );

            const data = await response.json();

            if (data.success) {
                toast.success("Projekt erfolgreich erstellt");

                await fetchProjects();

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

    // ===== Outside Click =====
    useEffect(() => {

        function handleClickOutside(e) {
            if (
                containerRef.current
                && !containerRef.current.contains(e.target)
            ) {
                setIsOpen(false);
            }
        }

        document.addEventListener(
            "mousedown",
            handleClickOutside
        );

        return () =>
            document.removeEventListener(
                "mousedown",
                handleClickOutside
            );

    }, []);

    // ===== Filter =====
    const filteredOptions = options
        .filter(opt => {

            if (showAll) {
                return true;
            }

            const search = ProjectName.toLowerCase();

            return [opt.name, opt.person, opt.room]
                .some(value =>
                    String(value)
                        .toLowerCase()
                        .includes(search)
                );
        })

        .sort((a, b) => {

            if (a.available !== b.available) {
                return b.available - a.available;
            }

            return a.name.localeCompare(b.name);
        });

    // ===== Render =====
// ===== Render =====
return (
    <div
        className="project-dropdown"
        ref={containerRef}
    >

        {
            ProjectName.trim().length > 0 &&
            !selectedOption && (
                <div className="validation-box floating-validation">

                    <div className={rules.minLength ? "valid" : "invalid"}>
                        {rules.minLength ? "✔" : "✖"} Mindestens 4 Zeichen
                    </div>

                    <div className={rules.maxLength ? "valid" : "invalid"}>
                        {rules.maxLength ? "✔" : "✖"} Maximal 255 Zeichen
                    </div>

                    <div className={rules.noInvalidChars ? "valid" : "invalid"}>
                        {rules.noInvalidChars ? "✔" : "✖"} Keine Zeichen: &lt; &gt; : " / \ | ? *
                    </div>

                    <div className={rules.noSpecialChars ? "valid" : "invalid"}>
                        {rules.noSpecialChars ? "✔" : "✖"} Keine Zeichen: . , ! # @ ( ) [ ]
                    </div>

                    <div className={rules.noSpaces ? "valid" : "invalid"}>
                        {rules.noSpaces ? "✔" : "✖"} Keine Leerzeichen
                    </div>

                    <div className={rules.noTrailingDotOrSpace ? "valid" : "invalid"}>
                        {rules.noTrailingDotOrSpace ? "✔" : "✖"} Nicht mit Leerzeichen oder Punkt enden
                    </div>

                    <div className={rules.notReserved ? "valid" : "invalid"}>
                        {rules.notReserved ? "✔" : "✖"} Kein reservierter Windows-Name
                    </div>

                </div>
            )
        }

        <h2>Projekte</h2>

        <div className="input-wrapper">

            <input
                type="text"
                placeholder="Wählen oder erstellen Sie ein Projekt..."
                value={ProjectName}
                className="input"

                onFocus={() => {
                    setShowAll(false);
                    setIsOpen(true);
                }}

                onChange={(e) => {
                    const val = e.target.value;

                    setShowAll(false);

                    setProjectName(val);
                    setSelectedOption(null);
                    setIsOpen(true);

                    onChange?.({name: val});
                }}
            />

            <button
                type="button"
                className="dropdown-toggle"

                onClick={() => {
                    setShowAll(true);
                    setIsOpen(true);
                }}
            >
                ▼
            </button>

        </div>

        {isOpen && (
            <ul className="dropdown">

                {filteredOptions.map((opt) => (

                    <li
                        key={opt.id}
                        className={
                            !opt.available
                                ? "disabled"
                                : ""
                        }

                        onClick={() => {

                            if (!opt.available) {
                                toast.error(
                                    "Projekt ist nicht verfügbar ❌"
                                );

                                return;
                            }

                            setProjectName(opt.name);
                            setSelectedOption(opt);
                            setIsOpen(false);

                            onChange?.(opt);
                            onConfirm?.(opt);
                        }}
                    >
                        <div className="row">

                            <div className="left">
                                <span className="name">
                                    {opt.name}
                                </span>
                            </div>

                            <div className="right-section">

                                <div className="right">
                                    <span className="projectPath">
                                        {opt.path}
                                    </span>
                                </div>

                                <div className="status">

                                    <div
                                        className="status-dot"

                                        style={{
                                            backgroundColor:
                                                opt.available
                                                    ? "green"
                                                    : "red"
                                        }}
                                    />

                                    <span className="status-text">
                                        {
                                            opt.available
                                                ? "Verfügbar"
                                                : "Nicht verfügbar"
                                        }
                                    </span>

                                </div>

                            </div>

                        </div>

                    </li>

                ))}

            </ul>
        )}

        <button
            className="continue-button"

            disabled={
                !ProjectName
                || (
                    !selectedOption &&
                    !isValidProjectName
                )
                || (
                    selectedOption &&
                    !selectedOption.available
                )
            }

            onClick={async () => {

                const finalValue =
                    selectedOption?.name
                    || ProjectName;

                let projectToConfirm =
                    selectedOption;

                if (!selectedOption) {

                    const newProject =
                        await createDirectory(finalValue);

                    if (!newProject) {
                        return;
                    }

                    projectToConfirm = {
                        id: newProject.id,
                        name: newProject.name,
                        path: newProject.path,
                        creator: newProject.creator,
                        available: newProject.available
                    };
                }

                console.log(
                    "✅ CONFIRM PROJECT:",
                    projectToConfirm
                );

                onConfirm?.(projectToConfirm);
            }}
        >
            Weiter
        </button>

    </div>
);
}
