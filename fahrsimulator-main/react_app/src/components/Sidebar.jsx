function Sidebar({ onAddWidget, onClearWidgets }) {
  return (
    <aside className="sidebar">
      <h2>Widget Library</h2>
      <p>Add widgets and arrange them by drag and resize.</p>

      <div className="sidebar-actions">
        <button onClick={() => onAddWidget("status")}>Add Status</button>
        <button onClick={() => onAddWidget("speed")}>Add Speed</button>
        <button onClick={() => onAddWidget("image")}>Add Image</button>
        <button onClick={() => onAddWidget("chart")}>Add Chart</button>
        <button onClick={() => onAddWidget("shimmer")}>Add Shimmer</button>
      </div>

      <button className="danger" onClick={onClearWidgets}>
        Clear Dashboard
      </button>
    </aside>
  )
}

export default Sidebar
