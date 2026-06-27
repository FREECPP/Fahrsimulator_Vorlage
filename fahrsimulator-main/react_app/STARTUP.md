# Startup Guide (Frontend + Flask Backend)

This guide is for colleagues who want to run the dashboard locally.

## 1) One-time setup

From the project root:

    cd ~/fahrsimulator-main

Create and activate a Python environment (optional, but recommended):

    python3 -m venv .venv
    source .venv/bin/activate

Install backend dependencies:

    pip install -r requirements.txt

Install frontend dependencies:

    cd react_app
    npm install

## 2) Start the backend (Terminal 1)

From the project root:

    cd ~/fahrsimulator-main
    source .venv/bin/activate
    python flask_app.py

Keep this terminal running.

## 3) Build and start the frontend (Terminal 2)

From the frontend folder:

    cd ~/fahrsimulator-main/react_app
    npm run build
    npm run preview

Keep this terminal running.

## 4) Open the app

Open the Vite URL shown in Terminal 2 (typically http://localhost:4173).

## Notes

- The frontend expects the Socket endpoint from VITE_SOCKET_URL.
- If VITE_SOCKET_URL is not set, frontend default is http://localhost:9999.
- Make sure Flask is running on the same port (configured in config.ini / backend config).
