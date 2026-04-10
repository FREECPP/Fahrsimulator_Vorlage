const update_interval = 100;
let steer = 0;
let brake, brakePad, brakePadRect;
let gas, gasPad, gasPadRect;
let speedChart, heartRateChart;
let brakesIconText, gasIconText;
let speed = 0;
let steering = 0;
let acc_pedal = 0;
let brake_pedal = 0;
let is_accelerating = false;
let brakes_pushed = false;
let heart_rate_data;
heart_rate_data_sdnn = 0;
heart_rate_data_rmssd = 0;

// Loading DOM Content
document.addEventListener("DOMContentLoaded", () => {

    // Initialize Object-Elements
    initObj("brake_pedal", initBrakePedal);
    initObj("gas_pedal", initGaspedal);
    initObj("brake_bar", initBrakeBar);
    initObj("gas_bar", initGasBar);

    // Canvas don't need LOAD-Event
    const speedCanvas = document.getElementById('speedChart')
    const speed2dContext = speedCanvas.getContext('2d');
    
    const heartrateCanvas = document.getElementById('heartRateChart')
    const heartrate2dContext = heartrateCanvas.getContext('2d');
    

    if (!speedCanvas) {
        console.error("Canvas mit ID 'speedChart' nicht gefunden!");
        return;
    }

    speedChart = createSpeedChart(speed2dContext);
    heartRateChart = createHeartRateChart(heartrate2dContext)
});

//Brake-Pedal
let brakeReady = false;
function initBrakePedal(svg) {
    brake = svg.getElementById("pedal-group");
    brakePad = svg.getElementById("pad");
    brakePadRect = svg.getElementById("pad-rect");

    brakeReady = !!(brake && brakePadRect);
}

//Gas-Pedal
let gasReady = false;
function initGaspedal(svg) {
    gas = svg.getElementById("pedal-group");
    gasPad = svg.getElementById("pad");
    gasPadRect = svg.getElementById("pad-rect");

    gasReady = !!(gas && gasPadRect);
}

//Brake-Icon
function initBrakeBar(svg) {
    //console.log("svg exists")
    brakesIconText = svg.getElementById("icon-text");
}
//Gas-Icon
function initGasBar(svg) {
    //console.log("svg exists")
    gasIconText = svg.getElementById("icon-text");
}

// Hilfsfunktion Object initialization
function initObj(objectId, initFn) {
    const obj = document.getElementById(objectId);
    if (!obj) return False;
    obj.addEventListener("load", () => {
        initFn(obj.contentDocument);
    });
    return true
}

// Hilfsfunktion zum initialisieren - never used!
function initializeElement(elementId, callback) {
    const element = document.getElementById(elementId);
    
    if (!element) {
        console.log(`${elementId} nicht gefunden!`);
        return;
    }
    
    // Falls Element bereits geladen
    if (element.contentDocument) {
        console.log(`${elementId} bereits geladen`);
        callback(element.contentDocument);
    } else {
        // Falls noch nicht geladen
        element.addEventListener("load", () => {
            console.log(`${elementId} jetzt geladen`);
            callback(element.contentDocument);
        });
    }
}


// Update die Bremspedal-Anzeige
function updateBremspedal() {
    //Brake-Bar
    document.getElementById("brakeFill").style.height = (brake_pedal/3.5*100) + "%";

    // Brake-Pedal
    if (brakes_pushed && brake && brakePad) {
        brake.setAttribute("transform", "translate(80,80) rotate(0)");
        brakePadRect.setAttribute("stroke-width", "15");
        brakePadRect.setAttribute("stroke", "red");
        brakePadRect.setAttribute("stroke-opacity", "0.20");
    } else {
        brake.setAttribute("transform", "translate(80,80) rotate(12)");
        brakePadRect.setAttribute("stroke-width", "2");
        brakePadRect.setAttribute("stroke", "white");
        brakePadRect.setAttribute("stroke-opacity", "0.12");
    }

    if (brake_pedal > 0.05) {
        //console.log(brake_pedal)
        brakes_pushed = true;
    } else {
        brakes_pushed = false;
    }

    if (brakes_pushed && brakesIconText) {
        //console.log("bremse gedrückt")
        //console.log(brake_pedal)
        brakesIconText.setAttribute("fill", "#ff2a2a");
    }
    if (!brakes_pushed && brakesIconText) {
        //console.log("bremse nicht gedrückt")
        //console.log(brake_pedal)
        brakesIconText.setAttribute("fill", "#444444");
    }

}    

