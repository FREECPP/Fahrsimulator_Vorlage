import { SENSOR_WIDGETS } from "./widgetConfig"

function Sidebar({ onAddWidget, onClearWidgets }) {
  return (
    <aside className="sidebar">
      <h2>Widget Library</h2>
      <p>Add one widget per sensor and choose the display mode in each card.</p>

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
    </aside>
  )
}

export default Sidebar
