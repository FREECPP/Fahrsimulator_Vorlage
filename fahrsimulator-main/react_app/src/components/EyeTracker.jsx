import { useEffect, useMemo, useRef, useState } from "react"

const TRAIL_WINDOW_MS = 60_000

const DISPLAY_AREA_BOUNDS = {
  left: 0.0,
  right: 1.0,
  top: 0.0,
  bottom: 1.0,
  invertY: false,
}

function clamp01(value) {
  return Math.max(0, Math.min(1, value))
}

function applyDisplayBounds(point) {
  if (!point?.valid) return point
  const width = DISPLAY_AREA_BOUNDS.right - DISPLAY_AREA_BOUNDS.left
  const height = DISPLAY_AREA_BOUNDS.bottom - DISPLAY_AREA_BOUNDS.top
  if (width <= 0 || height <= 0) {
    return { x: null, y: null, valid: false }
  }

  const normX = (point.x - DISPLAY_AREA_BOUNDS.left) / width
  const normY = (point.y - DISPLAY_AREA_BOUNDS.top) / height
  const mappedY = DISPLAY_AREA_BOUNDS.invertY ? 1 - normY : normY

  return { x: clamp01(normX), y: clamp01(mappedY), valid: true }
}

function getGazePoint(eyetracker) {
  const x = Number(eyetracker?.x)
  const y = Number(eyetracker?.y)
  if (Number.isFinite(x) && Number.isFinite(y)) {
    return applyDisplayBounds({ x, y, valid: true })
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

  return applyDisplayBounds({
    x: xCandidates.reduce((acc, item) => acc + item, 0) / xCandidates.length,
    y: yCandidates.reduce((acc, item) => acc + item, 0) / yCandidates.length,
    valid: true,
  })
}

function EyeTracker({ eyetracker, running }) {
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
    if (lastSampleAgeMs <= 2200) return { label: "Tracking", className: "ok" }
    return { label: "Lost", className: "bad" }
  }, [lastSampleAgeMs, latestPoint, running])

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
    </div>
  )
}

export default EyeTracker