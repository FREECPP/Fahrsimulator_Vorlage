import { useEffect, useRef, useState, memo } from "react"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts"
import { telemetryStore, THROTTLE_MS } from "../utils/telemetryStore"

const MAX_STEERING_RAD = 7.85
const MAX_STEERING_DEG = 450
const MAX_BRAKE_VALUE = 3.5
const STEERING_TICKS = [
  -360,
  0,
  360,
]
const RENDER_THROTTLE_MS = 500
const MAX_RENDER_POINTS = 300
const MIN_WINDOW_MINUTES = 1
const MAX_WINDOW_MINUTES = 30
const DEFAULT_WINDOW_MINUTES = 5
const MAX_WINDOW_MS = MAX_WINDOW_MINUTES * 60 * 1000

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function toSteeringDegrees(value) {
  if (!Number.isFinite(value)) return null
  const clamped = clamp(value, -MAX_STEERING_RAD, MAX_STEERING_RAD)
  return (clamped / MAX_STEERING_RAD) * MAX_STEERING_DEG
}

function formatSteeringRotation(value) {
  if (value === 0 || value === null) return "0.00"
  const rotations = Math.abs(value / 360)
  const direction = value > 0 ? "L" : "R"
  return `${rotations.toFixed(2)} ${direction}`
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
  const result = []
  for (let i = 0; i < entries.length; i += stride) {
    result.push(entries[i])
  }
  if (result.length > 0 && result[result.length - 1] !== entries[entries.length - 1]) {
    result.push(entries[entries.length - 1])
  }
  return result
}

