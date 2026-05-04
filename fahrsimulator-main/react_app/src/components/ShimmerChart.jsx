import {
  Area,
  AreaChart,
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
    key: "sdnn",
    aliases: ["SDNN"],
    label: "SDNN",
    unit: "ms",
    mode: "higher-better",
    low: 30,
    mid: 50,
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
    key: "hr",
    aliases: ["heart_rate", "bpm", "pulse"],
    label: "HR",
    unit: "bpm",
    mode: "range",
    low: 55,
    high: 95,
  },
  {
    key: "breathingrate",
    aliases: ["breathing_rate", "breaths_per_minute"],
    label: "Breathing",
    unit: "Hz",
    mode: "range",
    low: 0.12,
    high: 0.35,
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
    key: "breathingrate",
    aliases: ["breathing_rate", "breaths_per_minute"],
    label: "Breathing",
    unit: "Hz",
    format: (value) => `${(value * 60).toFixed(1)} breaths/min`,
  },
]

const ADVANCED_METRICS = [
  { label: "SDNN", keys: ["sdnn"], unit: "ms" },
  { label: "IBI", keys: ["ibi"], unit: "ms" },
  { label: "SDSD", keys: ["sdsd"], unit: "ms" },
  { label: "pNN20", keys: ["pnn20"], unit: "" },
  { label: "pNN50", keys: ["pnn50"], unit: "" },
  { label: "Breathing", keys: ["breathingrate"], unit: "Hz" },
  { label: "HR MAD", keys: ["hr_mad"], unit: "" },
  { label: "SD1", keys: ["sd1"], unit: "" },
  { label: "SD2", keys: ["sd2"], unit: "" },
  { label: "S", keys: ["s"], unit: "" },
  { label: "SD1/SD2", keys: ["sd1/sd2"], unit: "" },
]

const WINDOW_MS = 60_000
const MOCK_BASE_TIME = WINDOW_MS
const SERIES_COLORS = {
  sdnn: "#2f9d61",
  rmssd: "#2d5dff",
  hr: "#d84747",
  breathingrate: "#7b4eff",
}

function createMockShimmer(nowMs) {
  const t = nowMs / 1000
  const bpm = 74 + 7 * Math.sin(t * 0.42)
  const ibi = 60000 / Math.max(bpm, 1)
  const rmssd = 32 + 9 * Math.sin(t * 0.5 + 0.5)
  const sdnn = 45 + 10 * Math.sin(t * 0.35)
  const sdsd = Math.max(5, rmssd * 0.78 + 2.5 * Math.sin(t * 0.33))
  const pnn20 = Math.max(0, Math.min(1, 0.34 + 0.16 * Math.sin(t * 0.27)))
  const pnn50 = Math.max(0, Math.min(1, 0.18 + 0.11 * Math.sin(t * 0.21 + 0.3)))
  const hrMad = Math.max(10, 45 + 16 * Math.sin(t * 0.29 + 0.4))
  const sd1 = Math.max(1, rmssd / Math.sqrt(2))
  const sd2 = Math.max(sd1 + 1, sdnn * 1.18)

  return {
    bpm,
    heart_rate: bpm,
    ibi,
    sdnn,
    sdsd,
    rmssd,
    pnn20,
    pnn50,
    hr_mad: hrMad,
    sd1,
    sd2,
    s: Math.PI * sd1 * sd2,
    "sd1/sd2": sd1 / Math.max(sd2, 1e-6),
    breathingrate: Math.max(0.08, Math.min(0.45, 0.22 + 0.05 * Math.sin(t * 0.18))),
  }
}

function createMockHistory(nowMs) {
  const stepMs = 1000
  const startTime = nowMs - WINDOW_MS
  const history = []

  for (let timestamp = startTime; timestamp <= nowMs; timestamp += stepMs) {
    history.push({
      timestamp,
      ...createMockShimmer(timestamp),
    })
  }

  return history
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
  return `${value.toFixed(2)}${unit ? ` ${unit}` : ""}`
}

