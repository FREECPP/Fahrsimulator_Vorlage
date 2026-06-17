import { memo, Suspense, useEffect, useMemo, useRef } from "react"
import SilabCockpit from "./SilabCockpit"
import EyeTracker from "./EyeTracker"
import SilabSignalChart from "./SilabSignalChart"
import SilabSignalText from "./SilabSignalText"
import ShimmerChart from "./ShimmerChart";
import {getModeOptions, getNormalizedMode, SENSOR_WIDGETS} from "./widgetConfig"
import {SILAB_SIGNALS, getSilabSignal} from "./silabSignals"
import {Trash2} from "lucide-react"

function WidgetCard({ widget, onDelete, onChangeView, onChangeMode, onUpdateWidget, sensorData, running }) {
  const imageRef = useRef(null)
  const modeOptions = useMemo(() => getModeOptions(widget.view), [widget.view])
  const mode = getNormalizedMode(widget.view, widget.mode)

  const silab = sensorData?.silab
  const signalKey = widget.signal ?? "speed"
  const signalDisplay = widget.signalDisplay ?? "chart"
  const rgbFrame = sensorData?.rgb_frame
  const tofFrame = sensorData?.tof_scelet
  const rgbBackFrame = sensorData?.rgb_frame2
  const eyetracker = sensorData?.eyetracker
  const shimmer = sensorData?.shimmer
  const selectedImage =
    mode === "image"
      ? {
          tof: tofFrame,
          rgb_front: rgbFrame,
          rgb_back: rgbBackFrame,
        }[widget.view]
      : null

  useEffect(() => {
    if (mode !== "image" || !imageRef.current || !selectedImage) return

    let objectUrl = null
    try {
        const blob = new Blob([selectedImage], {type:"image/jpeg"})
        objectUrl = URL.createObjectURL(blob)
        imageRef.current.src = objectUrl
        }catch(error){
            console.error("Fehler beim Verarbeiten der Bild-Bytes",error)
            imageRef.current.removeAttribute("src")
            }

    return() => {
        if(objectUrl){
            URL.revokeObjectURL(objectUrl)
            }
        }
  }, [selectedImage, mode])

  let body = <div className="placeholder">Unknown widget type.</div>

  if (widget.view === "silab") {
    if (mode === "raw") {
      body = <pre className="raw-payload">{JSON.stringify(silab ?? {}, null, 2)}</pre>
    } else if (mode === "line") {
      const signal = getSilabSignal(signalKey)
      body = signalDisplay === "text"
        ? <SilabSignalText signal={signal} silab={silab} />
        : <SilabSignalChart signal={signal} />
    } else {
      body = <SilabCockpit silab={silab} />
    }
  }

  if (widget.view === "shimmer") {
    if (mode === "raw") {
      body = <pre className="raw-payload">{JSON.stringify(shimmer ?? {}, null, 2)}</pre>
    } else {
      body = (
        <Suspense fallback={<div className="placeholder">Loading chart...</div>}>
          <ShimmerChart shimmer={shimmer} running={running} />
        </Suspense>
      )
    }
  }

  if (widget.view === "eyetracker") {
    body =
      mode === "raw" ? (
        <pre className="raw-payload">{JSON.stringify(eyetracker ?? {}, null, 2)}</pre>
      ) : (
        <EyeTracker eyetracker={eyetracker} running={running} />
      )
  }

  if (["tof", "rgb_front", "rgb_back"].includes(widget.view)) {
    body = selectedImage ? (
      <div className="widget-stack image-widget">
        <img ref={imageRef} className="stream-image" alt="Live sensor stream" draggable={false} />
      </div>
    ) : (
      <div className="placeholder">No frame yet. Start recording to receive frames.</div>
    )
  }

    return (
        <article className="widget-card">
            <header className="widget-header">

                <div className="widget-title-group">
                    <select //Select1
                        className="compact-control"
                        value={widget.view}
                        onChange={(event) => onChangeView(widget.i, event.target.value)}
                    >
                        {SENSOR_WIDGETS.map((sensor) => (
                            <option key={sensor.key} value={sensor.key}>
                                {sensor.label}
                            </option>
                        ))}
                    </select>
                </div>

                <div className="widget-actions">

                    <select //Select2
                        className="compact-control"
                        value={mode}
                        onChange={(event) => onChangeMode(widget.i, event.target.value)}
                    >
                        {modeOptions.map((option) => (
                            <option key={option.value} value={option.value}>
                                {option.label}
                            </option>
                        ))}
                    </select>

                    {widget.view === "silab" && mode === "line" && (
                        <>
                            <select
                                className="compact-control"
                                value={signalKey}
                                onChange={(event) => onUpdateWidget(widget.i, {signal: event.target.value})}
                            >
                                {SILAB_SIGNALS.map((signal) => (
                                    <option key={signal.key} value={signal.key}>
                                        {signal.label}
                                    </option>
                                ))}
                            </select>

                            <select
                                className="compact-control"
                                value={signalDisplay}
                                onChange={(event) => onUpdateWidget(widget.i, {signalDisplay: event.target.value})}
                            >
                                <option value="chart">Chart</option>
                                <option value="text">Text</option>
                            </select>
                        </>
                    )}

                    <button
                        className="danger icon-button compact-control"
                        onClick={() => onDelete(widget.i)}
                    >
                        <Trash2 size={14}/>
                    </button>

                </div>

            </header>

            <section className="widget-body">
                {body}
            </section>

        </article>
    )
}

