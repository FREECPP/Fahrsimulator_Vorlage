import { useEffect, useRef, useState, memo } from "react"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
import { shimmerStore } from "../../../utils/shimmerStore"
import { downsampleData, formatElapsedSeconds } from "../silab/silabSignals"

const RENDER_THROTTLE_MS = 500
const MAX_RENDER_POINTS = 300
const MIN_WINDOW_MINUTES = 1
const MAX_WINDOW_MINUTES = 30
const DEFAULT_WINDOW_MINUTES = 5

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

// Slice the rolling shimmer buffer to the requested window (binary search on the
// sorted elapsedMs) and downsample for rendering. Mirrors SilabSignalChart.
function windowedData(allData, windowMs) {
  if (allData.length === 0) return { data: [], latest: 0 }

  const latest = allData[allData.length - 1].elapsedMs
  const minElapsedMs = latest - windowMs

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

  return {
    data: downsampleData(allData.slice(startIndex), MAX_RENDER_POINTS, startIndex),
    latest,
  }
}

const ShimmerSignalChart = memo(function ShimmerSignalChart({ signal }) {
  const [data, setData] = useState([])
  const [latestTime, setLatestTime] = useState(0)
  const [windowMinutes, setWindowMinutes] = useState(DEFAULT_WINDOW_MINUTES)
  // Raw text of the field, so it can be cleared/edited freely; the applied
  // windowMinutes is only normalized on blur.
  const [windowInput, setWindowInput] = useState(String(DEFAULT_WINDOW_MINUTES))
  const lastRenderRef = useRef(0)

  const windowMs = windowMinutes * 60 * 1000

  // Subscribe to the shared store (ingestion lives in Dashboard, so this
  // component only reads). Throttled re-render to keep it light.
  useEffect(() => {
    const refresh = (force = false) => {
      const now = Date.now()
      if (!force && now - lastRenderRef.current < RENDER_THROTTLE_MS) return
      lastRenderRef.current = now
      const { data: windowed, latest } = windowedData(shimmerStore.getData(), windowMs)
      setData(windowed)
      setLatestTime(latest)
    }

    refresh(true)
    const unsubscribe = shimmerStore.subscribe(() => refresh(false))
    return unsubscribe
  }, [windowMs])

  const windowStart = Math.max(0, latestTime - windowMs)
  const windowEnd = Math.max(latestTime, windowMs)

  const currentRaw = data.length > 0 ? data[data.length - 1][signal.key] : null
  const currentValue = Number.isFinite(currentRaw) ? signal.formatValue(currentRaw) : "--"

  return (
    <div className="silab-line-chart">
      <div className="silab-line-chart-section">
        <div className="silab-line-chart-title">
          {signal.label}
          <span className="silab-chart-current-value">
            {currentValue}{signal.unit ? ` ${signal.unit}` : ""}
          </span>
        </div>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 6, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dbe5ef" />
            <XAxis
              dataKey="elapsedMs"
              type="number"
              domain={[windowStart, windowEnd]}
              allowDataOverflow
              stroke="#5a6b7a"
              tick={{ fontSize: 11 }}
              height={18}
              tickMargin={3}
              tickFormatter={(val) => formatElapsedSeconds(val / 1000)}
            />
            <YAxis
              stroke="#5a6b7a"
              tick={{ fontSize: 11 }}
              width={signal.yAxisWidth}
              domain={signal.domain}
              ticks={signal.ticks}
              interval={signal.ticks ? 0 : undefined}
              tickFormatter={signal.tickFormatter}
            />
            <Tooltip
              contentStyle={{ backgroundColor: "#f9f9f9", border: "1px solid #cfd8e3" }}
              labelFormatter={(val) => formatElapsedSeconds(val / 1000)}
              formatter={(value) => [signal.formatValue(value), signal.label]}
            />
            <Line
              type="monotone"
              dataKey={signal.key}
              stroke={signal.color}
              strokeWidth={2.2}
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div
        className="silab-line-chart-controls"
        title="Window (minutes)"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <input
          id={`shimmer-window-${signal.key}`}
          type="number"
          min={MIN_WINDOW_MINUTES}
          max={MAX_WINDOW_MINUTES}
          step="1"
          value={windowInput}
          onChange={(event) => {
            const raw = event.target.value
            setWindowInput(raw)
            if (raw === "") return
            const nextValue = Number(raw)
            if (!Number.isFinite(nextValue)) return
            setWindowMinutes(clamp(nextValue, MIN_WINDOW_MINUTES, MAX_WINDOW_MINUTES))
          }}
          onBlur={() => {
            const nextValue = Number(windowInput)
            const normalized = Number.isFinite(nextValue) && windowInput !== ""
              ? clamp(nextValue, MIN_WINDOW_MINUTES, MAX_WINDOW_MINUTES)
              : windowMinutes
            setWindowMinutes(normalized)
            setWindowInput(String(normalized))
          }}
        />
        <span className="silab-line-chart-label">min</span>
      </div>
    </div>
  )
})

export default ShimmerSignalChart
