import {useEffect, useState} from "react";
import {SENSOR_WIDGETS} from "./widgetConfig";
import "../../styles/Sidebar.css"

const API_URL = "http://localhost:9999";

function Sidebar({
                     sidebarCollapsed,
                     setSidebarCollapsed,
                     onAddWidget,
                     onClearWidgets,
                     setLayout,
                     setWidgets,
                     widgets,
                     layout,
                     currentLayoutName,
                     setCurrentLayoutName,
                     project,
                     setLayoutProject
                 }) {
    const [layouts, setLayouts] = useState([]);
    const [layoutName, setLayoutName] = useState("");

    // 🔄 Layoutliste laden
    const fetchLayouts = async () => {
        try {
            const res = await fetch(`${API_URL}/api/layouts/full-db`, {
                credentials: "include",
            });

            const data = await res.json();
            setLayouts(data || []);
        } catch (err) {
            console.error("Fehler beim Laden der Layouts:", err);
        }
    };

/*
const resetDashboardLayout = () => {
    setWidgets([])
    setLayout([])
}
*/


    useEffect(() => {
        fetchLayouts();
    }, [project]);

    // 📥 Layout laden (projektübergreifend)
    const loadLayout = async (projectName, layoutName) => {
        if (!projectName || !layoutName) return;

        try {
            const res = await fetch(
                `${API_URL}/api/layout/${projectName}/${layoutName}`,
                {credentials: "include"}
            );

            if (!res.ok) throw new Error("API Fehler");

            const data = await res.json();

            setLayout(data.layout || []);
            setWidgets(data.widgets || []);

            // 🔥 Ownership setzen
            setLayoutProject(data.project);

        } catch (err) {
            console.error("Fehler beim Laden:", err);
        }
    };

    // 💾 Save Layout
    const saveLayoutAs = async () => {
        const trimmedName = layoutName.trim();
        if (!project || !trimmedName) return;

        try {
            const res = await fetch(
                `${API_URL}/api/layout/${project}/${trimmedName}`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    credentials: "include",
                    body: JSON.stringify({
                        layout,
                        widgets,
                    }),
                }
            );

            if (!res.ok) throw new Error("API Fehler");

            setCurrentLayoutName(`${project}::${trimmedName}`);
            setLayoutName("");
            fetchLayouts();

        } catch (err) {
            console.error("Fehler beim Speichern:", err);
        }
    };

    // 🗑 Delete Layout
    const deleteSelectedLayout = async () => {
        if (!currentLayoutName) return;

        const parts = currentLayoutName.split("::");

        // 🔥 Fallback falls kein "::" vorhanden
        const layoutProjectName = parts.length === 2 ? parts[0] : project;
        const layoutNameOnly = parts.length === 2 ? parts[1] : parts[0];

        // ❌ Fremdes Layout blockieren
        if (layoutProjectName !== project) {
            alert("Du kannst nur Layouts aus deinem eigenen Projekt löschen!");
            return;
        }

        const confirmed = window.confirm(`Layout "${layoutNameOnly}" löschen?`);
        if (!confirmed) return;

        try {
            const res = await fetch(
                `${API_URL}/api/layout/${project}/${layoutNameOnly}`,
                {
                    method: "DELETE",
                    credentials: "include",
                }
            );

            if (!res.ok) throw new Error("API Fehler");

            // 🔥 Reset UI nach Delete
            setCurrentLayoutName("");
            setLayout([]);
            setWidgets([]);

            // 🔄 Liste neu laden
            fetchLayouts();

        } catch (err) {
            console.error("Fehler beim Löschen:", err);
        }
    };
    // 🔥 Helpers
    const isForeignLayout =
        currentLayoutName &&
        currentLayoutName.split("::")[0] !== project;

    const isSameNameAsLoaded =
        currentLayoutName &&
        layoutName &&
        currentLayoutName.split("::")[1] === layoutName.trim();


    const sortedLayouts = [...layouts].sort((a, b) => {
        const aOwn = a.project_name === project;
        const bOwn = b.project_name === project;

        // Eigenes Projekt zuerst
        if (aOwn && !bOwn) return -1;
        if (!aOwn && bOwn) return 1;

        // danach alphabetisch
        return a.name.localeCompare(b.name);
    });


    return (
        <aside className={`Sidebar  ${sidebarCollapsed ? "SidebarCollapsed" : ""}`}>
            <button
                className="SidebarToggle"
                onClick={() => setSidebarCollapsed(prev => !prev)}
            >
                {sidebarCollapsed ? ">" : "<"}
            </button>
            {!sidebarCollapsed && (
                <>
                <div className="SidebarSensorCard">
                    <h2 className="SidebarTitle">
                        Sensoren
                    </h2>

                {/* SENSOREN */}
                <div className="SidebarActions">

                    {SENSOR_WIDGETS.map((sensor) => (
                        <button
                            key={sensor.key}
                            className="SidebarSensorCardBtn"
                            onClick={() => onAddWidget(sensor.key)}
                        >
                            <div className="SidebarSensorLeft">
                                <span className="SidebarSensorIcon">
                                    {sensor.icon}
                                </span>

                                <span className="SidebarSensorLabel">
                                    {sensor.label}
                                </span>
                            </div>

                        </button>
                    ))}

                        </div>
                        <button
                            className="SidebarDashboardClearBtn"
                            onClick={onClearWidgets}
                        >
                            🗑 Dashboard leeren
                        </button>
                    </div>

                    <div className="SidebarDivider"/>

                    {/* LAYOUT CARD */}

                    <div className="SidebarLayoutCard">

                        <h3 className="SidebarLayoutCardTitle">
                            Layouts
                        </h3>
                        {isForeignLayout && (
                            <div className="SidebarForeignLayoutWarning">
                                Dieses Layout gehört zu einem anderen Projekt.
                                Du kannst es nur unter neuem Namen speichern.
                            </div>
                        )}

                        {/*<div className="layout-current">
                                Current layout: {currentLayoutName || "-"}
                            </div>*/}
                        <label className="SidebarInputLabel">
                            Layout auswählen
                        </label>
                        <select
                            value={currentLayoutName || ""}
                            onChange={(e) => {
                                const value = e.target.value;
                                setCurrentLayoutName(value);

                                if (!value) return;

                                const [projectName, layoutNameOnly] = value.split("::");

                                loadLayout(projectName, layoutNameOnly);
                            }}
                        >
                            <option value="">Layout auswählen</option>
                            {sortedLayouts.map((l) => (
                                <option
                                    key={l.id}
                                    value={`${l.project_name}::${l.name}`}
                                    className={
                                        l.project_name === project
                                            ? "SidebarOwnLayout"
                                            : "SidebarForeignLayout"

                                    }
                                >
                                    {l.name} ({l.project_name})
                                </option>
                            ))}
                        </select>


                        <label className="SidebarInputLabel">
                            Layoutname
                        </label>
                        <input
                            type="text"
                            placeholder="z.B. Labor Setup 1"
                            className="SidebarLayoutName"
                            value={layoutName}
                            onChange={(e) =>
                                setLayoutName(e.target.value)
                            }
                        />

                        <button
                            className="SidebarSaveLayoutButton"
                            onClick={saveLayoutAs}
                            disabled={
                                !layoutName.trim() ||
                                (isForeignLayout && isSameNameAsLoaded)
                            }
                        > 💾 {
                            isForeignLayout
                                ? "Als neues Layout speichern"
                                : "Layout speichern"
                        }
                        </button>

{/*
                        <button
                            className="SidebarResetLayoutButton"
                            onClick={resetDashboardLayout}
                        >
                            ↻ Layout zurücksetzen
                        </button>
*/}

                        <button
                            className="SidebarDeleteLayoutButton"
                            onClick={deleteSelectedLayout}
                            disabled={
                                !currentLayoutName ||
                                isForeignLayout
                            }
                        >
                            🗑 Layout löschen
                        </button>

                    </div>

                </>
                )}
                </aside>

            );
            }
            export default Sidebar;