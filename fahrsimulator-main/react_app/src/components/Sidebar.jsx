import {useEffect, useState} from "react";
import { SENSOR_WIDGETS } from "./widgetConfig";

function Sidebar({onAddWidget, onClearWidgets, setLayout, setWidgets, widgets, currentLayoutName, setCurrentLayoutName}) {

    // State gehört IN die Komponente
    const [layouts, setLayouts] = useState([]);
    const [layoutName, setLayoutName] = useState("");

    // Layouts laden beim Start
    useEffect(() => {
        fetch("http://localhost:9999/api/layouts")


            .then(res => res.json())
            .then(data => {
                console.log("Layouts vom Server:", data);
                setLayouts(data);
            })
            .catch(err => console.error(err));
    }, []);

    const refreshLayouts = () => {
        fetch("http://localhost:9999/api/layouts")
            .then(res => res.json())
            .then(data => setLayouts(data))
            .catch(err => console.error(err));
    };

    // Layout laden
    const loadLayout = async (projectName) => {
        if (!projectName) return;

        try {
            const res = await fetch(`http://localhost:9999/api/layout/${projectName}`);

            if (!res.ok) throw new Error("API Fehler");

            const data = await res.json();

            // 🔍 DEBUG PRINT
            console.log("=== LOAD LAYOUT DEBUG ===");
            console.log("Project:", projectName);
            console.log("Layout:", data.layout);
            console.log("Widgets:", data.widgets);
            console.log("==========================");

            setLayout(data.layout);
            setWidgets(data.widgets);

        } catch (err) {
            console.error("Fehler beim Laden:", err);
        }
    };

    const deleteSelectedLayout = async () => {
        if (!currentLayoutName) return;

        const confirmed = window.confirm(`Delete layout "${currentLayoutName}"?`);
        if (!confirmed) return;

        try {
            const res = await fetch(`http://localhost:9999/api/layout/${currentLayoutName}`, {
                method: "DELETE",
            });

            if (!res.ok) throw new Error("API Fehler");

            setCurrentLayoutName("");
            setLayout([]);
            setWidgets([]);
            refreshLayouts();
        } catch (err) {
            console.error("Fehler beim Loeschen:", err);
        }
    };

    const saveLayoutAs = async () => {
        const trimmedName = layoutName.trim();
        if (!trimmedName) return;

        const layoutPayload = (widgets || []).map((widget) => ({
            i: widget.i,
            x: widget.x,
            y: widget.y,
            w: widget.w,
            h: widget.h,
        }));

        try {
            const res = await fetch(`http://localhost:9999/api/layout/${encodeURIComponent(trimmedName)}`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                credentials: "include",
                body: JSON.stringify({
                    layout: layoutPayload,
                    widgets: widgets || [],
                }),
            });

            if (!res.ok) throw new Error("API Fehler");

            setCurrentLayoutName(trimmedName);
            setLayoutName("");
            refreshLayouts();
        } catch (err) {
            console.error("Fehler beim Speichern:", err);
        }
    };


    return (
        <aside className="sidebar">
            <h2>Widget Library</h2>
            <p>Add widgets and arrange them by drag and resize.</p>

      <div className="sidebar-actions">
        {SENSOR_WIDGETS.map((sensor) => (
          <button key={sensor.key} onClick={() => onAddWidget(sensor.key)}>
            Add {sensor.label}
          </button>
        ))}
      </div>

            <button className="danger" onClick={onClearWidgets}>
                Clear Dashboard
            </button>

            {/* NEU: Dropdown */}
            <div className="sidebar-bottom">
                <h3>Layouts</h3>
                <div className="layout-current">
                    Current layout: {currentLayoutName || "-"}
                </div>
                <input
                    type="text"
                    placeholder="Layout name"
                    value={layoutName}
                    onChange={(e) => setLayoutName(e.target.value)}
                />
                <button onClick={saveLayoutAs} disabled={!layoutName.trim()}>
                    Save Layout
                </button>
                <select
                    value={currentLayoutName}
                    onChange={(e) => {
                        const nextLayout = e.target.value;
                        setCurrentLayoutName(nextLayout);
                        loadLayout(nextLayout);
                    }}
                >
                    <option value="">Layout auswählen</option>
                    {layouts.map((l) => (
                        <option key={l.project_name} value={l.project_name}>
                            {l.project_name}
                        </option>
                    ))}
                </select>
                <button className="danger" onClick={deleteSelectedLayout} disabled={!currentLayoutName}>
                    Delete Layout
                </button>
            </div>
        </aside>
    );
}

export default Sidebar;