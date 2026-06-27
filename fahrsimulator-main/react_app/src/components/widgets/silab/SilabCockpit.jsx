import { useEffect, useRef, useState } from "react"

const MAX_SPEED_KMH = 240
const GAS_RAW_MAX = 1.0
const BRAKE_RAW_MAX = 3.5
const MAX_STEERING_DEG = 450
const GAUGE_RADIUS = 52
const GAUGE_SPAN_DEG = 240
const GAUGE_ARC_LENGTH = (Math.PI * GAUGE_RADIUS * GAUGE_SPAN_DEG) / 180

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function toPercent(value, fullScale = 1) {
  if (!Number.isFinite(value)) return 0
  if (!Number.isFinite(fullScale) || fullScale <= 0) return 0

  // Keep compatibility with older normalized payloads in [0..1].
  if (fullScale > 1 && value >= 0 && value <= 1.2) {
    return clamp(value * 100, 0, 100)
  }

  return clamp((value / fullScale) * 100, 0, 100)
}

function toSteeringDegrees(value) {
  if (!Number.isFinite(value)) return 0

  // Exact old dashboard formula.
  const normalized = 1 - ((value + 8) / 16)
  return clamp((normalized - 0.5) * 2 * MAX_STEERING_DEG, -MAX_STEERING_DEG, MAX_STEERING_DEG)
}

function SilabCockpit({ silab }) {
  const wheelSources = ["/steering-wheel.svg", "/assets/steering-wheel.svg"]
  const [wheelSourceIndex, setWheelSourceIndex] = useState(0)
  const [displaySpeedKmh, setDisplaySpeedKmh] = useState(0)

  const speedKmh = Number.isFinite(silab?.speed) ? Math.max(0, silab.speed * 3.6) : 0
  const steeringDeg = toSteeringDegrees(silab?.steering)
  const gasPercent = toPercent(silab?.acc_pedal, GAS_RAW_MAX)
  const brakePercent = toPercent(silab?.brake_pedal, BRAKE_RAW_MAX)
  const speedRatio = clamp(displaySpeedKmh / MAX_SPEED_KMH, 0, 1)

  // Hold the latest target in a ref so the easing interval can stay stable
  // instead of being torn down and recreated on every incoming packet.
  const targetSpeedRef = useRef(speedKmh)
  useEffect(() => {
    targetSpeedRef.current = speedKmh
  }, [speedKmh])

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setDisplaySpeedKmh((current) => {
        const target = targetSpeedRef.current
        const delta = target - current
        if (Math.abs(delta) < 0.08) return target
        // Exponential easing gives a more natural instrument response.
        return current + delta * 0.22
      })
    }, 33)

    return () => window.clearInterval(intervalId)
  }, [])

  const wheelSrc = wheelSources[wheelSourceIndex]
  const hasMoreWheelSources = wheelSourceIndex < wheelSources.length - 1

  return (
    <div className="silab-cockpit">
      <section className="silab-wheel-panel">
        <div className="wheel-stage">
          <div className="wheel-frame" style={{ transform: `rotate(${steeringDeg.toFixed(1)}deg)` }}>
            {wheelSrc ? (
              <img
                src={wheelSrc}
                alt="Steering wheel"
                className="steering-wheel-asset"
                draggable={false}
                onError={() => {
                  if (hasMoreWheelSources) {
                    setWheelSourceIndex((current) => current + 1)
                  } else {
                    setWheelSourceIndex(-1)
                  }
                }}
              />
            ) : (
              <div className="wheel-fallback" aria-label="Steering wheel fallback">
                <div className="wheel-ring" />
                <div className="wheel-spoke wheel-spoke-top" />
                <div className="wheel-spoke wheel-spoke-left" />
                <div className="wheel-spoke wheel-spoke-right" />
              </div>
            )}
          </div>
        </div>

      </section>

      <section className="silab-gauge-panel">
        <svg viewBox="0 0 140 95" className="speed-gauge" role="img" aria-label="Speedometer">
          <path d="M 18 72 A 52 52 0 0 1 122 72" fill="none" stroke="#d7e2ec" strokeWidth="10" strokeLinecap="round" />
          <path
            d="M 18 72 A 52 52 0 0 1 122 72"
            fill="none"
            stroke="url(#gaugeAccent)"
            strokeWidth="10"
            strokeLinecap="round"
            style={{
              strokeDasharray: `${speedRatio * GAUGE_ARC_LENGTH} ${GAUGE_ARC_LENGTH}`,
              transition: "stroke-dasharray 120ms linear",
            }}
          />

          <defs>
            <linearGradient id="gaugeAccent" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#6ab2ff" />
              <stop offset="100%" stopColor="#2d5dff" />
            </linearGradient>
          </defs>
          <text x="70" y="85" textAnchor="middle" fontSize="12" fontWeight="700" fill="#223447">
            {displaySpeedKmh.toFixed(1)} km/h
          </text>
        </svg>
      </section>

      <section className="silab-pedals">
        <div className="pedal">
          <span className="pedal-label">Gas</span>
          <div className="pedal-track">
            <div className="pedal-fill gas-fill" style={{ height: `${gasPercent.toFixed(1)}%` }} />
          </div>
          <strong className="pedal-value">{gasPercent.toFixed(0)}%</strong>
        </div>

        <div className="pedal">
          <span className="pedal-label">Brake</span>
          <div className="pedal-track">
            <div className="pedal-fill brake-fill" style={{ height: `${brakePercent.toFixed(1)}%` }} />
          </div>
          <strong className="pedal-value">{brakePercent.toFixed(0)}%</strong>
        </div>
      </section>
    </div>
  )
}

export default SilabCockpit
