import { useEffect, useMemo, useRef, useState } from "react"
import { io } from "socket.io-client"
import DashboardGrid from "./components/DashboardGrid"
import Sidebar from "./components/Sidebar"
import { getDefaultMode, getNormalizedMode, getSensorTitle } from "./components/widgetConfig"
import { getPreferredWidgetSize } from "./components/widgetSizing"
import "./App.css"

const SOCKET_URL = import.meta.env.VITE_SOCKET_URL || "http://localhost:9999"
const WIDGET_LAYOUT_STORAGE_KEY = "fahrsimulator-dashboard-widgets"

const DEFAULT_WIDGET_LAYOUT = [
  { view: "silab", x: 0, y: 0 },
  { view: "eyetracker", x: 6, y: 0 },
  { view: "tof", x: 0, y: 3 },
  { view: "rgb_front", x: 4, y: 3 },
  { view: "rgb_back", x: 8, y: 3 },
  { view: "shimmer", x: 0, y: 6 },
]

function createWidget(view) {
  const id = `${Date.now()}-${Math.round(Math.random() * 10000)}`
  const mode = getDefaultMode(view)
  const preferredSize = getPreferredWidgetSize(view, mode)

  return {
    i: id,
    x: 0,
    y: Infinity,
    w: preferredSize.w,
    h: preferredSize.h,
    view,
    mode,
    title: getSensorTitle(view),
  }
}

function createDefaultWidgets() {
  return DEFAULT_WIDGET_LAYOUT.map(({ view, x, y }) => ({
    ...createWidget(view),
    x,
    y,
  }))
}

function loadStoredWidgets() {
  if (typeof window === "undefined") return createDefaultWidgets()

  try {
    const rawValue = window.localStorage.getItem(WIDGET_LAYOUT_STORAGE_KEY)
    if (!rawValue) return createDefaultWidgets()

    const parsed = JSON.parse(rawValue)
    if (!Array.isArray(parsed) || parsed.length === 0) return createDefaultWidgets()

    return parsed
      .filter((widget) => widget && typeof widget === "object" && typeof widget.view === "string")
      .map((widget) => {
        const mode = getNormalizedMode(widget.view, widget.mode)
        const preferredSize = getPreferredWidgetSize(widget.view, mode)

        return {
          ...createWidget(widget.view),
          ...widget,
          mode,
          w: Number.isFinite(widget.w) ? widget.w : preferredSize.w,
          h: Number.isFinite(widget.h) ? widget.h : preferredSize.h,
        }
      })
  } catch {
    return createDefaultWidgets()
  }
}

function getDefaultHorizontalPosition(widgetCount, widgetWidth = 4, totalCols = 12) {
  const widgetsPerRow = Math.max(1, Math.floor(totalCols / widgetWidth))
  const slot = widgetCount % widgetsPerRow
  return slot * widgetWidth
}

function App() {
  const socketRef = useRef(null)
  const [widgets, setWidgets] = useState(() => loadStoredWidgets())
  const [connected, setConnected] = useState(false)
  const [running, setRunning] = useState(false)
  const [sensorData, setSensorData] = useState({})
  const [lastPacketTime, setLastPacketTime] = useState(null)

  useEffect(() => {
    try {
      window.localStorage.setItem(WIDGET_LAYOUT_STORAGE_KEY, JSON.stringify(widgets))
    } catch {
      // Ignore storage failures and keep the dashboard usable.
    }
  }, [widgets])

  useEffect(() => {
    const socket = io(SOCKET_URL, {
      transports: ["websocket", "polling"],
      reconnection: true,
    })

    socket.on("connect", () => setConnected(true))
    socket.on("disconnect", () => setConnected(false))
    socket.on("is_running", (value) => setRunning(Boolean(value)))
    socket.on("sensor_update", (payload) => {
      setSensorData(payload || {})
      setLastPacketTime(new Date())
    })

    socketRef.current = socket

    return () => {
      socket.close()
      socketRef.current = null
    }
  }, [])

  const handleStart = () => {
    if (!socketRef.current || !connected || running) return
    // This event marks the start point for logging sessions on the backend.
    socketRef.current.emit("start_recording")
  }

  const handleStop = () => {
    if (!socketRef.current || !connected || !running) return
    // This event marks the end point for logging sessions on the backend.
    socketRef.current.emit("stop_recording")
  }

  const packetLabel = useMemo(() => {
    if (!lastPacketTime) return "no packets yet"
    return lastPacketTime.toLocaleTimeString()
  }, [lastPacketTime])

  const resetDashboardLayout = () => {
    setWidgets(createDefaultWidgets())
  }

  return (
    <div className="app-shell">
      <Sidebar
        onAddWidget={(view) =>
          setWidgets((items) => {
            const nextWidget = createWidget(view)
            return [
              ...items,
              {
                ...nextWidget,
                x: getDefaultHorizontalPosition(items.length, nextWidget.w),
                y: Math.max(...items.map((item) => item.y + item.h), 0),
              },
            ]
          })
        }
        onClearWidgets={() => setWidgets([])}
      />

      <main className="dashboard-area">
        <header className="topbar">
          <div>
            <h1>Fahrsimulator Dashboard</h1>
          </div>
          <div className="topbar-right">
            <div className="simulation-controls">
              <button className="control-btn start" onClick={handleStart} disabled={!connected || running}>
                Start Simulation
              </button>
              <button className="control-btn stop" onClick={handleStop} disabled={!connected || !running}>
                Stop Simulation
              </button>
              <button className="control-btn reset" onClick={resetDashboardLayout}>
                Reset Layout
              </button>
            </div>

            <div className="badges">
              <span className={connected ? "badge ok" : "badge bad"}>
                {connected ? "Socket connected" : "Socket disconnected"}
              </span>
              <span className={running ? "badge ok" : "badge idle"}>
                {running ? "Recording running" : "Recording stopped"}
              </span>
              <span className="badge">Last packet: {packetLabel}</span>
            </div>
          </div>
        </header>

        <DashboardGrid
          widgets={widgets}
          setWidgets={setWidgets}
          sensorData={sensorData}
          connected={connected}
          running={running}
        />
      </main>
    </div>
  )
}

export default App
