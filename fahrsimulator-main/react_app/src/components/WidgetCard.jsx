import { memo, useEffect, useRef, useState } from "react"
import SpeedChart from "./SpeedChart"

function WidgetCard({ widget, onDelete, onChangeView, sensorData, connected, running }) {
  const [imageSource, setImageSource] = useState("rgb_front")
  const imageRef = useRef(null)
  const silab = sensorData?.silab
  const rgbFrame = sensorData?.rgb_frame
  const tofFrame = sensorData?.tof_scelet
  const rgbBackFrame = sensorData?.rgb_frame2
  const shimmer = sensorData?.shimmer
  const sdnn = Number(shimmer?.sdnn)
  const rmssd = Number(shimmer?.rmssd)
  const selectedImage =
    widget.view === "image"
      ? {
          rgb_front: rgbFrame,
          tof: tofFrame,
          rgb_back: rgbBackFrame,
        }[imageSource]
      : null

  useEffect(() => {
    if (widget.view !== "image" || !imageRef.current) return

    if (selectedImage) {
      imageRef.current.src = `data:image/jpeg;base64,${selectedImage}`
    } else {
      imageRef.current.removeAttribute("src")
    }
  }, [selectedImage, widget.view])

  let body = <div className="placeholder">Unknown widget type.</div>

  if (widget.view === "status") {
    body = (
      <div className="widget-stack">
        <div className="status-row">
          <span>Socket</span>
          <strong className={connected ? "ok" : "bad"}>{connected ? "Connected" : "Disconnected"}</strong>
        </div>
        <div className="status-row">
          <span>Recording</span>
          <strong className={running ? "ok" : "idle"}>{running ? "Running" : "Stopped"}</strong>
        </div>
        <div className="status-row">
          <span>Speed (km/h)</span>
          <strong>{typeof silab?.speed === "number" ? (silab.speed * 3.6).toFixed(1) : "-"}</strong>
        </div>
      </div>
    )
  }

  if (widget.view === "speed") {
    body = (
      <div className="widget-stack">
        <h4>Live Values</h4>
        <div className="status-row">
          <span>Speed</span>
          <strong>{typeof silab?.speed === "number" ? `${(silab.speed * 3.6).toFixed(1)} km/h` : "-"}</strong>
        </div>
        <div className="status-row">
          <span>Steering</span>
          <strong>{typeof silab?.steering === "number" ? silab.steering.toFixed(2) : "-"}</strong>
        </div>
        <div className="status-row">
          <span>Gas Pedal</span>
          <strong>{typeof silab?.acc_pedal === "number" ? silab.acc_pedal.toFixed(2) : "-"}</strong>
        </div>
        <div className="status-row">
          <span>Brake Pedal</span>
          <strong>{typeof silab?.brake_pedal === "number" ? silab.brake_pedal.toFixed(2) : "-"}</strong>
        </div>
      </div>
    )
  }

  if (widget.view === "image") {
    body = (
      <div className="widget-stack image-widget">
        <div style={{ marginBottom: "8px" }}>
          <label style={{ marginRight: "8px", fontSize: "0.9em" }}>Camera:</label>
          <select 
            value={imageSource} 
            onChange={(e) => setImageSource(e.target.value)}
            style={{ padding: "4px 8px", borderRadius: "4px", border: "1px solid #ccc" }}
          >
            <option value="rgb_front">RGB Front</option>
            <option value="tof">ToF</option>
            <option value="rgb_back">RGB Back</option>
          </select>
        </div>
        {selectedImage ? (
          <img ref={imageRef} className="stream-image" alt="Live sensor stream" />
        ) : (
          <div className="placeholder">No frame yet for {imageSource.replace("_", " ")}. Start recording to receive frames.</div>
        )}
      </div>
    )
  }

  if (widget.view === "chart") {
    body = <SpeedChart sensorData={sensorData} />
  }

  if (widget.view === "shimmer") {
    body = (
      <div className="widget-stack">
        <h4>HRV (Shimmer)</h4>
        <div className="status-row">
          <span>SDNN</span>
          <strong>{Number.isFinite(sdnn) ? sdnn.toFixed(2) : "-"}</strong>
        </div>
        <div className="status-row">
          <span>RMSSD</span>
          <strong>{Number.isFinite(rmssd) ? rmssd.toFixed(2) : "-"}</strong>
        </div>
      </div>
    )
  }

  return (
    <article className="widget-card">
      <header className="widget-header">
        <strong>{widget.title}</strong>
        <div className="widget-actions">
          <select value={widget.view} onChange={(event) => onChangeView(widget.i, event.target.value)}>
            <option value="status">Status</option>
            <option value="speed">Speed</option>
            <option value="image">Image</option>
            <option value="chart">Chart</option>
            <option value="shimmer">Shimmer</option>
          </select>
          <button className="danger" onClick={() => onDelete(widget.i)}>
            Remove
          </button>
        </div>
      </header>
      <section className="widget-body">{body}</section>
    </article>
  )
}

function hasSameWidgetIdentity(prevWidget, nextWidget) {
  return (
    prevWidget.i === nextWidget.i &&
    prevWidget.view === nextWidget.view &&
    prevWidget.title === nextWidget.title &&
    prevWidget.x === nextWidget.x &&
    prevWidget.y === nextWidget.y &&
    prevWidget.w === nextWidget.w &&
    prevWidget.h === nextWidget.h
  )
}

function areWidgetPropsEqual(prevProps, nextProps) {
  if (!hasSameWidgetIdentity(prevProps.widget, nextProps.widget)) return false
  if (prevProps.connected !== nextProps.connected) return false
  if (prevProps.running !== nextProps.running) return false

  const view = nextProps.widget.view
  const prevData = prevProps.sensorData || {}
  const nextData = nextProps.sensorData || {}

  if (view === "status") {
    return prevData.silab?.speed === nextData.silab?.speed
  }

  if (view === "speed" || view === "chart") {
    return (
      prevData.silab?.speed === nextData.silab?.speed &&
      prevData.silab?.steering === nextData.silab?.steering &&
      prevData.silab?.acc_pedal === nextData.silab?.acc_pedal &&
      prevData.silab?.brake_pedal === nextData.silab?.brake_pedal
    )
  }

  if (view === "image") {
    return (
      prevData.rgb_frame === nextData.rgb_frame &&
      prevData.tof_scelet === nextData.tof_scelet &&
      prevData.rgb_frame2 === nextData.rgb_frame2
    )
  }

  if (view === "shimmer") {
    return prevData.shimmer === nextData.shimmer
  }

  return true
}

export default memo(WidgetCard, areWidgetPropsEqual)
