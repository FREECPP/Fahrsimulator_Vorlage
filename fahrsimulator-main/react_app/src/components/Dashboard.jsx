import {useEffect, useMemo, useRef, useState} from "react"
import {useLocation} from "react-router-dom"
import {io} from "socket.io-client"
import {FaPlay, FaStop} from "react-icons/fa"
import DashboardGrid from "./DashboardGrid"
import Sidebar from "./Sidebar"
import StartSensorPopup from "./StartSensorPopup"

import {
    getDefaultMode,
    getSensorTitle
} from "./widgetConfig"

import {getPreferredWidgetSize} from "./widgetSizing"

import "./../styles/DashboardStyle.css"

const SOCKET_URL =
    import.meta.env.VITE_SOCKET_URL
    || "http://localhost:9999"

const API_URL = "http://localhost:9999"

const DEFAULT_WIDGET_LAYOUT = [
    {view: "silab", x: 0, y: 0},
    {view: "eyetracker", x: 6, y: 0},
    {view: "tof", x: 0, y: 3},
    {view: "rgb_front", x: 4, y: 3},
    {view: "rgb_back", x: 8, y: 3},
    {view: "shimmer", x: 0, y: 6},
]

// ===== Widget =====
function createWidget(view) {

    const id =
        `${Date.now()}-${Math.round(Math.random() * 10000)}`

    const mode = getDefaultMode(view)

    const preferredSize =
        getPreferredWidgetSize(view, mode)

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


function getDefaultHorizontalPosition(
    widgetCount,
    widgetWidth = 4,
    totalCols = 12
) {

    const widgetsPerRow = Math.max(
        1,
        Math.floor(totalCols / widgetWidth)
    )

    const slot = widgetCount % widgetsPerRow

    return slot * widgetWidth
}

function Dashboard() {

    const socketRef = useRef(null)

    const location = useLocation()

    const project = location.state?.project
    const projectName = project?.name

    const participant = location.state?.participant
    const participantName = participant?.name

    const [widgets, setWidgets] = useState([])
    const [layout, setLayout] = useState([])

    const [sidebarCollapsed, setSidebarCollapsed] =
        useState(false)
    const [sensorPopupOpen, setSensorPopupOpen] =
        useState(false)
    const [layoutReady, setLayoutReady] =
        useState(false)

    const [layoutProject, setLayoutProject] =
        useState(null)

    const [currentLayoutName, setCurrentLayoutName] =
        useState(null)

    const [connected, setConnected] =
        useState(false)

    const [running, setRunning] =
        useState(false)

    const [sensorData, setSensorData] =
        useState({})

    const [lastPacketTime, setLastPacketTime] =
        useState(null)

    // ===== Init =====
    useEffect(() => {

        if (!projectName) {
            return
        }

        const initLayout = async () => {

            try {

                const res = await fetch(
                    `${API_URL}/api/layouts/${projectName}`
                )

                const data = await res.json()

                if (data.length > 0) {

                    setCurrentLayoutName(
                        `${projectName}::${data[0].name}`
                    )

                } else {

                    setCurrentLayoutName(
                        `${projectName}::default`
                    )
                }

            } catch {

                setCurrentLayoutName(
                    `${projectName}::default`
                )
            }
        }

        initLayout()

    }, [projectName])

    // ===== Socket =====
    useEffect(() => {

        const socket = io(SOCKET_URL)

        socket.on(
            "connect",
            () => setConnected(true)
        )

        socket.on(
            "disconnect",
            () => setConnected(false)
        )

        socket.on(
            "is_running",
            (value) => setRunning(Boolean(value))
        )

        socket.on(
            "sensor_update",
            (payload) => {
                console.log(payload.heartbeat)

                console.log("LATENCIES", payload.sensor_latency)

                setSensorData(payload || {})
                setLastPacketTime(new Date())
            }
        )

        socketRef.current = socket

        return () => socket.close()

    }, [])

    // ===== Load Layout =====
    useEffect(() => {

        if (!currentLayoutName) {
            return
        }

        const [
            layoutProjectName,
            layoutNameOnly
        ] = currentLayoutName.split("::")

        const fetchLayout = async () => {

            try {

                console.log(
                    "📥 Lade Layout:",
                    layoutProjectName,
                    layoutNameOnly
                )

                const res = await fetch(
                    `${API_URL}/api/layout/${layoutProjectName}/${layoutNameOnly}`
                )

                const data = await res.json()

                setWidgets(
                    data.widgets?.length
                        ? data.widgets
                        : createDefaultWidgets()
                )

                setLayout(
                    data.layout?.length
                        ? data.layout
                        : []
                )

                setLayoutProject(layoutProjectName)

            } catch (err) {

                console.error(
                    "❌ Fehler beim Laden:",
                    err
                )

                setWidgets(createDefaultWidgets())

            } finally {

                setLayoutReady(true)
            }
        }

        fetchLayout()

    }, [currentLayoutName])

    // ===== Save Layout =====
    const saveLayout = async () => {

        if (!projectName || !currentLayoutName) {
            return
        }

        const [
            layoutProjectName,
            layoutNameOnly
        ] = currentLayoutName.split("::")

        if (layoutProjectName !== projectName) {

            console.warn(
                "⛔ Fremdes Layout – wird nicht gespeichert"
            )

            return
        }

        try {

            await fetch(
                `${API_URL}/api/layout/${projectName}/${layoutNameOnly}`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json",
                    },

                    body: JSON.stringify({
                        layout,
                        widgets
                    }),
                }
            )

        } catch (err) {

            console.error(
                "❌ Fehler beim Speichern:",
                err
            )
        }
    }

    const handleStart = () => {

        if (
            !socketRef.current
            || !connected
            || running
        ) {
            return
        }

        socketRef.current.emit(
            "start_recording",
            {
                participant: participant,
                project: projectName,
            }
        )
    }

    const handleStop = () => {

        if (
            !socketRef.current
            || !connected
            || !running
        ) {
            return
        }

        socketRef.current.emit("stop_recording")
    }

    const handleStartSensor = () => {
        if (
            !socketRef.current
            || !connected
            || running
        ) {
            return
        }
        setSensorPopupOpen(true)
        socketRef.current.emit(
            "start_sensor",
            {
                participant,
                project: projectName,
            }
        )
    }


    const handleConfirmStartSensor = () => {

        console.log("CONFIRM CLICK POPUP")

        setSensorPopupOpen(false)
    }

    const handleStartLogging = () => {

        if (
            !socketRef.current
            || !connected
            || !running
        ) {
            return
        }

        socketRef.current.emit("start_logging",
            {
                participant: participant,
                project: projectName,
            })
    }

    const handleStartPC = () => {
        socketRef.current.emit("start_pc")
    }

    const handleStartSimulation = () => {

        if (!participant?.simulation_path) {
            console.error(
                "Keine Simulation hinterlegt"
            )
            return
        }

        socketRef.current.emit(
            "start_simulation",
            {
                simulation_path:
                participant.simulation_path
            }
        )
    }

    const packetLabel = useMemo(() => {

        if (!lastPacketTime) {
            return "no packets yet"
        }

        return lastPacketTime.toLocaleTimeString()

    }, [lastPacketTime])


    return (
        <div
            className={`app-shell ${
                sidebarCollapsed
                    ? "sidebar-is-collapsed"
                    : ""
            }`}
        >

            <Sidebar
                sidebarCollapsed={sidebarCollapsed}
                setSidebarCollapsed={setSidebarCollapsed}
                setLayout={setLayout}
                setWidgets={setWidgets}

                widgets={widgets}
                layout={layout}

                currentLayoutName={currentLayoutName}

                setCurrentLayoutName={
                    setCurrentLayoutName
                }

                project={projectName}

                setLayoutProject={
                    setLayoutProject
                }

                onAddWidget={(view) => {

                    setWidgets((items) => {

                        const nextWidget =
                            createWidget(view)

                        return [
                            ...items,
                            {
                                ...nextWidget,

                                x:
                                    getDefaultHorizontalPosition(
                                        items.length,
                                        nextWidget.w
                                    ),

                                y:
                                    Math.max(
                                        ...items.map(
                                            (item) =>
                                                item.y + item.h
                                        ),
                                        0
                                    ),
                            },
                        ]
                    })
                }}

                onClearWidgets={() => setWidgets([])}

                onSaveLayout={saveLayout}
            />

            <main className="dashboard-area">

                <header className="topbar">


                    <div className="simulation-controls">

                        <button
                            className="control-btn start"

                            onClick={handleStart}

                            disabled={
                                !connected
                                || running
                            }
                        >
                            <FaPlay style={{marginRight: "6px"}}/>
                            Sim
                        </button>

                        <button
                            className="control-btn stop"

                            onClick={handleStop}

                            disabled={
                                !connected
                                || !running
                            }
                        >
                            <FaStop style={{marginRight: "6px"}}/>
                            Sim
                        </button>

                        <button
                            className="start sensor"

                            onClick={handleStartSensor}

                            disabled={
                                !connected
                                || running
                            }
                        >
                            Start Sensor
                        </button>

                        <button
                            className="start logging"

                            onClick={handleStartLogging}

                            disabled={
                                !connected
                                || !running
                            }
                        >
                            Start logging
                        </button>

                        <button
                            className="start PC"

                            onClick={handleStartPC}
                        >
                            Start PC
                        </button>

                        <button
                            className="start Simulation"

                            onClick={
                                handleStartSimulation
                            }
                        >
                            Start Sim on PC2
                        </button>

                    </div>

                    <div className="badges">

                            <span
                                className={
                                    connected
                                        ? "badge ok"
                                        : "badge bad"
                                }
                            >
                                {
                                    connected
                                        ? "Socket connected"
                                        : "Socket disconnected"
                                }
                            </span>

                        <span
                            className={
                                running
                                    ? "badge ok"
                                    : "badge idle"
                            }
                        >
                                {
                                    running
                                        ? "Recording running"
                                        : "Recording stopped"
                                }
                            </span>

                        <span className="badge">
                                Last packet: {packetLabel}
                            </span>

                    </div>

                    <div
                        className="badges"
                        style={{display: "flex", gap: "12px", flexWrap: "wrap"}}
                    >
                        {[
                            ["silab", "SiLab"],
                            ["shimmer", "Shimmer"],
                            ["eyetracker", "Eyetracker"],
                            ["rgb_frame", "RGB Front"],
                            ["rgb_frame2", "RGB Back"],
                            ["tof_scelet", "TOF"],
                        ].map(([key, label]) => (
                            <span
                                key={key}
                                style={{
                                    color: (sensorData.heartbeat || {})[key]
                                        ? "limegreen"
                                        : "gray",
                                }}
                            >
                                    ● {label}
                                </span>
                        ))}
                    </div>
                    <div className="drive-stats">
                        <div>
                            Strecke:{" "}
                            {sensorData?.silab?.distance_km?.toFixed(2) ?? "0.00"} km
                        </div>

                        <div>
                            Zeit:{" "}
                            {sensorData?.silab?.drive_time ?? "--:--"}
                        </div>
                    </div>
                </header>

                <DashboardGrid
                    sidebarCollapsed={sidebarCollapsed}
                    layout={layout}
                    setLayout={setLayout}

                    widgets={widgets}
                    setWidgets={setWidgets}

                    sensorData={sensorData}

                    connected={connected}
                    running={running}

                    saveEnabled={layoutReady}

                    project={projectName}

                    currentLayoutName={
                        currentLayoutName
                    }

                    layoutProject={layoutProject}
                />

            </main>
            <StartSensorPopup
                open={sensorPopupOpen}
                onClose={() =>
                    setSensorPopupOpen(false)
                }
                onConfirm={
                    handleConfirmStartSensor
                }
                heartbeat={
                    sensorData.heartbeat || {}
                }
                    sensorLatency={
        sensorData.sensor_latency || {}
    }
            />
        </div>
    )
}

export default Dashboard