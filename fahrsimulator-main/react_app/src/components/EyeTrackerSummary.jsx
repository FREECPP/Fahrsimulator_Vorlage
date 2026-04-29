import { useEffect, useMemo, useRef, useState } from "react"

const TRAIL_WINDOW_MS = 60_000

function isFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value)
}

function clamp01(value) {
  return Math.max(0, Math.min(1, value))
}

function getGazePoint(eyetracker) {
  const x = Number(eyetracker?.x)
  const y = Number(eyetracker?.y)
  if (Number.isFinite(x) && Number.isFinite(y)) {
    return { x: clamp01(x), y: clamp01(y), valid: true }
  }

  const left = eyetracker?.left_gaze_point_on_display_area
  const right = eyetracker?.right_gaze_point_on_display_area

  const xCandidates = []
  const yCandidates = []
  if (Array.isArray(left) && left.length >= 2) {
    const lx = Number(left[0])
    const ly = Number(left[1])
    if (Number.isFinite(lx) && Number.isFinite(ly)) {
      xCandidates.push(lx)
      yCandidates.push(ly)
    }
  }
  if (Array.isArray(right) && right.length >= 2) {
    const rx = Number(right[0])
    const ry = Number(right[1])
    if (Number.isFinite(rx) && Number.isFinite(ry)) {
      xCandidates.push(rx)
      yCandidates.push(ry)
    }
  }

  if (!xCandidates.length) {
    return { x: null, y: null, valid: false }
  }

  return {
    x: clamp01(xCandidates.reduce((acc, item) => acc + item, 0) / xCandidates.length),
    y: clamp01(yCandidates.reduce((acc, item) => acc + item, 0) / yCandidates.length),
    valid: true,
  }
}

function getPupilLeft(eyetracker) {
  const direct = Number(eyetracker?.pupil_left)
  if (Number.isFinite(direct)) return direct
  const raw = Number(eyetracker?.left_pupil_diameter)
  return Number.isFinite(raw) ? raw : null
}

function getPupilRight(eyetracker) {
  const direct = Number(eyetracker?.pupil_right)
  if (Number.isFinite(direct)) return direct
  const raw = Number(eyetracker?.right_pupil_diameter)
  return Number.isFinite(raw) ? raw : null
}

function classifyAoi(point) {
  if (!point || !point.valid) return "unknown"

  if (point.y > 0.64 && point.x >= 0.3 && point.x <= 0.7) return "cluster"
  if (point.y < 0.28 && (point.x <= 0.18 || point.x >= 0.82)) return "mirrors"
  if (point.y <= 0.62 && point.x >= 0.18 && point.x <= 0.82) return "road"
  return "off_road"
}

function formatValue(value, digits = 2) {
  return Number.isFinite(value) ? value.toFixed(digits) : "-"
}

