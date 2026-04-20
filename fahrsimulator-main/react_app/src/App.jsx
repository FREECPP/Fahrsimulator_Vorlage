import {useEffect, useMemo, useRef, useState} from "react"
import {io} from "socket.io-client"
import DashboardGrid from "./components/DashboardGrid"
import Sidebar from "./components/Sidebar"
import "./App.css"

const SOCKET_URL = import.meta.env.VITE_SOCKET_URL || "http://localhost:9999"

function createWidget(view) {
    const id = `${Date.now()}-${Math.round(Math.random() * 10000)}`
    return {
        i: id,
        x: 0,
        y: Infinity,
        w: 4,
        h: 4,
        view,
        title: view.charAt(0).toUpperCase() + view.slice(1),
    }
}

function getDefaultHorizontalPosition(widgetCount, widgetWidth = 4, totalCols = 12) {
    const widgetsPerRow = Math.max(1, Math.floor(totalCols / widgetWidth))
    const slot = widgetCount % widgetsPerRow
    return slot * widgetWidth
}

function App() {
    const socketRef = useRef(null)
    const [layout, setLayout] = useState([]);
    const [widgets, setWidgets] = useState(() =>
        ["status", "speed", "image"].map((view, index) => {
            const widget = createWidget(view)
            return {
                ...widget,
                x: getDefaultHorizontalPosition(index, widget.w),
                y: Infinity,
            }
        }),
    )
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
            try {

                const res = await fetch(`http://localhost:9999/api/layout/${PROJECT}`, {
                    credentials: "include",
                })

                const data = await res.json()

                if (data.widgets?.length > 0) {
                    setWidgets(data.widgets);
                }
                if (data.layout) {
                    setLayout(data.layout);
                }
            } catch (err) {
                console.error("Fehler beim Laden:", err)
            }
        }

        fetchLayout()
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

    return (
        <div className="app-shell">
            <Sidebar
                setLayout={setLayout}
                setWidgets={setWidgets}
                onAddWidget={(view) => {
                    setWidgets((items) => {
                        const nextWidget = createWidget(view);

                        return [
                            ...items,
                            {
                                ...nextWidget,
                                x: getDefaultHorizontalPosition(items.length, nextWidget.w),
                                y: Infinity,
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
                />
            </main>
        </div>
    )
}

export default App
