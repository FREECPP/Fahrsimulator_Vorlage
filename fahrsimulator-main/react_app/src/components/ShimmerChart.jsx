import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { useEffect, useMemo, useRef, useState } from "react"

const TREND_METRICS = [
  {
    key: "hr",
    aliases: ["heart_rate", "bpm", "pulse"],
    label: "HR",
    unit: "bpm",
    mode: "range",
    low: 55,
    high: 95,
  },
  {
    key: "rmssd",
    aliases: ["RMSSD"],
    label: "RMSSD",
    unit: "ms",
    mode: "higher-better",
    low: 20,
    mid: 40,
  },
  {
    key: "sdnn",
    aliases: ["SDNN"],
    label: "SDNN",
    unit: "ms",
    mode: "higher-better",
    low: 30,
    mid: 50,
  },
  {
    key: "skin_resistance",
    aliases: ["skin_conductance_resistance", "gsr_resistance", "skin_resistance"],
    label: "Skin resistance",
    unit: "ohm",
    mode: "range",
    low: 1000,
    high: 300000,
  },
]

const PRIMARY_METRICS = [
  {
    key: "hr",
    aliases: ["heart_rate", "bpm", "pulse"],
    label: "BPM",
    unit: "bpm",
    format: (value) => `${Math.round(value)} bpm`,
  },
  {
    key: "rmssd",
    aliases: ["RMSSD"],
    label: "RMSSD",
    unit: "ms",
  },
  {
    key: "sdnn",
    aliases: ["SDNN"],
    label: "SDNN",
    unit: "ms",
  },
  {
    key: "skin_resistance",
    aliases: ["skin_conductance_resistance", "gsr_resistance", "skin_resistance"],
    label: "Skin resistance",
    unit: "ohm",
    format: (value) => {
      if (!Number.isFinite(value)) return "-"
      if (value >= 1000) return `${(value / 1000).toFixed(1)} kOhm`
      return `${Math.round(value)} Ohm`
    },
  },
]

const WINDOW_MS = 60_000
const SERIES_COLORS = {
  sdnn: "#2f9d61",
  rmssd: "#2d5dff",
  hr: "#d84747",
  skin_resistance: "#b76b2d",
}

function getValue(packet, config) {
  const keys = [config.key, ...(config.aliases || [])]
  for (const key of keys) {
    const value = Number(packet?.[key])
    if (Number.isFinite(value)) return value
  }
  return null
}

function formatMetricValue(value, unit) {
  if (!Number.isFinite(value)) return "-"

  if (unit === "bpm") return `${Math.round(value)} ${unit}`
  if (unit === "ohm") {
    if (value >= 1000) return `${(value / 1000).toFixed(1)} kOhm`
    return `${Math.round(value)} Ohm`
  }
  return `${value.toFixed(2)}${unit ? ` ${unit}` : ""}`
}

