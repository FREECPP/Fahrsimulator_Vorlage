import {
    FaCheckCircle,
    FaSpinner,
    FaCamera,
    FaEye
} from "react-icons/fa"

import {
    MdSensors
} from "react-icons/md"

import {
    GiRadarSweep
} from "react-icons/gi"

import {
    IoPulse
} from "react-icons/io5"

import {
    useEffect,
    useState
} from "react"

import "../../styles/Popup.css"

function getSensorIcon(key) {

    switch (key) {

        case "tof_scelet":
            return <GiRadarSweep/>

        case "rgb_frame":
        case "rgb_frame2":
            return <FaCamera/>

        case "shimmer":
            return <IoPulse/>

        case "eyetracker":
            return <FaEye/>

        case "silab":
            return <MdSensors/>

        default:
            return <MdSensors/>
    }
}

const SENSORS = [
    {
        key: "silab",
        name: "SiLab"
    },
    {
        key: "shimmer",
        name: "Shimmer"
    },
    {
        key: "eyetracker",
        name: "Eyetracker"
    },
    {
        key: "rgb_frame",
        name: "RGB Front"
    },
    {
        key: "rgb_frame2",
        name: "RGB Back"
    },
    {
        key: "tof_scelet",
        name: "TOF"
    }
]

function StartSensorPopup({
                              open,
                              onClose,
                              onConfirm,
                              heartbeat = {},
                              sensorLatency = {},
                              onRestartSensor
                          }){

    const [startTimes, setStartTimes] =
        useState({})

    const [connectedTimes, setConnectedTimes] =
        useState({})

    // Pro Sensor: Zeitpunkt, bis zu dem nach einem Reconnect der noch alte
    // Heartbeat ignoriert wird (ueberbrueckt das ~2s Heartbeat-Timeout-Fenster).
    const [ignoreHeartbeatUntil, setIgnoreHeartbeatUntil] =
        useState({})

    const [now, setNow] =
        useState(Date.now())

    useEffect(() => {

        if (!open) {
            setStartTimes({})
            setConnectedTimes({})
            setIgnoreHeartbeatUntil({})
            return
        }

        const timestamp = Date.now()

        const starts = {}

        SENSORS.forEach(sensor => {
            starts[sensor.key] = timestamp
        })

        setStartTimes(starts)
        setConnectedTimes({})

    }, [open])

    useEffect(() => {

        if (!open) {
            return
        }

        const interval = setInterval(() => {
            setNow(Date.now())
        }, 100)

        return () => clearInterval(interval)

    }, [open])

    useEffect(() => {

        if (!open) {
            return
        }

        setConnectedTimes(prev => {

            const updated = {
                ...prev
            }

            let changed = false

            SENSORS.forEach(sensor => {

                const hasHeartbeat =
                    heartbeat?.[sensor.key]

                const alreadyConnected =
                    updated[sensor.key] !== undefined

                // Direkt nach einem Reconnect den noch alten Heartbeat ignorieren,
                // bis der alte Prozess wirklich tot ist (Heartbeat-Timeout).
                const ignoreHeartbeat =
                    ignoreHeartbeatUntil[sensor.key] > Date.now()

                if (
                    hasHeartbeat &&
                    !alreadyConnected &&
                    startTimes[sensor.key] &&
                    !ignoreHeartbeat
                ) {

                    updated[sensor.key] =
                        Date.now() -
                        startTimes[sensor.key]

                    changed = true
                }
            })

            return changed
                ? updated
                : prev
        })

    }, [heartbeat, startTimes, open, ignoreHeartbeatUntil])

    if (!open) {
        return null
    }

    const allReady =
        SENSORS.every(
            sensor => connectedTimes[sensor.key] !== undefined
        )

    return (
        <div className="popupOverlay">

            <div
                className="popup SensorPopup"
                onClick={(e) =>
                    e.stopPropagation()
                }
            >

                <div className="popupHeader">

                    <h3>
                        Sensoren starten
                    </h3>

                    <div className="popupSub">
                        Verfügbarkeit der Sensoren
                    </div>

                </div>

                <div className="popupBody">

                    <div className="SensorList">

                        {SENSORS.map((sensor) => {

                            const available =
                                connectedTimes[sensor.key] !== undefined
                            const latency =
                                sensorLatency?.[sensor.key]?.latency_ms

                            let elapsedMs = 0

                            if (
                                connectedTimes[sensor.key] !==
                                undefined
                            ) {

                                elapsedMs =
                                    connectedTimes[sensor.key]

                            } else if (
                                startTimes[sensor.key]
                            ) {

                                elapsedMs =
                                    now -
                                    startTimes[sensor.key]
                            }

                            const elapsed =
                                (
                                    elapsedMs / 1000
                                ).toFixed(1)

                            return (
<div
    key={sensor.key}
    className="SensorCard"
>
    <div className="SensorRow">

        <div className="SensorIcon">
            {getSensorIcon(sensor.key)}
        </div>

        <div className="SensorName">
            {sensor.name}
        </div>

        <div className="SensorLatency">
            {latency !== undefined
                ? `${latency} ms`
                : "N/A"}
        </div>

        <div className="SensorStatus">

            {available ? (
                <>
                    <FaCheckCircle
                    size={20}
                        className="SensorStatusSuccess"
                    />

                    <span>
                        Verbunden ({elapsed}s)
                    </span>
                </>
            ) : (
                <>
                    <FaSpinner
                        className="SensorSpinner"
                    />

                    <span>
                        Suche... ({elapsed}s)
                    </span>
                </>
            )}

        </div>

        <div className="SensorRestart">

            <button
                className="popupBtn"
                onClick={() => {
                    // Sensor als "nicht verbunden" markieren, damit wieder
                    // der Spinner ("Suche...") statt "Verbunden" angezeigt wird
                    setConnectedTimes(prev => {
                        const u = { ...prev }
                        delete u[sensor.key]
                        return u
                    })
                    // Startzeit zuruecksetzen, damit der Timer neu zaehlt
                    setStartTimes(prev => ({
                        ...prev,
                        [sensor.key]: Date.now()
                    }))
                    // Noch alten Heartbeat 2,2s ignorieren (> Heartbeat-Timeout),
                    // damit nicht sofort wieder "Verbunden (0s)" erscheint
                    setIgnoreHeartbeatUntil(prev => ({
                        ...prev,
                        [sensor.key]: Date.now() + 2200
                    }))
                    // Reconnect im Backend ausloesen
                    onRestartSensor?.(sensor.key)
                }}
            >
                Restart
            </button>

        </div>

    </div>
</div>
                            )
                        })}

                    </div>

                </div>

                <div className="popupActions">

                    <button
                        className="popupBtn"
                        onClick={onClose}
                    >
                        Abbruch
                    </button>

                    <button
                        className={`popupBtn primary ${allReady ? "ready" : ""}`}
                        disabled={!allReady}
                        onClick={onConfirm}
                    >
                        OK
                    </button>

                </div>

            </div>

        </div>
    )
}

export default StartSensorPopup