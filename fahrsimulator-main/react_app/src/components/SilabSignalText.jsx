import { memo } from "react"

// Shows a single SiLab signal as its live value: label on top, big value + unit.
const SilabSignalText = memo(function SilabSignalText({ signal, silab }) {
  const value = signal.store(silab)
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

export default SilabSignalText