function formatElapsed(ms) {
  if (!Number.isFinite(ms)) return "0:00"
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${seconds.toString().padStart(2, "0")}`
}

function ShimmerChart({ shimmer, running }) {
  const [history, setHistory] = useState([])
  const [now, setNow] = useState(0)
  const latestValuesRef = useRef({})
  const startTimeRef = useRef(null)

  const shimmerPacket = useMemo(() => shimmer || {}, [shimmer])

  const latestValues = useMemo(() => {
    const nextValues = {}
    for (const config of TREND_METRICS) {
      const value = getValue(shimmerPacket, config)
      if (Number.isFinite(value)) {
        nextValues[config.key] = value
      }
    }
    return nextValues
  }, [shimmerPacket])

  useEffect(() => {
    latestValuesRef.current = latestValues
  }, [latestValues])

  useEffect(() => {
    if (!running) return

    const intervalId = window.setInterval(() => {
      const timestamp = Date.now()
      if (!startTimeRef.current) {
        startTimeRef.current = timestamp
      }

      const elapsedMs = timestamp - startTimeRef.current
      setNow(elapsedMs)

      const currentValues = latestValuesRef.current
      if (Object.keys(currentValues).length === 0) return

      setHistory((currentHistory) => {
        const nextHistory = [...currentHistory, { elapsedMs, ...currentValues }]
        return nextHistory.filter((entry) => elapsedMs - entry.elapsedMs <= WINDOW_MS)
      })
    }, 1000)

    return () => window.clearInterval(intervalId)
  }, [running])

  useEffect(() => {
    if (running) return
    startTimeRef.current = null
    setNow(0)
  }, [running])

  const primaryCards = useMemo(
    () =>
      PRIMARY_METRICS.map((metric) => ({
        ...metric,
        value: getValue(shimmerPacket, metric),
      })),
    [shimmerPacket],
  )

  const data = useMemo(() => {
    const sourceHistory = !running ? [] : history
    const cutoff = now - WINDOW_MS

    return sourceHistory
      .filter((entry) => entry.elapsedMs >= cutoff)
      .map((entry) => ({
        ...entry,
        timeLabel: formatElapsed(entry.elapsedMs),
      }))
  }, [history, now, running])

  const hrTrendData = useMemo(
    () =>
      data
        .map((entry) => ({
          elapsedMs: entry.elapsedMs,
          timeLabel: entry.timeLabel,
          hr: entry.hr,
        }))
        .filter((entry) => Number.isFinite(entry.hr)),
    [data],
  )

  const hrvTrendData = useMemo(
    () =>
      data
        .map((entry) => ({
          elapsedMs: entry.elapsedMs,
          timeLabel: entry.timeLabel,
          rmssd: entry.rmssd,
          sdnn: entry.sdnn,
        }))
        .filter((entry) => Number.isFinite(entry.rmssd) || Number.isFinite(entry.sdnn)),
    [data],
  )

  return (
    <div className="shimmer-chart-card">
      <div className="shimmer-chart-header">
        <strong>Last 60 seconds</strong>
        <span>
          {!running
            ? "No live data"
            : "Live data"}
        </span>
      </div>

      <div className="shimmer-section-title">
        <h4>Primary indicators</h4>
      </div>

      <div className="shimmer-primary-grid">
        {primaryCards.map((metric) => (
          <article className="shimmer-primary-card" key={metric.key}>
            <span>{metric.label}</span>
            <strong>
              {typeof metric.format === "function"
                ? Number.isFinite(metric.value)
                  ? metric.format(metric.value)
                  : "-"
                : formatMetricValue(metric.value, metric.unit)}
            </strong>
          </article>
        ))}
      </div>

      <div className="shimmer-section-title">
        <h4>Heart rate trend</h4>
        <p>Live BPM evolution over the last 60 seconds.</p>
      </div>

      <div className="shimmer-chart-wrap">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={hrTrendData} margin={{ top: 10, right: 12, left: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dbe5ef" />
            <XAxis dataKey="timeLabel" tick={{ fill: "#30475d", fontSize: 11 }} axisLine={{ stroke: "#c1cfdd" }} />
            <YAxis tick={{ fill: "#30475d", fontSize: 11 }} axisLine={{ stroke: "#c1cfdd" }} width={40} />
            <Tooltip
              labelFormatter={(label) => `Time: ${label}`}
              formatter={(value, name) => {
                const config = TREND_METRICS.find((item) => item.key === name)
                const valueLabel = Number(value).toFixed(2)
                return [`${valueLabel} ${config?.unit || ""}`, config?.label || name]
              }}
            />
            <Line
              type="monotone"
              dataKey="hr"
              name="hr"
              stroke={SERIES_COLORS.hr}
              strokeWidth={2.4}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="shimmer-section-title">
        <h4>HRV trend</h4>
        <p>RMSSD and SDNN stability over the last 60 seconds.</p>
      </div>

      <div className="shimmer-chart-wrap">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={hrvTrendData} margin={{ top: 10, right: 12, left: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dbe5ef" />
            <XAxis dataKey="timeLabel" tick={{ fill: "#30475d", fontSize: 11 }} axisLine={{ stroke: "#c1cfdd" }} />
            <YAxis tick={{ fill: "#30475d", fontSize: 11 }} axisLine={{ stroke: "#c1cfdd" }} width={40} />
            <Tooltip
              labelFormatter={(label) => `Time: ${label}`}
              formatter={(value, name) => {
                const config = TREND_METRICS.find((item) => item.key === name)
                return [Number(value).toFixed(2), config?.label || name]
              }}
            />
            <Line
              type="monotone"
              dataKey="rmssd"
              name="rmssd"
              stroke={SERIES_COLORS.rmssd}
              strokeWidth={2.4}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="sdnn"
              name="sdnn"
              stroke={SERIES_COLORS.sdnn}
              strokeWidth={2.4}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="shimmer-legend">
        <span className="legend-item">
          <span className="legend-dot" style={{ background: SERIES_COLORS.rmssd }} />
          RMSSD
        </span>
        <span className="legend-item">
          <span className="legend-dot" style={{ background: SERIES_COLORS.sdnn }} />
          SDNN
        </span>
        <span className="legend-item">
          <span className="legend-dot" style={{ background: SERIES_COLORS.hr }} />
          Heart rate
        </span>
      </div>

    </div>
  )
}

export default ShimmerChart
