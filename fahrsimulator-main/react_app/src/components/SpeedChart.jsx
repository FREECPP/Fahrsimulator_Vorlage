import { useEffect, useRef, useState } from "react"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"

const MAX_STEERING_DEG = 450
const THROTTLE_MS = 200
const MAX_RENDER_POINTS = 300
const WINDOW_OPTIONS = [
  { label: "Last 1 min", value: 60 * 1000 },
  { label: "Last 3 min", value: 3 * 60 * 1000 },
  { label: "Last 5 min", value: 5 * 60 * 1000 },
  { label: "Last 10 min", value: 10 * 60 * 1000 },
]
const MAX_WINDOW_MS = Math.max(...WINDOW_OPTIONS.map((option) => option.value))
const MAX_POINTS = Math.ceil((MAX_WINDOW_MS / THROTTLE_MS) * 1.2)

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function toSteeringDegrees(value) {
  if (!Number.isFinite(value)) return null

  const normalized = 1 - ((value + 8) / 16)
  return clamp((normalized - 0.5) * 2 * MAX_STEERING_DEG, -MAX_STEERING_DEG, MAX_STEERING_DEG)
}

function formatElapsedSeconds(value) {
  if (!Number.isFinite(value)) return ""
  const totalSeconds = Math.max(0, Math.floor(value))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  const secondsLabel = minutes > 0 ? seconds.toString().padStart(2, "0") : seconds.toString()
  return `${minutes}:${secondsLabel}`
}

function downsampleData(entries, maxPoints) {
  if (!Array.isArray(entries) || entries.length <= maxPoints) return entries
  const stride = Math.ceil(entries.length / maxPoints)
  return entries.filter((_, index) => index % stride === 0 || index === entries.length - 1)
}

function SpeedChart({ silab, sensorData }) {
  const [data, setData] = useState([])
  const dataRef = useRef([])
  const startTimeRef = useRef(null)
  const lastPushRef = useRef(0)
  const [windowMs, setWindowMs] = useState(WINDOW_OPTIONS[2].value)

  useEffect(() => {
    const source = silab ?? sensorData?.silab
    if (!source) return

    const timestamp = Date.now()
    if (!startTimeRef.current) {
      startTimeRef.current = timestamp
    }
    if (timestamp - lastPushRef.current < THROTTLE_MS) {
      return
    }
    lastPushRef.current = timestamp
    const elapsedMs = timestamp - startTimeRef.current
    const elapsedSeconds = elapsedMs / 1000

    const speedValue = Number.isFinite(source.speed) ? parseFloat((source.speed * 3.6).toFixed(1)) : null
    const steeringRaw = toSteeringDegrees(source.steering)
    const steeringValue = Number.isFinite(steeringRaw) ? parseFloat(steeringRaw.toFixed(1)) : null
    const gasValue = Number.isFinite(source.acc_pedal) ? parseFloat(source.acc_pedal.toFixed(2)) : null
    const brakeValue = Number.isFinite(source.brake_pedal) ? parseFloat(source.brake_pedal.toFixed(2)) : null

    const newDataPoint = {
      time: elapsedSeconds,
      elapsedMs,
      speed: speedValue,
      steering: steeringValue,
      gas: gasValue,
      brake: brakeValue,
    }

    const trimmed = dataRef.current.filter((entry) => elapsedMs - entry.elapsedMs <= MAX_WINDOW_MS)
    dataRef.current = [...trimmed, newDataPoint].slice(-MAX_POINTS)
    const windowed = dataRef.current.filter((entry) => elapsedMs - entry.elapsedMs <= windowMs)
    setData(downsampleData(windowed, MAX_RENDER_POINTS))
  }, [sensorData, silab, windowMs])

  useEffect(() => {
    const latest = dataRef.current[dataRef.current.length - 1]
    if (!latest) {
      setData([])
      return
    }
    const windowed = dataRef.current.filter((entry) => latest.elapsedMs - entry.elapsedMs <= windowMs)
    setData(downsampleData(windowed, MAX_RENDER_POINTS))
  }, [windowMs])

  return (
    <div className="silab-line-chart">
      <div className="silab-line-chart-grid">
        <div className="silab-line-chart-section">
          <div className="silab-line-chart-title">Speed (km/h)</div>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} syncId="silab-line" syncMethod="value" margin={{ top: 6, right: 12, left: 18, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#dbe5ef" />
              <XAxis dataKey="time" stroke="#5a6b7a" tick={{ fontSize: 11 }} hide />
              <YAxis stroke="#5a6b7a" tick={{ fontSize: 11 }} width={52} unit="km/h" />
              <Tooltip contentStyle={{ backgroundColor: "#f9f9f9", border: "1px solid #cfd8e3" }} />
              <Line
                type="monotone"
                dataKey="speed"
                stroke="#1f8a46"
                strokeWidth={2.2}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="silab-line-chart-section">
          <div className="silab-line-chart-title">Steering (deg)</div>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} syncId="silab-line" syncMethod="value" margin={{ top: 6, right: 12, left: 18, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#dbe5ef" />
              <XAxis dataKey="time" stroke="#5a6b7a" tick={{ fontSize: 11 }} hide />
              <YAxis stroke="#5a6b7a" tick={{ fontSize: 11 }} width={52} unit="deg" />
              <Tooltip contentStyle={{ backgroundColor: "#f9f9f9", border: "1px solid #cfd8e3" }} />
              <Line
                type="monotone"
                dataKey="steering"
                stroke="#225f7a"
                strokeWidth={2.2}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="silab-line-chart-section">
          <div className="silab-line-chart-title">Gas pedal</div>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} syncId="silab-line" syncMethod="value" margin={{ top: 6, right: 12, left: 18, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#dbe5ef" />
              <XAxis dataKey="time" stroke="#5a6b7a" tick={{ fontSize: 11 }} hide />
              <YAxis stroke="#5a6b7a" tick={{ fontSize: 11 }} width={52} />
              <Tooltip contentStyle={{ backgroundColor: "#f9f9f9", border: "1px solid #cfd8e3" }} />
              <Line
                type="monotone"
                dataKey="gas"
                stroke="#f59e0b"
                strokeWidth={2.2}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="silab-line-chart-section">
          <div className="silab-line-chart-title">Brake pedal</div>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} syncId="silab-line" syncMethod="value" margin={{ top: 6, right: 12, left: 18, bottom: 6 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#dbe5ef" />
              <XAxis
                dataKey="time"
                stroke="#5a6b7a"
                tick={{ fontSize: 11 }}
                tickFormatter={formatElapsedSeconds}
              />
              <YAxis stroke="#5a6b7a" tick={{ fontSize: 11 }} width={52} />
              <Tooltip contentStyle={{ backgroundColor: "#f9f9f9", border: "1px solid #cfd8e3" }} />
              <Line
                type="monotone"
                dataKey="brake"
                stroke="#dc2626"
                strokeWidth={2.2}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="silab-line-chart-controls">
        <label className="silab-line-chart-label" htmlFor="silab-window">
          Window
        </label>
        <select
          id="silab-window"
          value={windowMs}
          onChange={(event) => setWindowMs(Number(event.target.value))}
        >
          {WINDOW_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}

export default SpeedChart