// Update die Gas-Pedal-Anzeige
function updateGaspedal() {    
    // Gas-Balken aktualisieren
    document.getElementById("gasFill").style.height = (acc_pedal*100) + "%";

    //Gas-Pedal
    if (is_accelerating && gas && gasPad) {
        gas.setAttribute("transform", "translate(80,80) rotate(0)");
        gasPadRect.setAttribute("stroke-width", "15");
        gasPadRect.setAttribute("stroke", "red");
        gasPadRect.setAttribute("stroke-opacity", "0.20");
        
        gasIconText.setAttribute("fill", "#ff2a2a");
    } else {
        gas.setAttribute("transform", "translate(80,80) rotate(12)");
        gasPadRect.setAttribute("stroke-width", "2");
        gasPadRect.setAttribute("stroke", "white");
        gasPadRect.setAttribute("stroke-opacity", "0.12");
        
        gasIconText.setAttribute("fill", "#444444");
    }

    if (acc_pedal > 0.05) {
        //console.log("Gas gedrückt")
        //console.log(acc_pedal)
        is_accelerating = true;
    }
    else {
        //console.log("Gas nicht gedrückt")
        //console.log(acc_pedal)
        is_accelerating = false;
    }

}  

// 1. Linien-Diagramm für Geschwindigkeit-Anzeige
function createSpeedChart(context) {
    return new Chart(context, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Geschwindigkeit (km/h)',
                data: [],
                borderColor: 'blue',
                fill: false,
                tension: 0.1,
                pointStyle: false,
            }]
        },
        options: {
            animation: false,
            scales: {
                y: { beginAtZero: true }
            },
            plugins: {
                title: {
                    display: false,
                    text: "Geschwindigkeit"
                }
            }
        }
    });
}

// 2. Funktion zum Hinzufügen von Werten für Geschwindigkeit-Linien-Diagramm
function addSpeedValue(chart, speed) {
    const now = new Date().toLocaleTimeString();
    chart.data.labels.push(now);
    chart.data.datasets[0].data.push(speed);

    while (chart.data.labels.length > 60) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
    }
    chart.update();
}

// 3. Linien-Diagramm für Herzrate-Anzeige
function createHeartRateChart(context) {
    return new Chart(context, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
            {
                label: 'sdnn',
                data: [],
                borderColor: 'red',
                fill: false,
                tension: 0.1,
                pointStyle: false,
            },
            {
                label: 'rmssd',
                data: [],
                borderColor: 'blue',
                fill: false,
                tension: 0.1,
                pointStyle: false,
            }
            ]
        },
        options: {
            animation: false,
            scales: {
                y: {
                    beginAtZero: false
                }
            },
            plugins: {
                title: {
                    display: false,
                    text: "Herzrate"
                }
            }
        }
    });
}

// 4. Funktion zum Hinzufügen von Werten für Herzrate-Anzeige
function addHeartrateValue(chart, heart_rate_data_sdnn, heart_rate_data_rmssd) {
    const now = new Date().toLocaleTimeString();
    chart.data.labels.push(now);
    chart.data.datasets[0].data.push(heart_rate_data_sdnn);
    chart.data.datasets[1].data.push(heart_rate_data_rmssd);

    while (chart.data.labels.length > 360) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
        chart.data.datasets[1].data.shift();
    }
    chart.update();
}


// Ausführen im Abstand von update_interval
setInterval(() => {
    updateGaspedal()
    updateBremspedal()

    const normalized_steering = 1- ((steering+8)/16); // // 0 – 1
    //console.log(normalized_steering)
    document.getElementById("steerIndicator").style.left =
        (normalized_steering * 100) + "%";

    const wheel_steering = 1- ((steering+8)/16);
    const wheel_steering2 = (wheel_steering-0.5)*2*450;
    document.getElementById("wheel").style.transform =
        `rotate(${wheel_steering2}deg)`;

    if (speedChart) {
        addSpeedValue(speedChart, speed*3.6);
    }
    
    //heart_rate_data = Math.random()
    addHeartrateValue(heartRateChart, heart_rate_data_sdnn, heart_rate_data_rmssd)
    
    updateUI();
}, update_interval);


// Funktion um beim Aufruf der Seite den Viewport auf das Dashboard zu zentralisieren
window.addEventListener('load', () => {
    const container = document.querySelector('.grid-container');
    if (container) {
        container.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'center',   // vertikal zentrieren
            inline: 'center'   // horizontal zentrieren
        });
    }
});




const socket = io();
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
let isRunning = false;

// ===== Event Listener für Buttons =====
document.getElementById('toggle-btn').addEventListener('click', () => {
    toggleButton();
});


socket.on('is_running', (running) => {
    isRunning = running;
    updateUI();
    console.log('Status aktualisiert:', running);
});

