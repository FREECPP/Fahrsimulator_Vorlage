import {useEffect, useMemo, useRef, useState} from "react"
import {io} from "socket.io-client"
import DashboardGrid from "./DashboardGrid"
import Sidebar from "./Sidebar"
import { getDefaultMode, getSensorTitle } from "./widgetConfig"
import { getPreferredWidgetSize } from "./widgetSizing"
import "./../styles/DashboardStyle.css"

const SOCKET_URL = import.meta.env.VITE_SOCKET_URL || "http://localhost:9999"
const CURRENT_LAYOUT_STORAGE_KEY = "fahrsimulator-current-layout"

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


function getDefaultHorizontalPosition(widgetCount, widgetWidth = 4, totalCols = 12) {
    const widgetsPerRow = Math.max(1, Math.floor(totalCols / widgetWidth))
    const slot = widgetCount % widgetsPerRow
    return slot * widgetWidth
}

function App() {
  const socketRef = useRef(null)
  const [widgets, setWidgets] = useState([])
  const [layout, setLayout] = useState([])
  const [layoutReady, setLayoutReady] = useState(false)
  const [currentLayoutName, setCurrentLayoutName] = useState("")
  const [connected, setConnected] = useState(false)
  const [running, setRunning] = useState(false)
  const [sensorData, setSensorData] = useState({})
  const [lastPacketTime, setLastPacketTime] = useState(null)

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

    const API_URL = "http://localhost:9999"
    const PROJECT = "demo3"

    useEffect(() => {
      const fetchLayout = async () => {
        const savedLayoutName =
          typeof window === "undefined"
            ? ""
            : window.localStorage.getItem(CURRENT_LAYOUT_STORAGE_KEY) || ""
        const layoutNameToLoad = savedLayoutName || PROJECT

        try {
          const res = await fetch(`http://localhost:9999/api/layout/${layoutNameToLoad}`, {
            credentials: "include",
          })

          const data = await res.json()

          if (data.widgets?.length > 0) {
            setWidgets(data.widgets);
          } else {
            setWidgets(createDefaultWidgets())
          }

          if (data.layout?.length > 0) {
            setLayout(data.layout);
          } else {
            setLayout([])
          }

          setCurrentLayoutName(layoutNameToLoad)
        } catch (err) {
          console.error("Fehler beim Laden:", err)
          setWidgets(createDefaultWidgets())
        } finally {
          setLayoutReady(true)
        }
      }

      fetchLayout()
    }, [])

    useEffect(() => {
      if (typeof window === "undefined") return

      if (currentLayoutName) {
        window.localStorage.setItem(CURRENT_LAYOUT_STORAGE_KEY, currentLayoutName)
      } else {
        window.localStorage.removeItem(CURRENT_LAYOUT_STORAGE_KEY)
      }
    }, [currentLayoutName])

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
                setLayout={setLayout}
                setWidgets={setWidgets}
                widgets={widgets}
                currentLayoutName={currentLayoutName}
                setCurrentLayoutName={setCurrentLayoutName}
                onAddWidget={(view) => {
                    setWidgets((items) => {
                        const nextWidget = createWidget(view);

                        return [
                            ...items,
                            {
                                ...nextWidget,
                                x: getDefaultHorizontalPosition(items.length, nextWidget.w),
                                y: Math.max(...items.map((item) => item.y + item.h), 0),
                            },
                        ];
                    });
                }}
                onClearWidgets={() => setWidgets([])}
            />

            <main className="dashboard-area">
                <header className="topbar">
                    <div>
                        <h1>Fahrsimulator Dashboard</h1>
                    </div>
                    <div className="topbar-right">
                        <div className="simulation-controls">
                            <button className="control-btn start" onClick={handleStart}
                                    disabled={!connected || running}>
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
                    layout={layout}
                    setLayout={setLayout}
                    widgets={widgets}
                    setWidgets={setWidgets}
                    sensorData={sensorData}
                    connected={connected}
                    running={running}
                  saveEnabled={layoutReady}
                />
            </main>
        </div>
    )
}

export default App
