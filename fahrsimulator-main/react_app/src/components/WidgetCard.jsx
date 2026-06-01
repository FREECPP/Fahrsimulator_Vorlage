import { lazy, memo, Suspense, useEffect, useMemo, useRef } from "react"
import SilabCockpit from "./SilabCockpit"
import EyeTrackerSummary from "./EyeTrackerSummary"
import SpeedChart from "./SpeedChart"
import {getModeOptions, getNormalizedMode, getSensorTitle, SENSOR_WIDGETS} from "./widgetConfig"
import {Trash2} from "lucide-react"

const ShimmerChart = lazy(() => import("./ShimmerChart"))

function WidgetCard({ widget, onDelete, onChangeView, onChangeMode, sensorData, running }) {
  const imageRef = useRef(null)
  const modeOptions = useMemo(() => getModeOptions(widget.view), [widget.view])
  const mode = getNormalizedMode(widget.view, widget.mode)

  const silab = sensorData?.silab
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
      body = <SpeedChart silab={silab} />
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
        <EyeTrackerSummary eyetracker={eyetracker} running={running} />
      )
  }

  if (["tof", "rgb_front", "rgb_back"].includes(widget.view)) {
    const frameBySensor = {
      tof: tofFrame,
      rgb_front: rgbFrame,
      rgb_back: rgbBackFrame,
    }
    const packetPayload = frameBySensor[widget.view] || ""

    if (mode === "image") {
      body = selectedImage ? (
        <div className="widget-stack image-widget">
          <img ref={imageRef} className="stream-image" alt="Live sensor stream" />
        </div>
      ) : (
        <div className="placeholder">No frame yet. Start recording to receive frames.</div>
      )
    } else {
      body = (
        <div className="widget-stack">
          <div className="status-row">
            <span>Sensor</span>
            <strong>{getSensorTitle(widget.view)}</strong>
          </div>
          <div className="status-row">
            <span>Frame Available</span>
            <strong>{packetPayload ? "Yes" : "No"}</strong>
          </div>
          <div className="status-row">
            <span>Payload Length</span>
            <strong>{packetPayload.length || 0}</strong>
          </div>
        </div>
      )
    }
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
      return prevData.silab?.speed === nextData.silab?.speed && prevData.silab?.steering === nextData.silab?.steering
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
