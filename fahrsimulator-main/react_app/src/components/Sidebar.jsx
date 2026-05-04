import {useEffect, useState} from "react";

function Sidebar({onAddWidget, onClearWidgets, setLayout, setWidgets}) {

    // State gehört IN die Komponente
    const [layouts, setLayouts] = useState([]);

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
                <select onChange={(e) => loadLayout(e.target.value)}>
                    <option value="">Layout auswählen</option>
                    {layouts.map((l) => (
                        <option key={l.project_name} value={l.project_name}>
                            {l.project_name}
                        </option>
                    ))}
                </select>
            </div>
        </aside>
    );
}

export default Sidebar;