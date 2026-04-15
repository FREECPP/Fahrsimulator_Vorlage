import { useEffect, useRef, useState } from "react"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"

function SpeedChart({ sensorData }) {
  const [data, setData] = useState([])
  const dataRef = useRef([])
  const timestepRef = useRef(0)

  useEffect(() => {
    if (!sensorData?.silab) return

    const silab = sensorData.silab
    const newDataPoint = {
      time: timestepRef.current++,
      speed: typeof silab.speed === "number" ? parseFloat((silab.speed * 3.6).toFixed(1)) : 0,
      steering: typeof silab.steering === "number" ? parseFloat(silab.steering.toFixed(2)) : 0,
      accel: typeof silab.acc_pedal === "number" ? parseFloat(silab.acc_pedal.toFixed(2)) : 0,
      brake: typeof silab.brake_pedal === "number" ? parseFloat(silab.brake_pedal.toFixed(2)) : 0,
    }

    dataRef.current = [...dataRef.current.slice(-99), newDataPoint]
    setData([...dataRef.current])
  }, [sensorData])

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart
        data={data}
        margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
        <XAxis dataKey="time" stroke="#666" />
        <YAxis stroke="#666" />
        <Tooltip
          contentStyle={{ backgroundColor: "#f9f9f9", border: "1px solid #ccc" }}
        />
        <Legend wrapperStyle={{ paddingTop: "10px" }} />
        <Line
          type="monotone"
          dataKey="speed"
          stroke="#1f8a46"
          dot={false}
          isAnimationActive={false}
        />
        <Line
          type="monotone"
          dataKey="steering"
          stroke="#225f7a"
          dot={false}
          isAnimationActive={false}
        />
        <Line
          type="monotone"
          dataKey="accel"
          stroke="#f59e0b"
          dot={false}
          isAnimationActive={false}
        />
        <Line
          type="monotone"
          dataKey="brake"
          stroke="#dc2626"
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

export default SpeedChart