function hasSameWidgetIdentity(prevWidget, nextWidget) {
  return (
    prevWidget.i === nextWidget.i &&
    prevWidget.view === nextWidget.view &&
    prevWidget.mode === nextWidget.mode &&
    prevWidget.signal === nextWidget.signal &&
    prevWidget.signalDisplay === nextWidget.signalDisplay &&
    prevWidget.title === nextWidget.title &&
    prevWidget.x === nextWidget.x &&
    prevWidget.y === nextWidget.y &&
    prevWidget.w === nextWidget.w &&
    prevWidget.h === nextWidget.h
  )
}

function areWidgetPropsEqual(prevProps, nextProps) {
  if (!hasSameWidgetIdentity(prevProps.widget, nextProps.widget)) return false
  if (prevProps.running !== nextProps.running) return false

  const view = nextProps.widget.view
  const mode = nextProps.widget.mode
  
  // Raw mode always needs to update with live data
  if (mode === "raw") return false

  const prevData = prevProps.sensorData || {}
  const nextData = nextProps.sensorData || {}

  if (view === "silab") {
    if (mode === "line") {
      // Chart self-updates from the telemetry store; only text needs prop-driven
      // re-renders, and only when its selected signal's value changes.
      if ((nextProps.widget.signalDisplay ?? "chart") !== "text") return true
      const signal = getSilabSignal(nextProps.widget.signal ?? "speed")
      return signal.store(prevData.silab) === signal.store(nextData.silab)
    }
    if (mode === "cockpit" || mode === "pedals") {
      return (
        prevData.silab?.speed === nextData.silab?.speed &&
        prevData.silab?.steering === nextData.silab?.steering &&
        prevData.silab?.acc_pedal === nextData.silab?.acc_pedal &&
        prevData.silab?.brake_pedal === nextData.silab?.brake_pedal
      )
    }
    return prevData.silab?.speed === nextData.silab?.speed
  }

  if (view === "shimmer") {
    return prevData.shimmer === nextData.shimmer
  }

  if (view === "eyetracker") {
    return prevData.eyetracker === nextData.eyetracker
  }

  if (view === "tof") {
    return prevData.tof_scelet === nextData.tof_scelet
  }

  if (view === "rgb_front") {
    return prevData.rgb_frame === nextData.rgb_frame
  }

  if (view === "rgb_back") {
    return prevData.rgb_frame2 === nextData.rgb_frame2
  }

  if (mode === "image") {
    return (
      prevData.rgb_frame === nextData.rgb_frame &&
      prevData.tof_scelet === nextData.tof_scelet &&
      prevData.rgb_frame2 === nextData.rgb_frame2
    )
  }

  return true
}

export default memo(WidgetCard, areWidgetPropsEqual)
