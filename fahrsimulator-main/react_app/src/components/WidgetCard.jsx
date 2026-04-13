import { useState } from "react"
import SpeedChart from "./SpeedChart"

function WidgetCard({ widget, onDelete, onChangeView, sensorData, connected, running }) {
  const [imageSource, setImageSource] = useState("rgb_front")
  const silab = sensorData?.silab
  const rgbFrame = sensorData?.rgb_frame
  const tofFrame = sensorData?.tof_scelet
  const rgbBackFrame = sensorData?.rgb_frame2
  const gazeFrame = sensorData?.gaze
  const distraction = sensorData?.distraction
  const fahrweise = sensorData?.fahrweise
  const shimmer = sensorData?.shimmer
  const eyetracker = sensorData?.eyetracker
  const packetSummary = {
    silab,
    distraction,
    fahrweise,
    shimmer,
    eyetracker,
    rgb_frame: rgbFrame ? `[base64:${rgbFrame.length}]` : null,
    rgb_frame2: rgbBackFrame ? `[base64:${rgbBackFrame.length}]` : null,
    tof_scelet: tofFrame ? `[base64:${tofFrame.length}]` : null,
    gaze: gazeFrame ? `[base64:${gazeFrame.length}]` : null,
  }

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
    const imageMap = {
      rgb_front: rgbFrame,
      tof: tofFrame,
      rgb_back: rgbBackFrame,
    }
    const selectedImage = imageMap[imageSource]
    
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
          <img className="stream-image" src={`data:image/jpeg;base64,${selectedImage}`} alt="Live sensor stream" />
        ) : (
          <div className="placeholder">No frame yet for {imageSource.replace("_", " ")}. Start recording to receive frames.</div>
        )}
      </div>
    )
  }

  if (widget.view === "gaze") {
    body = gazeFrame ? (
      <img className="stream-image" src={`data:image/jpeg;base64,${gazeFrame}`} alt="Live gaze stream" />
    ) : (
      <div className="placeholder">No gaze frame available in the current sensor payload.</div>
    )
  }

  if (widget.view === "text") {
    body = (
      <div className="widget-stack">
        <h4>Notes</h4>
        <p>Use this panel to keep task notes while validating your dashboard layout.</p>
      </div>
    )
  }

  if (widget.view === "chart") {
    body = <SpeedChart sensorData={sensorData} />
  }

  if (widget.view === "distraction") {
    const prob = Number(distraction?.prob_distracted)
    const label = Number(distraction?.label)
    const frames = Number(distraction?.n_frames)
    const isDistracted = Number.isFinite(label) && label === 1

    body = (
      <div className="widget-stack">
        <div className="status-row">
          <span>Distracted</span>
          <strong className={isDistracted ? "bad" : "ok"}>{isDistracted ? "Yes" : "No"}</strong>
        </div>
        <div className="status-row">
          <span>Probability</span>
          <strong>{Number.isFinite(prob) ? prob.toFixed(3) : "-"}</strong>
        </div>
        <div className="status-row">
          <span>Frames</span>
          <strong>{Number.isFinite(frames) ? frames : "-"}</strong>
        </div>
      </div>
    )
  }

  if (widget.view === "fahrweise") {
    const prediction = fahrweise?.prediction
    const confidence = Number(fahrweise?.confidence)
    const isFast = prediction === "fast"

    body = (
      <div className="widget-stack">
        <div className="status-row">
          <span>Prediction</span>
          <strong className={isFast ? "bad" : "ok"}>{prediction || "-"}</strong>
        </div>
        <div className="status-row">
          <span>Confidence</span>
          <strong>{Number.isFinite(confidence) ? confidence.toFixed(3) : "-"}</strong>
        </div>
      </div>
    )
  }

  if (widget.view === "shimmer") {
    const sdnn = Number(shimmer?.sdnn)
    const rmssd = Number(shimmer?.rmssd)

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

  if (widget.view === "eyetracker") {
    body = eyetracker ? (
      <pre className="raw-payload">{JSON.stringify(eyetracker, null, 2)}</pre>
    ) : (
      <div className="placeholder">No eyetracker packet available in the current payload.</div>
    )
  }

  if (widget.view === "raw") {
    body = (
      <div className="widget-stack">
        <h4>Raw Sensor Packet</h4>
        <pre className="raw-payload">{JSON.stringify(packetSummary, null, 2)}</pre>
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
            <option value="gaze">Gaze</option>
            <option value="text">Notes</option>
            <option value="chart">Chart</option>
            <option value="distraction">Distraction</option>
            <option value="fahrweise">Fahrweise</option>
            <option value="shimmer">Shimmer</option>
            <option value="eyetracker">Eyetracker</option>
            <option value="raw">Raw Packet</option>
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

export default WidgetCard
