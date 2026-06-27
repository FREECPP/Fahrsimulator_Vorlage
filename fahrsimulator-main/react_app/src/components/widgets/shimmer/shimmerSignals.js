// Single source of truth for the Shimmer signals that can be shown one-per-widget,
// either as a line chart or as a text value. Mirrors silabSignals: each entry
// knows how to read its value out of the raw shimmer payload (with a few aliases
// for differing backend field names), how to format it, and its axis config.

const ohmTickFormatter = (value) => {
  if (!Number.isFinite(value)) return ""
  if (Math.abs(value) >= 1000) return `${Math.round(value / 1000)}k`
  return `${Math.round(value)}`
}

function formatOhm(value) {
  if (!Number.isFinite(value)) return "--"
  if (value >= 1000) return `${(value / 1000).toFixed(1)} kOhm`
  return `${Math.round(value)} Ohm`
}

export const SHIMMER_SIGNALS = [
  {
    key: "hr",
    aliases: ["heart_rate", "bpm", "pulse"],
    label: "Heart rate",
    unit: "bpm",
    color: "#d84747",
    yAxisWidth: 32,
    formatValue: (v) => (Number.isFinite(v) ? `${Math.round(v)}` : "--"),
  },
  {
    key: "rmssd",
    aliases: ["RMSSD"],
    label: "RMSSD",
    unit: "ms",
    color: "#2d5dff",
    yAxisWidth: 38,
    formatValue: (v) => (Number.isFinite(v) ? v.toFixed(1) : "--"),
  },
  {
    key: "sdnn",
    aliases: ["SDNN"],
    label: "SDNN",
    unit: "ms",
    color: "#2f9d61",
    yAxisWidth: 38,
    formatValue: (v) => (Number.isFinite(v) ? v.toFixed(1) : "--"),
  },
  {
    key: "skin_resistance",
    aliases: ["skin_conductance_resistance", "gsr_resistance"],
    label: "Skin resistance",
    unit: "",
    color: "#b76b2d",
    yAxisWidth: 42,
    tickFormatter: ohmTickFormatter,
    formatValue: formatOhm,
  },
]

const SHIMMER_SIGNAL_MAP = Object.fromEntries(SHIMMER_SIGNALS.map((s) => [s.key, s]))

export function getShimmerSignal(key) {
  return SHIMMER_SIGNAL_MAP[key] || SHIMMER_SIGNALS[0]
}

// Read a signal's value out of a raw shimmer payload, trying each alias.
export function getShimmerValue(packet, signal) {
  const keys = [signal.key, ...(signal.aliases || [])]
  for (const key of keys) {
    const value = Number(packet?.[key])
    if (Number.isFinite(value)) return value
  }
  return null
}

// Build a single store point from a raw shimmer payload. Returns null when the
// payload carries none of the tracked signals, so the caller can skip it.
export function buildShimmerPoint(shimmer, elapsedMs) {
  const point = { elapsedMs }
  let hasValue = false
  for (const signal of SHIMMER_SIGNALS) {
    const value = getShimmerValue(shimmer, signal)
    point[signal.key] = value
    if (Number.isFinite(value)) hasValue = true
  }
  return hasValue ? point : null
}
