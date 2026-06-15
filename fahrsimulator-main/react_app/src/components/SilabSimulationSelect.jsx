import { useEffect, useRef, useState } from "react";
import { toast } from "react-toastify";

import "./../styles/ProjectTable.css";

export default function SilabSimulationSelect({
    onChange,
    onConfirm
}) {
    const [fileName, setFileName] = useState("");
    const [selectedOption, setSelectedOption] = useState(null);
    const [options, setOptions] = useState([]);
    const [isOpen, setIsOpen] = useState(false);
    const [showAll, setShowAll] = useState(false);

    const containerRef = useRef(null);

    // ===== Dateien laden ====

async function fetchFiles() {
    try {

        const res = await fetch(
            "http://localhost:9999/api/silab/simulations"
        );

        if (!res.ok) {
            throw new Error(
                `HTTP ${res.status}`
            );
        }

        const data = await res.json();

        const formatted = data.map(
            simulation => ({
                name: simulation.name,
                path: simulation.path,
                available: true
            })
        );

        setOptions(formatted);

    } catch (err) {

        console.error(
            "Fehler beim Laden der Simulationen:",
            err
        );

        toast.error(
            "Simulationen konnten nicht geladen werden"
        );
    }
}
    useEffect(() => {
        fetchFiles();
    }, []);

    // ===== Outside Click =====
    useEffect(() => {

        function handleClickOutside(e) {

            if (
                containerRef.current &&
                !containerRef.current.contains(
                    e.target
                )
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

            const search =
                fileName.toLowerCase();

            return [
                opt.name,
                opt.path
            ].some(value =>
                String(value)
                    .toLowerCase()
                    .includes(search)
            );
        })

        .sort((a, b) =>
            a.name.localeCompare(b.name)
        );

    return (
        <div
            className="project-dropdown"
            ref={containerRef}
        >

            <div className="input-wrapper">

                <input
                    type="text"
                    placeholder="Datei auswählen..."
                    value={fileName}
                    className="input"

                    onFocus={() => {
                        setShowAll(false);
                        setIsOpen(true);
                    }}

                    onChange={(e) => {

                        const val =
                            e.target.value;

                        setShowAll(false);

                        setFileName(val);
                        setSelectedOption(null);
                        setIsOpen(true);

                        onChange?.({
                            name: val
                        });
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

                    {filteredOptions.length === 0 && (
                        <li
                            style={{
                                padding: "12px",
                                color: "#777"
                            }}
                        >
                            Keine Dateien gefunden
                        </li>
                    )}

                    {filteredOptions.map(opt => (

                        <li
                            key={opt.path}

                            onClick={() => {

                                setFileName(
                                    opt.name
                                );

                                setSelectedOption(
                                    opt
                                );

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

                                    {/* <div className="right">
                                        <span className="projectPath">
                                            {opt.path}
                                        </span>
                                    </div>*/}

                                </div>

                            </div>

                        </li>

                    ))}

                </ul>
            )}

        </div>
    );
}