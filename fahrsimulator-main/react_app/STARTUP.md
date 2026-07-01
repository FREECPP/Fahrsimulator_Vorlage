# Startup Guide (Frontend + Flask Backend)

This guide is for colleagues who want to run the dashboard locally.

> Note on operating systems: the full setup with real sensors / SILAB runs on
> **Windows**. macOS and Linux can run the backend in mock mode for UI/preview
> work, but not the actual hardware acquisition.
> Commands below are shown for **macOS/Linux** and **Windows** where they differ.

## 1) One-time setup

Go to the project root (the folder that contains `flask_app.py`).

Create and activate a Python environment (recommended):

macOS / Linux:

    python3 -m venv .venv
    source .venv/bin/activate

Windows (PowerShell):

    py -3 -m venv .venv
    .venv\Scripts\Activate.ps1

Windows (cmd):

    py -3 -m venv .venv
    .venv\Scripts\activate

Install only necessary backend dependencies to be able to run flask_app.py:

    pip install flask flask-cors flask-socketio flask-sqlalchemy opencv-python numpy pyautogui

Install frontend dependencies:

    cd react_app
    npm install

## 2) Start the backend (Terminal 1)

To add a participant locally (without the simulator) you need a simulations
directory the backend can read. Temporarily point it at the bundled demo via
the `SIMULATION_DIR` environment variable — without it the backend uses the
real simulator path, which does not exist locally.

The directory must contain at least one `.cfg` simulation file; the repo ships
a demo at `SILAB/Projects/SILABDemo/TestSimulation.cfg`. That `.cfg` is what
shows up in the simulation dropdown when adding a participant. Point
`SIMULATION_DIR` at the folder that contains it (not at the file itself), and
adjust the path if your demo lives elsewhere:

macOS / Linux:

    export SIMULATION_DIR="SILAB/Projects/SILABDemo"

Windows (PowerShell):

    $env:SIMULATION_DIR = "SILAB\Projects\SILABDemo"

Windows (cmd):

    set SIMULATION_DIR=SILAB\Projects\SILABDemo

Then, from the project root with the venv activated:

    python flask_app.py

(Use `python3` on macOS/Linux if `python` is not on your PATH.)

Keep this terminal running. The backend listens on the port from `config.ini`
(`[General] PORT`, default 9999).

## 3) Start the frontend (Terminal 2)

From the `react_app` folder, choose one of the two modes:

### a) Local development / mock data (recommended for testing)

    npm run dev

Use this when you want to work locally. It runs Vite in dev mode, which is the
**only** mode that shows the local **Start** button (mock sensor stream) — that
button is hidden in production builds on purpose. The dev server URL is shown in
the terminal (typically http://localhost:5173).

### b) Production-like preview

    npm run build
    npm run preview

This serves the optimized production build (typically http://localhost:4173).
The local mock **Start** button is intentionally NOT available here.

Keep this terminal running.

## 4) Open the app

Open the Vite URL shown in Terminal 2 (dev: http://localhost:5173,
preview: http://localhost:4173).

## Notes

- The frontend expects the Socket endpoint from VITE_SOCKET_URL.
- If VITE_SOCKET_URL is not set, the frontend default is http://localhost:9999.
- Make sure Flask is running on the same port (configured in config.ini under
  [General], or via the PORT environment variable).
