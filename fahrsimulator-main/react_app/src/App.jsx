import React, {useState, useEffect} from "react";
import "./App.css";
import ProjectTable from "./components/ProjectTable.jsx";
import {useNavigate} from "react-router-dom";
import {ToastContainer, toast} from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

import {useDropzone} from "react-dropzone";

export default function ProjectManager() {
    const navigate = useNavigate();
    const [participants, setParticipants] = useState([]);
    const [_selectedProject, setSelectedProject] = useState("");
    const [confirmedProject, setConfirmedProject] = useState(null);
    const [showModal, setShowModal] = useState(false);
    const [newParticipantName, setNewParticipantName] = useState("");

    // 🔥 Teilnehmer laden
    const loadParticipants = async (projectId) => {
        const url = `http://localhost:9999/api/participants/${projectId}`

        try {
            const res = await fetch(url)

            if (!res.ok) {
                console.error("❌ Teilnehmer-Request fehlgeschlagen:", res.status)
                return
            }

            const data = await res.json()
            setParticipants(data)

        } catch (err) {
            console.error("❌ Fetch Fehler (Participants):", err)
        }
    }

    useEffect(() => {
        if (!confirmedProject?.id) {
            console.warn("⚠️ Kein gültiges Projekt:", confirmedProject)
            return
        }

        loadParticipants(confirmedProject.id)
    }, [confirmedProject])

    // 🔥 DELETE
    const handleDeleteParticipant = (id) => {
        if (!window.confirm("Sind Sie sich sicher, dass Sie den Probanden und dessen Daten löschen wollen?")) {
            return;
        }

        fetch(`http://localhost:9999/api/participant/${id}`, {
            method: "DELETE"
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    setParticipants(prev => prev.filter(p => p.id !== id));
                    toast.success("Participant gelöscht");
                } else {
                    toast.error(data.message);
                }
            })
            .catch(err => {
                console.error(err);
                toast.error("Fehler beim Löschen");
            });
    };

    // 🔥 Upload
    const onDrop = (acceptedFiles) => {
        if (!confirmedProject) {
            toast.error("Bitte zuerst ein Projekt auswählen");
            return;
        }

        const formData = new FormData();

        acceptedFiles.forEach(file => {
            formData.append("files", file);
            formData.append("paths", file.webkitRelativePath || file.name);
        });

        formData.append("project_id", confirmedProject.id);

        fetch("http://localhost:9999/api/upload", {
            method: "POST",
            body: formData
        })
            .then(res => res.json())
            .then(() => {
                toast.success("Upload erfolgreich");
                loadParticipants(confirmedProject.id);
            })
            .catch(err => {
                console.error(err);
                toast.error("Upload fehlgeschlagen");
            });
    };

    // 🔥 Create Participant
    const handleCreateParticipant = () => {
        if (!newParticipantName.trim()) {
            toast.error("Bitte Namen eingeben");
            return;
        }

        if (!confirmedProject) {
            toast.error("Kein Projekt ausgewählt");
            return;
        }

        fetch("http://localhost:9999/api/participant/create", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                name: newParticipantName,
                project_id: confirmedProject.id
            })
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    toast.success("Participant erstellt");
                    setShowModal(false);
                    setNewParticipantName("");
                    loadParticipants(confirmedProject.id);
                } else {
                    toast.error(data.message);
                }
            })
            .catch(() => toast.error("Fehler beim Erstellen"));
    };

    const {getRootProps, getInputProps, isDragActive} = useDropzone({
        onDrop,
        multiple: true
    });

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

                    <div className="card">
                        <table>
                            <thead>
                                <tr>
                                    <th className="play-column"></th>
                                    <th>Name</th>
                                    <th>Pfad</th>
                                    <th>Letzter Aufruf</th>
                                    <th className="right">Runs</th>
                                    <th></th>
                                </tr>
                            </thead>

                            <tbody>
                                {participants.length === 0 ? (
                                    <tr>
                                        <td colSpan="6" style={{textAlign: "center"}}>
                                            Keine Teilnehmer gefunden
                                        </td>
                                    </tr>
                                ) : (
                                    participants.map((p) => (
                                        <tr key={p.id}>
                                            <td className="play-column">
                                                <button
                                                    className="play-btn"
                                                    onClick={() => {
                                                        const fullPath = p.path

                                                        console.log("👉 Öffne Dashboard mit:", fullPath)

                                                        navigate("/dashboard", {
                                                            state: {
                                                                project: confirmedProject,
                                                                participant: p,
                                                                path: fullPath,
                                                            },
                                                        })
                                                    }}
                                                >
                                                    ▶
                                                </button>
                                            </td>

                                            <td>{p.name}</td>

                                            <td className="path-cell" title={p.path}>
                                                {p.path}
                                            </td>

                                            <td>
                                                {p.last_run ? new Date(p.last_run).toLocaleDateString() : "—"}
                                            </td>

                                            <td className="right">{p.runs}</td>

                                            <td>
                                                <button
                                                    className="delete-btn"
                                                    onClick={() => handleDeleteParticipant(p.id)}
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

                    <div className="center">
                        <button className="btn primary" onClick={() => setShowModal(true)}>
                            + Add Participant
                        </button>
                    </div>

                    {showModal && (
                        <div className="modalOverlay">
                            <div className="modal">
                                <h3>Neuer Proband</h3>

                                <input
                                    value={newParticipantName}
                                    onChange={(e) => setNewParticipantName(e.target.value)}
                                />

                                <div className="modalActions">
                                    <button onClick={handleCreateParticipant}>OK</button>
                                    <button onClick={() => setShowModal(false)}>Abbrechen</button>
                                </div>
                            </div>
                        </div>
                    )}

                    <div {...getRootProps()} className={`upload ${isDragActive ? "active" : ""}`}>
                        <input {...getInputProps()} />
                        Drag & Drop
                    </div>
                </section>
            </div>

            <ToastContainer position="bottom-center" />
        </main>
    );
}
