import { memo } from "react"
import { getShimmerValue } from "./shimmerSignals"

// Shows a single Shimmer signal as its live value: label on top, big value + unit.
const ShimmerSignalText = memo(function ShimmerSignalText({ signal, shimmer }) {
  const value = getShimmerValue(shimmer, signal)
  const formatted = value == null ? "--" : signal.formatValue(value)

  return (
    <div className="silab-signal-text">
      <div className="silab-signal-text-label">{signal.label}</div>
      <div className="silab-signal-text-value">
        {formatted}
        {signal.unit && value != null ? (
          <span className="silab-signal-text-unit">{signal.unit}</span>
        ) : null}
      </div>
    </div>
  )
})

export default ShimmerSignalText