// ===== UI aktualisieren =====
function updateUI() {
    const toggleBtn = document.getElementById('toggle-btn')
    const statusDiv = document.getElementById('statusDiv');
    const statusText = document.getElementById('statusText');
    const statusSym = document.getElementById('statusSymbol')

    if (isRunning && dataStream) {
        toggleBtn.textContent = "Stop";
        statusDiv.className = 'status running';
        statusText.textContent = 'Läuft';
        statusSym.className = 'dot red';
    }
    else if (isRunning && !dataStream) {
        toggleBtn.textContent = "loading";
        statusDiv.className = 'status waiting';
        statusText.textContent = 'Warte';
        statusSym.className = 'dot yellow';

    }
    else if (isRunning && dataStream){
        toggleBtn.textContent = "Start";
        statusDiv.className = 'status stopped';
        statusText.textContent = 'Gestoppt';
        statusSym.className = 'dot white';
    }
}
// Initiale UI
updateUI();

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
function toggleButton() {
    if (!isRunning && !dataStream) {
        socket.emit('start_recording');
    }
    else if (isRunning && !dataStream) {
        console.log("Wait for DataStream")
    }
    else {
        socket.emit('stop_recording');
    }
}

let dataStream = false;
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//Sensor-Daten vom Backend in Empfang nehmen
socket.on('sensor_update', (data) => {
    // RGB
    if (data.rgb_frame) {
        document.getElementById('rgb-stream').src = 'data:image/jpeg;base64,' + data.rgb_frame;
    }
    
    if (data.rgb_frame2) {
        document.getElementById('rgb2-stream').src = 'data:image/jpeg;base64,' + data.rgb_frame2;
    }
    
    // TOF
    if (data.tof_scelet) {
        document.getElementById('tof-stream').src = 'data:image/jpeg;base64,' + data.tof_scelet;
    }
    
    /*
    // Gaze
    if (data.gaze) {
        document.getElementById('rgb2-stream').src = 'data:image/jpeg;base64,' + data.gaze;
    }
    */
    
    // Distraction Model
    if (data.distraction) {
        const label = Number(data.distraction.label);
        const prob = Number(data.distraction.prob_distracted);
        const nFrames = Number(data.distraction.n_frames);

        document.getElementById("probText").textContent =
            Number.isFinite(prob) ? prob.toFixed(3) : "-";

        document.getElementById("framesText").textContent =
            Number.isFinite(nFrames) ? nFrames : "-";

        document.getElementById("labelText").textContent =
            Number.isFinite(label) ? label : "-";

        const red = document.getElementById("light-red");
        const green = document.getElementById("light-green");

        if (label === 1) {
            red.classList.add("active");
            green.classList.remove("active");
        } else {
            green.classList.add("active");
            red.classList.remove("active");
        }
    }
    
    // Rasante Fahrweise Model
    if (data.fahrweise) {
        console.log(data.fahrweise.prediction)
        const prediction = data.fahrweise.prediction;
        const confidence = data.fahrweise.confidence;

        document.getElementById("fahr_probText").textContent =
            prediction ? prediction : "-";

        document.getElementById("fahr_framesText").textContent =
            confidence ? confidence : "-";


        const red = document.getElementById("fahr_light-red");
        const green = document.getElementById("fahr_light-green");

        console.log(prediction)
        if (prediction === "fast") {
            red.classList.add("active");
            green.classList.remove("active");
        } else {
            green.classList.add("active");
            red.classList.remove("active");
        }
    }
    
    // Eyetracker
    //if (data.eyetracker) {
    //    document.getElementById('eye-data').textContent = JSON.stringify(data.eyetracker);
    //}

    // SILAB
    if (data.silab) {
        const silab = data.silab;
        
        speed = silab['speed']; 
        steering = silab['steering'];
        acc_pedal = silab['acc_pedal'];
        brake_pedal = silab['brake_pedal'];
    }

    if (data.silab && data.rgb_frame && data.tof_scelet) {
        dataStream = true;
    }

    // Heartrate
    if (data.shimmer) {
        heart_rate_data = data.shimmer;

        if (heart_rate_data['sdnn']) {
            heart_rate_data_sdnn = Number(heart_rate_data['sdnn'])
        } else {
            heart_rate_data_sdnn = 0;
        }
        if (heart_rate_data['rmssd']) {
            heart_rate_data_rmssd = Number(heart_rate_data['rmssd'])
        }
        else {
            heart_rate_data_rmssd = 0;
        }
        console.log(heart_rate_data_sdnn, heart_rate_data_rmssd)
    }
});