const SpeedChartInner = memo(function SpeedChartInner({ data, windowStart, windowEnd, currentValues }) {
  return (
    <div className="silab-line-chart-grid">
      <div className="silab-line-chart-section">
        <div className="silab-line-chart-title">
          Speed (km/h) <span className="silab-chart-current-value">{currentValues.speed ?? "--"}</span>
        </div>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} syncId="silab-line" syncMethod="value" margin={{ top: 10, right: 12, left: 60, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dbe5ef" />
            <XAxis
              dataKey="elapsedMs"
              type="number"
              domain={[windowStart, windowEnd]}
              allowDataOverflow
              stroke="#5a6b7a"
              tick={{ fontSize: 11 }}
              tickFormatter={(val) => formatElapsedSeconds(val / 1000)}
              hide
            />
            <YAxis stroke="#5a6b7a" tick={{ fontSize: 11 }} width={52} unit="km/h" />
            <Tooltip
              contentStyle={{ backgroundColor: "#f9f9f9", border: "1px solid #cfd8e3" }}
              labelFormatter={(val) => formatElapsedSeconds(val / 1000)}
            />
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
        <div className="silab-line-chart-title">
          Steering (rotations) <span className="silab-chart-current-value">{formatSteeringRotation(currentValues.steering)}</span>
        </div>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} syncId="silab-line" syncMethod="value" margin={{ top: 10, right: 12, left: 60, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dbe5ef" />
            <XAxis
              dataKey="elapsedMs"
              type="number"
              domain={[windowStart, windowEnd]}
              allowDataOverflow
              stroke="#5a6b7a"
              tick={{ fontSize: 11 }}
              tickFormatter={(val) => formatElapsedSeconds(val / 1000)}
              hide
            />
            <YAxis
              stroke="#5a6b7a"
              tick={{ fontSize: 11 }}
              width={65}
              domain={[-MAX_STEERING_DEG, MAX_STEERING_DEG]}
              ticks={STEERING_TICKS}
              interval={0}
              tickFormatter={(value) => {
                if (value === 0) return "0.00"
                const rotations = Math.abs(value / 360)
                const direction = value > 0 ? "L" : "R"
                return `${rotations.toFixed(2)} ${direction}`
              }}
            />
            <ReferenceLine y={0} stroke="#5a6b7a" strokeWidth={1} strokeDasharray="3 3" />
            <Tooltip
              contentStyle={{ backgroundColor: "#f9f9f9", border: "1px solid #cfd8e3" }}
              labelFormatter={(val) => formatElapsedSeconds(val / 1000)}
              formatter={(value, name) => {
                if (name === "steering") {
                  return [formatSteeringRotation(value), "Steering"]
                }
                return [value, name]
              }}
            />
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
        <div className="silab-line-chart-title">
          Gas pedal <span className="silab-chart-current-value">{currentValues.gas ?? "--"}</span>
        </div>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} syncId="silab-line" syncMethod="value" margin={{ top: 10, right: 12, left: 60, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dbe5ef" />
            <XAxis
              dataKey="elapsedMs"
              type="number"
              domain={[windowStart, windowEnd]}
              allowDataOverflow
              stroke="#5a6b7a"
              tick={{ fontSize: 11 }}
              tickFormatter={(val) => formatElapsedSeconds(val / 1000)}
              hide
            />
            <YAxis stroke="#5a6b7a" tick={{ fontSize: 11 }} width={52} domain={[0, 1]} ticks={[0, 0.5, 1]} interval={0} />
            <Tooltip
              contentStyle={{ backgroundColor: "#f9f9f9", border: "1px solid #cfd8e3" }}
              labelFormatter={(val) => formatElapsedSeconds(val / 1000)}
            />
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
        <div className="silab-line-chart-title">
          Brake pedal <span className="silab-chart-current-value">{currentValues.brake ?? "--"}</span>
        </div>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} syncId="silab-line" syncMethod="value" margin={{ top: 10, right: 12, left: 60, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dbe5ef" />
            <XAxis
              dataKey="elapsedMs"
              type="number"
              domain={[windowStart, windowEnd]}
              allowDataOverflow
              stroke="#5a6b7a"
              tick={{ fontSize: 11 }}
              tickFormatter={(val) => formatElapsedSeconds(val / 1000)}
            />
            <YAxis stroke="#5a6b7a" tick={{ fontSize: 11 }} width={52} domain={[0, 1]} ticks={[0, 0.5, 1]} interval={0} />
            <Tooltip
              contentStyle={{ backgroundColor: "#f9f9f9", border: "1px solid #cfd8e3" }}
              labelFormatter={(val) => formatElapsedSeconds(val / 1000)}
            />
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
  )
})

const SpeedChart = memo(function SpeedChart({ silab, sensorData }) {
  const [data, setData] = useState([])
  const [latestTime, setLatestTime] = useState(0)
  const [currentValues, setCurrentValues] = useState({
    speed: null,
    steering: null,
    gas: null,
    brake: null,
  })
  const lastPushRef = useRef(0)
  const lastRenderRef = useRef(0)
  const [windowMinutes, setWindowMinutes] = useState(DEFAULT_WINDOW_MINUTES)
  const windowMsRef = useRef(DEFAULT_WINDOW_MINUTES * 60 * 1000)

  useEffect(() => {
    const source = silab ?? sensorData?.silab
    if (!source) return

    const timestamp = Date.now()
    const startTime = telemetryStore.initStartTime()
    if (timestamp - lastPushRef.current < THROTTLE_MS) {
      return
    }
    lastPushRef.current = timestamp
    const elapsedMs = timestamp - startTime
    const elapsedSeconds = elapsedMs / 1000

    const speedValue = Number.isFinite(source.speed) ? parseFloat((source.speed * 3.6).toFixed(1)) : null
    const steeringRaw = toSteeringDegrees(source.steering)
    const steeringValue = Number.isFinite(steeringRaw) ? parseFloat(steeringRaw.toFixed(1)) : null
    const gasValue = Number.isFinite(source.acc_pedal) ? parseFloat(source.acc_pedal.toFixed(2)) : null
    const brakeValue = Number.isFinite(source.brake_pedal) ? parseFloat((source.brake_pedal / MAX_BRAKE_VALUE).toFixed(2)) : null

    const newDataPoint = {
      time: elapsedSeconds,
      elapsedMs,
      speed: speedValue,
      steering: steeringValue,
      gas: gasValue,
      brake: brakeValue,
    }

    telemetryStore.addDataPoint(newDataPoint)

    if (timestamp - lastRenderRef.current < RENDER_THROTTLE_MS) {
      return
    }
    lastRenderRef.current = timestamp

    const currentWindowMs = windowMsRef.current
    const minElapsedMs = elapsedMs - currentWindowMs

    const allData = telemetryStore.getData()
    let low = 0
    let high = allData.length - 1
    let startIndex = allData.length

    while (low <= high) {
      const mid = Math.floor((low + high) / 2)
      if (allData[mid].elapsedMs >= minElapsedMs) {
        startIndex = mid
        high = mid - 1
      } else {
        low = mid + 1
      }
    }

    const windowed = allData.slice(startIndex)
    const downsampled = downsampleData(windowed, MAX_RENDER_POINTS)

    requestAnimationFrame(() => {
      setData(downsampled)
      setLatestTime(elapsedMs)
      setCurrentValues({
        speed: speedValue,
        steering: steeringValue,
        gas: gasValue,
        brake: brakeValue,
      })
    })
  }, [sensorData, silab])

  const windowMs = windowMinutes * 60 * 1000
  const windowStart = Math.max(0, latestTime - windowMs)
  const windowEnd = Math.max(latestTime, windowMs)

  return (
    <div className="silab-line-chart">
      <SpeedChartInner
        data={data}
        windowStart={windowStart}
        windowEnd={windowEnd}
        currentValues={currentValues}
      />
      <div className="silab-line-chart-controls">
        <label className="silab-line-chart-label" htmlFor="silab-window-minutes">
          Window (min)
        </label>
        <input
          id="silab-window-minutes"
          type="number"
          min={MIN_WINDOW_MINUTES}
          max={MAX_WINDOW_MINUTES}
          step="1"
          value={windowMinutes}
          onChange={(event) => {
            const nextValue = Number(event.target.value)
            if (!Number.isFinite(nextValue)) return
            const clamped = clamp(nextValue, MIN_WINDOW_MINUTES, MAX_WINDOW_MINUTES)
            const nextWindowMs = clamped * 60 * 1000
            windowMsRef.current = nextWindowMs
            setWindowMinutes(clamped)

            const allData = telemetryStore.getData()
            const latest = allData[allData.length - 1]
            if (!latest) {
              setData([])
              return
            }

            const minElapsedMs = latest.elapsedMs - nextWindowMs
            let low = 0
            let high = allData.length - 1
            let startIndex = allData.length
            while (low <= high) {
              const mid = Math.floor((low + high) / 2)
              if (allData[mid].elapsedMs >= minElapsedMs) {
                startIndex = mid
                high = mid - 1
              } else {
                low = mid + 1
              }
            }
            const windowed = allData.slice(startIndex)
            setData(downsampleData(windowed, MAX_RENDER_POINTS))
          }}
        />
      </div>
    </div>
  )
})

export default SpeedChart
