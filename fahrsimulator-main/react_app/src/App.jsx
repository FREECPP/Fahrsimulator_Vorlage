import React, {useState, useEffect} from "react";
import "./App.css";
import ProjectTable from "./components/ProjectTable.jsx";
import {useNavigate} from "react-router-dom";
import {ToastContainer, toast} from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import SilabSimulationSelect from "./components/SilabSimulationSelect.jsx";


export default function ProjectManager() {
    const navigate = useNavigate();

    const [participants, setParticipants] = useState([]);
    const [_selectedProject, setSelectedProject] = useState("");
    const [confirmedProject, setConfirmedProject] = useState(null);
    const [showModal, setShowModal] = useState(false);
    const [newParticipantName, setNewParticipantName] = useState("");
    const [selectedParticipant, setSelectedParticipant] = useState(null);
    const [selectedSimulation, setSelectedSimulation] =
    useState(null);
    // Teilnehmer laden
    const loadParticipants = async (projectId) => {
        const url = `http://localhost:9999/api/participants/${projectId}`;

        try {
            const res = await fetch(url);

            if (!res.ok) {
                console.error("Participants Request Fehler:", res.status);
                return;
            }

            const data = await res.json();
            setParticipants(data);
        } catch (err) {
            console.error("Participants Fetch Fehler:", err);
        }
    };

    // Projekt geändert
    useEffect(() => {
        if (!confirmedProject?.id) {
            console.warn("Ungültiges Projekt:", confirmedProject);
            return;
        }

        setSelectedParticipant(null);
        void loadParticipants(confirmedProject.id);
    }, [confirmedProject]);
const handleDeleteParticipant = (id) => {
        if (
            !window.confirm(
                "Sind Sie sich sicher, dass Sie den Probanden und dessen Daten löschen wollen?"
            )
        ) {
            return;
        }

        fetch(`http://localhost:9999/api/participant/${id}`, {
            method: "DELETE"
        })
            .then((res) => res.json())
            .then((data) => {
                if (data.success) {
                    setParticipants((prev) => prev.filter((p) => p.id !== id));
                    toast.success("Participant gelöscht");
                } else {
                    toast.error(data.message);
                }
            })
            .catch((err) => {
                console.error(err);
                toast.error("Fehler beim Löschen");
            });
    };

    // Participant löschen
const handleCreateParticipant = () => {
    if (!newParticipantName.trim()) {
        toast.error("Bitte Namen eingeben");
        return;
    }

    if (!confirmedProject) {
        toast.error("Kein Projekt ausgewählt");
        return;
    }

    if (!selectedSimulation) {
        toast.error("Bitte eine Datei auswählen");
        return;
    }

    fetch("http://localhost:9999/api/participant/create", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            name: newParticipantName,
            project_id: confirmedProject.id,
            simulation_path: selectedSimulation.path
        })
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.success) {

                toast.success("Participant erstellt");

                const participant =
                    data.participant;

                setShowModal(false);
                setNewParticipantName("");
                setSelectedSimulation(null);

                navigate("/dashboard", {
                    state: {
                        project: confirmedProject,
                        participant,
                        path: participant.path
                    }
                });

            } else {
                toast.error(data.message);
            }
        })
        .catch(() =>
            toast.error("Fehler beim Erstellen")
        );
};

    // Dashboard öffnen
    const openDashboard = () => {
        if (!selectedParticipant) {
            toast.error("Bitte Participant auswählen");
            return;
        }

        const fullPath = selectedParticipant.path;

        console.log("Öffne Dashboard:", fullPath);

        navigate("/dashboard", {
            state: {
                project: confirmedProject,
                participant: selectedParticipant,
                path: fullPath
            }
        });
    };

    // Render
    return (
        <main className="page">
            <div className="container">
                <ProjectTable
                    onChange={setSelectedProject}
                    onConfirm={(proj) => setConfirmedProject(proj)}
                />

                <section>
                    <div className="header">
                        <div className="center">
                            <h2>Probanden</h2>

                            <p className="sub">
                                {confirmedProject?.name || "Kein Projekt ausgewählt"}
                            </p>
                        </div>
                    </div>

                    {/* Tabelle */}
                    <div className="card">
                        <table>
                            <thead>
                            <tr>
                                <th>Name</th>
                                <th>Simulation</th>
                                <th>Datum</th>
                                <th>Dauer</th>
                                <th>Größe</th>
                                <th></th>
                            </tr>
                            </thead>

                            <tbody>
                            {participants.length === 0 ? (
                                <tr>
                                    <td
                                        colSpan="6"
                                        style={{textAlign: "center"}}
                                    >
                                        Keine Teilnehmer gefunden
                                    </td>
                                </tr>
                            ) : (
                                participants.map((p) => (
                                    <tr
                                        key={p.id}
                                        onClick={() => setSelectedParticipant(p)}
                                        className={
                                            selectedParticipant?.id === p.id
                                                ? "selected-row"
                                                : ""
                                        }
                                    >
                                        <td>{p.name}</td>

                                        <td
                                            className="path-cell"
                                            title={p.simulation_path}
                                        >
                                            {p.simulation_path.split(/[\\/]/).pop()}
                                        </td>

                                        <td>
                                            {p.run_started_at
                                                ? new Date(
                                                    p.run_started_at
                                                ).toLocaleString()
                                                : "—"}
                                        </td>

                                        <td>
                                            {p.run_duration_seconds
                                                ? `${Math.floor(
                                                    p.run_duration_seconds / 60
                                                )} min ${
                                                    p.run_duration_seconds % 60
                                                } s`
                                                : "—"}
                                        </td>
                                        <td>

                                            {p.file_size !== undefined
                                                ? `${(p.file_size / (1024 * 1024)).toFixed(2)} MB`
                                                : "—"}
                                        </td>
                                        <td>
                                            <button
                                                className="delete-btn"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleDeleteParticipant(p.id);
                                                }}
                                            >
                                                🗑️
                                            </button>
                                        </td>
                                    </tr>
                                ))
                            )}
                            </tbody>
                        </table>
                    </div>

                    {/* Buttons */}
                    <div
                        className="center"
                        style={{
                            display: "flex",
                            gap: "1rem",
                            justifyContent: "center"
                        }}
                    >
                        <button
                            className="btn primary"
                            onClick={() => setShowModal(true)}
                        >
                            + Add Participant
                        </button>

                        <button
                            className="btn primary"
                            onClick={openDashboard}
                        >
                            Dashboard öffnen
                        </button>
                    </div>

                    {/* Modal */}
                    {showModal && (
    <div className="modalOverlay">

        <div
            className="modal"
            style={{
                minWidth: "400px",
                maxWidth: "600px"
            }}
        >

            <h3>Neuer Proband</h3>

            <input
                value={newParticipantName}
                placeholder="Name des Probanden"
                onChange={(e) =>
                    setNewParticipantName(
                        e.target.value
                    )
                }
            />

            <div
                style={{
                    marginTop: "15px"
                }}
            >
                <label
                    style={{
                        display: "block",
                        marginBottom: "8px",
                        fontWeight: 600
                    }}
                >
                    Simulation auswählen
                </label>

                <SilabSimulationSelect
                    onConfirm={(file) => {
                        console.log(
                            "Datei ausgewählt:",
                            file
                        );

                        setSelectedSimulation(
                            file
                        );
                    }}
                />
            </div>

            {selectedSimulation && (
                <div
                    style={{
                        marginTop: "10px",
                        fontSize: "12px",
                        color: "#666"
                    }}
                >
                </div>
            )}

            <div className="modalActions">

                <button
                    onClick={
                        handleCreateParticipant
                    }
                >
                    OK
                </button>

                <button
                    onClick={() => {

                        setShowModal(false);

                        setSelectedSimulation(
                            null
                        );

                        setNewParticipantName(
                            ""
                        );
                    }}
                >
                    Abbrechen
                </button>

            </div>

        </div>

    </div>
)}
                </section>
            </div>

            <ToastContainer position="bottom-center"/>
        </main>
    );
}