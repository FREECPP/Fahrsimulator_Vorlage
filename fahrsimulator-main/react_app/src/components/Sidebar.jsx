import {useEffect, useState} from "react";
import {getDefaultMode, getSensorTitle, SENSOR_WIDGETS} from "./widgetConfig";
import {getPreferredWidgetGridSize} from "./widgetSizing.js";

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

    function createDefaultWidgets() {
        const DEFAULT_WIDGET_LAYOUT = [
            {view: "silab", x: 0, y: 0},
            {view: "eyetracker", x: 6, y: 0},
            {view: "tof", x: 0, y: 3},
            {view: "rgb_front", x: 4, y: 3},
            {view: "rgb_back", x: 8, y: 3},
            {view: "shimmer", x: 0, y: 6},
        ]


// ===== Widget =====
        function createWidget(view) {

            const id =
                `${Date.now()}-${Math.round(Math.random() * 10000)}`

            const mode = getDefaultMode(view)

            const preferredSize =
                getPreferredWidgetGridSize(view, mode)

            return {
                i: id,
                x: 0,
                y: 0,
                w: preferredSize.w,
                h: preferredSize.h,
                view,
                mode,
                title: getSensorTitle(view),
            }
        }

        return DEFAULT_WIDGET_LAYOUT.map(
            ({view, x, y}) => ({
                ...createWidget(view),
                x,
                y,
            })
        )
    }

    const resetDashboardLayout = () => {
        setWidgets(createDefaultWidgets())
    }

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

        const confirmed = window.confirm(
            `Delete layout "${layoutNameOnly}"?`
        );
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
        <aside className={`sidebar ${sidebarCollapsed ? "collapsed" : ""}`}>
            <button
                className="sidebar-toggle"
                onClick={() => setSidebarCollapsed(prev => !prev)}
            >
                {sidebarCollapsed ? ">" : "<"}
            </button>
            {!sidebarCollapsed && (
                <>
                    <h2>Sensoren</h2>
                    <div className="sidebar-button-group">

                        <div className="sidebar-actions">
                            {SENSOR_WIDGETS.map((sensor) => (
                                <button key={sensor.key} onClick={() => onAddWidget(sensor.key)}>
                                    Add {sensor.label}
                                </button>
                            ))}
                        </div>
                        <div className="sidebar-actions">
                            <button className="danger" onClick={onClearWidgets}>
                                Clear Dashboard
                            </button>
                        </div>
                        <div className="sidebar-bottom">
                            <h3>Layouts</h3>

                            {/*<div className="layout-current">
                                Current layout: {currentLayoutName || "-"}
                            </div>*/}

                            {/* 🔥 Hinweis */}
                            {isForeignLayout && (
                                <div style={{color: "orange", fontSize: "0.9em", margin: "12px 0"}}>
                                    Dieses Layout gehört zu einem anderen Projekt. Du kannst es unter einem anderen
                                    Namen speichern
                                </div>
                            )}
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
                                                ? "own-layout"
                                                : "foreign-layout"
                                        }
                                    >
                                        {l.name} ({l.project_name})
                                    </option>
                                ))}
                            </select>
                            <input
                                type="text"
                                placeholder="Layout name"
                                className="layoutName"
                                value={layoutName}
                                onChange={(e) => setLayoutName(e.target.value)}
                            />

                            <button
                                className="save-layout-button"
                                onClick={saveLayoutAs}
                                disabled={
                                    !layoutName.trim() ||
                                    (isForeignLayout && isSameNameAsLoaded)
                                }
                            >
                                {isForeignLayout ? "Save as new layout" : "Save Layout"}
                            </button>


                            <button
                                className="delete-layout-button"
                                onClick={deleteSelectedLayout}
                                disabled={!currentLayoutName || isForeignLayout}
                            >
                                Delete Layout
                            </button>

                            <button
                                className="control-btn reset"

                                onClick={
                                    resetDashboardLayout
                                }
                            >
                                Reset Layout
                            </button>
                        </div>
                    </div>
                </>
            )}
        </aside>
    );
}

export default Sidebar;