function EyeTrackerSummary({ eyetracker, running }) {
  const [trail, setTrail] = useState([])
  const [nowMs, setNowMs] = useState(() => Date.now())
  const gazePointRef = useRef({ x: null, y: null, valid: false })
  const runningRef = useRef(running)

  const gazePoint = useMemo(() => getGazePoint(eyetracker), [eyetracker])

  useEffect(() => {
    gazePointRef.current = gazePoint
  }, [gazePoint])

  useEffect(() => {
    runningRef.current = running
  }, [running])

  useEffect(() => {
    const timer = window.setInterval(() => {
      const timestamp = Date.now()
      setNowMs(timestamp)

      setTrail((current) => {
        if (!runningRef.current) {
          return current.length > 0 ? [] : current
        }

        const point = gazePointRef.current
        if (!point.valid) {
          return current.filter((entry) => timestamp - entry.timestamp <= TRAIL_WINDOW_MS)
        }

        const withCurrent = [...current, { ...point, timestamp }]
        return withCurrent.filter((entry) => timestamp - entry.timestamp <= TRAIL_WINDOW_MS)
      })
    }, 500)
    return () => window.clearInterval(timer)
  }, [])

  const visibleTrail = useMemo(() => (running ? trail : []), [running, trail])

  const latestPoint = visibleTrail[visibleTrail.length - 1]
  const lastSampleAgeMs = latestPoint ? nowMs - latestPoint.timestamp : null

  const trackingStatus = useMemo(() => {
    if (!running) return { label: "Simulation stopped", className: "idle" }
    if (!latestPoint) return { label: "No gaze samples", className: "bad" }
    if (lastSampleAgeMs <= 700) return { label: "Good", className: "ok" }
    if (lastSampleAgeMs <= 2200) return { label: "Degraded", className: "idle" }
    return { label: "Lost", className: "bad" }
  }, [lastSampleAgeMs, latestPoint, running])

  const pupilLeft = getPupilLeft(eyetracker)
  const pupilRight = getPupilRight(eyetracker)

  const aoiStats = useMemo(() => {
    const counts = {
      road: 0,
      mirrors: 0,
      cluster: 0,
      off_road: 0,
      unknown: 0,
    }

    for (const point of visibleTrail) {
      counts[classifyAoi(point)] += 1
    }

    const total = visibleTrail.length || 1
    return [
      { key: "road", label: "Road", percent: Math.round((counts.road / total) * 100) },
      { key: "mirrors", label: "Mirrors", percent: Math.round((counts.mirrors / total) * 100) },
      { key: "cluster", label: "Cluster", percent: Math.round((counts.cluster / total) * 100) },
      { key: "off_road", label: "Off-road", percent: Math.round((counts.off_road / total) * 100) },
    ]
  }, [visibleTrail])

  const markerStyle = {
    left: `${((latestPoint?.x ?? 0.5) * 100).toFixed(2)}%`,
    top: `${((latestPoint?.y ?? 0.5) * 100).toFixed(2)}%`,
  }

  return (
    <div className="eyetracker-card">
      <div className="eyetracker-header">
        <strong>Driver gaze</strong>
        <span className={trackingStatus.className}>{trackingStatus.label}</span>
      </div>

      <div className="eyetracker-map">
        <div className="eyetracker-aoi-grid" />
        {visibleTrail.map((point, index) => (
          <span
            key={`${point.timestamp}-${index}`}
            className="eyetracker-trail-dot"
            style={{
              left: `${(point.x * 100).toFixed(2)}%`,
              top: `${(point.y * 100).toFixed(2)}%`,
              opacity: Math.max(0.15, (index + 1) / Math.max(1, visibleTrail.length)),
            }}
          />
        ))}
        <span className="eyetracker-live-dot" style={markerStyle} />
      </div>

      <div className="eyetracker-metrics">
        <div className="status-row">
          <span>Gaze X / Y</span>
          <strong>
            {formatValue(latestPoint?.x, 3)} / {formatValue(latestPoint?.y, 3)}
          </strong>
        </div>
        <div className="status-row">
          <span>Pupil Left / Right</span>
          <strong>
            {formatValue(pupilLeft, 2)} / {formatValue(pupilRight, 2)}
          </strong>
        </div>
        <div className="status-row">
          <span>Last sample age</span>
          <strong>{isFiniteNumber(lastSampleAgeMs) ? `${Math.round(lastSampleAgeMs)} ms` : "-"}</strong>
        </div>
      </div>

      <div className="eyetracker-aoi-panel">
        <h4>AOI over last 60s</h4>
        <div className="eyetracker-aoi-list">
          {aoiStats.map((item) => (
            <div className="eyetracker-aoi-row" key={item.key}>
              <span>{item.label}</span>
              <div className="eyetracker-aoi-bar-wrap">
                <div className="eyetracker-aoi-bar" style={{ width: `${item.percent}%` }} />
              </div>
              <strong>{item.percent}%</strong>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default EyeTrackerSummary