// Client-Bibliothek einbinden (npm install socket.io-client)
import {io} from "socket.io-client";
const socket = io("http://localhost:9999");

socket.on("connect", () => {
    console.log("Verbunden über Socket.io!");
});

// Das Event 'new_data' muss exakt so heißen wie im Python emit
socket.on("sensor_update", (data) => {
    // KEIN JSON.parse() nötig!
    console.log("Sensor:", data.silab);
    
});