function ShimmerChart({ shimmer, running }) {
  const [history, setHistory] = useState([])
  const [now, setNow] = useState(MOCK_BASE_TIME)
  const latestValuesRef = useRef({})

  const hasTrendValues = useMemo(
    () => TREND_METRICS.some((metric) => Number.isFinite(getValue(shimmer, metric))),
    [shimmer],
  )

  const useMockFallback = running && (!shimmer || Object.keys(shimmer).length === 0 || !hasTrendValues)
  const shimmerPacket = useMemo(() => (useMockFallback ? createMockShimmer(now || 0) : shimmer || {}), [
    useMockFallback,
    now,
    shimmer,
  ])

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
      setNow(timestamp)

      const currentValues = latestValuesRef.current
      if (Object.keys(currentValues).length === 0) return

      setHistory((currentHistory) => {
        const nextHistory = [...currentHistory, { timestamp, ...currentValues }]
        return nextHistory.filter((entry) => timestamp - entry.timestamp <= WINDOW_MS)
      })
    }, 1000)

    return () => window.clearInterval(intervalId)
  }, [running])

  const primaryCards = useMemo(
    () =>
      PRIMARY_METRICS.map((metric) => ({
        ...metric,
        value: getValue(shimmerPacket, metric),
      })),
    [shimmerPacket],
  )

  const advancedRows = useMemo(
    () =>
      ADVANCED_METRICS.map((metric) => {
        const value = Number(
          metric.keys.map((key) => shimmerPacket?.[key]).find((item) => Number.isFinite(Number(item))),
        )
        return {
          ...metric,
          value: Number.isFinite(value) ? value : null,
        }
      }).filter((metric) => Number.isFinite(metric.value)),
    [shimmerPacket],
  )

  const data = useMemo(() => {
    const sourceHistory = !running ? [] : useMockFallback ? createMockHistory(MOCK_BASE_TIME) : history
    const cutoff = (useMockFallback ? MOCK_BASE_TIME : now) - WINDOW_MS

    return sourceHistory
      .filter((entry) => entry.timestamp >= cutoff)
      .map((entry) => ({
        ...entry,
        timeLabel: new Date(entry.timestamp).toLocaleTimeString([], {
          minute: "2-digit",
          second: "2-digit",
        }),
      }))
  }, [history, now, running, useMockFallback])

  const sdnnTrendData = useMemo(
    () =>
      data
        .map((entry) => ({
          timestamp: entry.timestamp,
          timeLabel: entry.timeLabel,
          sdnn: entry.sdnn,
        }))
        .filter((entry) => Number.isFinite(entry.sdnn)),
    [data],
  )

  const breathingTrendData = useMemo(
    () =>
      data
        .map((entry) => ({
          timestamp: entry.timestamp,
          timeLabel: entry.timeLabel,
          breathingrate: entry.breathingrate,
          breathing_wave: Math.sin(entry.timestamp / 1000 * 2.4) * (entry.breathingrate || 0),
        }))
        .filter((entry) => Number.isFinite(entry.breathingrate)),
    [data],
  )

  return (
    <div className="shimmer-chart-card">
      <div className="shimmer-chart-header">
        <strong>Last 60 seconds</strong>
        <span>
          {!running
            ? "No live data"
            : useMockFallback
              ? "Local mock preview data"
              : "Primary values + trend + research"}
        </span>
      </div>

      <div className="shimmer-section-title">
        <h4>Primary indicators</h4>
        <p>BPM, RMSSD and breathing give the fastest live overview.</p>
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
        <h4>SDNN trend</h4>
        <p>Longer-term stability over the last 60 seconds.</p>
      </div>

      <div className="shimmer-chart-wrap">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={sdnnTrendData} margin={{ top: 10, right: 12, left: 4, bottom: 4 }}>
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
            <Area
              type="monotone"
              dataKey="sdnn"
              name="sdnn"
              stroke={SERIES_COLORS.sdnn}
              fill={SERIES_COLORS.sdnn}
              fillOpacity={0.2}
              strokeWidth={2.5}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="shimmer-section-title">
        <h4>Breathing waveform</h4>
        <p>Live breathing rhythm over the same 60-second window.</p>
      </div>

      <div className="shimmer-chart-wrap">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={breathingTrendData} margin={{ top: 10, right: 12, left: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dbe5ef" />
            <XAxis dataKey="timeLabel" tick={{ fill: "#30475d", fontSize: 11 }} axisLine={{ stroke: "#c1cfdd" }} />
            <YAxis tick={{ fill: "#30475d", fontSize: 11 }} axisLine={{ stroke: "#c1cfdd" }} width={40} />
            <Tooltip
              labelFormatter={(label) => `Time: ${label}`}
              formatter={(value, name) => {
                if (name === "breathing_wave") {
                  return [Number(value).toFixed(2), "Breathing waveform"]
                }
                return [Number(value).toFixed(2), "Breathing rate"]
              }}
            />
            <Line
              type="monotone"
              dataKey="breathing_wave"
              name="breathing_wave"
              stroke={SERIES_COLORS.breathingrate}
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
          <span className="legend-dot" style={{ background: SERIES_COLORS.breathingrate }} />
          Breathing waveform
        </span>
      </div>

      <div className="shimmer-legend">
        <span className="legend-item">
          <span className="legend-dot" style={{ background: SERIES_COLORS.sdnn }} />
          SDNN trend
        </span>
      </div>

      <details className="shimmer-advanced-panel">
        <summary>Researcher corner</summary>
        <div className="shimmer-advanced-grid">
          {advancedRows.length === 0 ? (
            <div className="placeholder">No advanced metrics in current packet.</div>
          ) : (
            advancedRows.map((metric) => (
              <div className="shimmer-advanced-row" key={metric.label}>
                <span>{metric.label}</span>
                <strong>{formatMetricValue(metric.value, metric.unit)}</strong>
              </div>
            ))
          )}
        </div>
      </details>
    </div>
  )
}

export default ShimmerChart
