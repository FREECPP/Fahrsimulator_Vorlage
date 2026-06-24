export const SENSOR_WIDGETS = [
  {
    key: "silab",
    label: "SiLab",
    defaultMode: "cockpit",
    modes: [
      { value: "cockpit", label: "Cockpit" },
      { value: "line", label: "Signal" },
      { value: "raw", label: "Raw" },
    ],
  },
  {
    key: "shimmer",
    label: "Shimmer",
    defaultMode: "line",
    modes: [
      { value: "line", label: "Signal" },
      { value: "raw", label: "Raw" },
    ],
  },
  {
    key: "eyetracker",
    label: "Eyetracker",
    defaultMode: "gaze",
    modes: [
      { value: "gaze", label: "Gaze" },
      { value: "raw", label: "Raw" },
    ],
  },
  {
    key: "tof",
    label: "ToF Camera",
    defaultMode: "image",
    modes: [
      { value: "image", label: "Image" },
    ],
  },
  {
    key: "rgb_front",
    label: "RGB Front",
    defaultMode: "image",
    modes: [
      { value: "image", label: "Image" },
    ],
  },
  {
    key: "rgb_back",
    label: "RGB Back",
    defaultMode: "image",
    modes: [
      { value: "image", label: "Image" },
    ],
  },
]

const SENSOR_WIDGET_MAP = Object.fromEntries(SENSOR_WIDGETS.map((item) => [item.key, item]))

export function getSensorConfig(view) {
  return SENSOR_WIDGET_MAP[view]
}

export function getSensorTitle(view) {
  return getSensorConfig(view)?.label || view
}

export function getDefaultMode(view) {
  return getSensorConfig(view)?.defaultMode || "raw"
}

export function getModeOptions(view) {
  return getSensorConfig(view)?.modes || [{ value: "raw", label: "Raw" }]
}

export function getNormalizedMode(view, requestedMode) {
  const options = getModeOptions(view)
  if (options.some((option) => option.value === requestedMode)) return requestedMode
  return getDefaultMode(view)
}
