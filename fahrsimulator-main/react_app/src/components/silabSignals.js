// Single source of truth for the SiLab signals that can be shown one-per-widget,
// either as a line chart or as a text value. Each entry knows how to read its
// value out of the raw silab payload, how to format it, and (for charts) its
// axis configuration.

const MAX_STEERING_RAD = 7.85
const MAX_STEERING_DEG = 450
const MAX_BRAKE_VALUE = 3.5

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function num(value) {
  return Number.isFinite(value) ? value : null
}

export function toSteeringDegrees(value) {
  if (!Number.isFinite(value)) return null
  const clamped = clamp(value, -MAX_STEERING_RAD, MAX_STEERING_RAD)
  return (clamped / MAX_STEERING_RAD) * MAX_STEERING_DEG
}

export function formatSteeringRotation(value) {
  if (value === 0 || value === null || value === undefined) return "0.00"
  const rotations = Math.abs(value / 360)
  const direction = value > 0 ? "L" : "R"
  return `${rotations.toFixed(2)} ${direction}`
}

export function formatElapsedSeconds(value) {
  if (!Number.isFinite(value)) return ""
  const totalSeconds = Math.max(0, Math.floor(value))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  const secondsLabel = minutes > 0 ? seconds.toString().padStart(2, "0") : seconds.toString()
  return `${minutes}:${secondsLabel}`
}

export function downsampleData(entries, maxPoints) {
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

const rotationTickFormatter = (value) => {
  if (value === 0) return "0.00"
  const rotations = Math.abs(value / 360)
  const direction = value > 0 ? "L" : "R"
  return `${rotations.toFixed(2)} ${direction}`
}

export const SILAB_SIGNALS = [
  {
    key: "speed",
    label: "Speed",
    unit: "km/h",
    color: "#1f8a46",
    yAxisWidth: 52,
    leftMargin: 6,
    store: (silab) => num(silab?.speed != null ? silab.speed * 3.6 : null),
    formatValue: (v) => (v == null ? "--" : v.toFixed(1)),
  },
  {
    key: "steering",
    label: "Steering",
    unit: "rotations",
    color: "#225f7a",
    yAxisWidth: 65,
    leftMargin: 6,
    domain: [-MAX_STEERING_DEG, MAX_STEERING_DEG],
    ticks: [-360, 0, 360],
    tickFormatter: rotationTickFormatter,
    store: (silab) => toSteeringDegrees(silab?.steering),
    formatValue: (v) => formatSteeringRotation(v),
  },
  {
    key: "gas",
    label: "Gas",
    unit: "",
    color: "#f59e0b",
    yAxisWidth: 52,
    leftMargin: 6,
    domain: [0, 1],
    ticks: [0, 0.5, 1],
    store: (silab) => num(silab?.acc_pedal),
    formatValue: (v) => (v == null ? "--" : v.toFixed(2)),
  },
  {
    key: "brake",
    label: "Brake",
    unit: "",
    color: "#dc2626",
    yAxisWidth: 52,
    leftMargin: 6,
    domain: [0, 1],
    ticks: [0, 0.5, 1],
    store: (silab) => num(silab?.brake_pedal != null ? silab.brake_pedal / MAX_BRAKE_VALUE : null),
    formatValue: (v) => (v == null ? "--" : v.toFixed(2)),
  },
]

const SILAB_SIGNAL_MAP = Object.fromEntries(SILAB_SIGNALS.map((s) => [s.key, s]))

export function getSilabSignal(key) {
  return SILAB_SIGNAL_MAP[key] || SILAB_SIGNALS[0]
}
