# react_app — Driving-Simulator Sensor Dashboard (Frontend)

React/Vite frontend for a driving-simulator sensor dashboard. It connects to a
Python/Flask backend over Socket.IO, receives one combined payload per
`sensor_update` event (SiLab telemetry, Shimmer biosignals, eye tracker, RGB and
ToF camera frames, plus `heartbeat` and `sensor_latency`), and renders the data
as configurable, drag-and-resizable widgets on a grid. Layouts are persisted per
project through the backend REST API.

---

## 1. Tech stack

| Area | Choice |
|------|--------|
| UI library | **React 19** (`react` / `react-dom` `^19.2.4`) |
| Build tool | **Vite 8** (`vite ^8.0.4`, `@vitejs/plugin-react ^6.0.1`) |
| Module type | ESM (`"type": "module"`) |
| Routing | `react-router-dom ^7.15.0` |
| Realtime transport | `socket.io-client ^4.8.3` |
| Charts | `recharts ^3.8.1` |
| Drag & resize | `react-rnd ^10.5.3` |
| Icons | `react-icons ^5.6.0`, `lucide-react ^1.18.0` |
| Notifications | `react-toastify ^11.1.0` |
| Utilities | `lodash ^4.18.1` (uses `debounce`) |
| Linting | ESLint 9 (`eslint ^9.39.4`, `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`) |

> Versions are taken verbatim from `package.json`. The project name there is
> `react_app`, version `0.0.0`, and it is marked `private`.

---

## 2. Prerequisites

- **Node.js** — no `engines` field in `package.json` and no `.nvmrc` in the repo,
  so the required version is not pinned. This setup was verified on **Node
  v25.8.2** (npm 11.11.1). Vite 8 / React 19 require at minimum a current Node
  release; a recent LTS (Node 20+) is recommended for reproducibility.
- **Package manager** — a `package-lock.json` is committed, so **npm** is the
  expected package manager (verified with **npm 11.11.1**). No `yarn.lock` /
  `pnpm-lock.yaml` present.
- A running **Flask backend** reachable over HTTP and Socket.IO (see
  [Configuration](#5-configuration) and the repo-level `STARTUP.md`).

---

## 3. Installation & run

Install dependencies:

```bash
npm install
```

The scripts below are exactly those defined in `package.json`:

```bash
# Start the Vite dev server (HMR)
npm run dev
```

```bash
# Production build into dist/
npm run build
```

```bash
# Serve the production build locally
npm run preview
```

```bash
# Lint the project
npm run lint
```

> See the repo-level `STARTUP.md` for the full local setup (backend +
> frontend). It documents the `npm run build` + `npm run preview` workflow and
> notes that `preview` typically serves at `http://localhost:4173`.

---

## 4. Configuration

### Socket.IO endpoint

The socket connection URL is resolved in `src/components/dashboard/Dashboard.jsx`:

```js
const SOCKET_URL =
    import.meta.env.VITE_SOCKET_URL
    || "http://localhost:9999"
```

- Set **`VITE_SOCKET_URL`** (a Vite env variable, e.g. in a `.env` file) to point
  the dashboard at a non-default backend.
- If unset, it falls back to `http://localhost:9999`.

> No `.env` / `.env.example` file is committed (`.gitignore` excludes `*.local`),
> so there is nothing to copy — create one yourself if you need to override the
> default.

### REST API base URL

The REST base URL (`API_URL`) is **hardcoded** to `http://localhost:9999` and is
**not** read from an env variable. It appears in several files:

- `src/components/dashboard/Dashboard.jsx` (`/api/layouts/...`, `/api/layout/...`)
- `src/components/dashboard/DashboardGrid.jsx` (layout autosave)
- `src/components/dashboard/Sidebar.jsx` (layout list / load / save / delete)
- `src/App.jsx` (`/api/participants/...`, `/api/participant/...`)

> Note: this is fine for the intended **local-only** setup — backend and frontend
> run on the same machine at port `9999`. It only matters if you ever serve the
> frontend against a different host/port: there is no single config source, so
> you would need to edit each of these files (or refactor them to read
> `import.meta.env`, like `VITE_SOCKET_URL` above).

---

## 5. Project structure

```
react_app/
├─ index.html                 # Vite entry HTML (#root)
├─ vite.config.js             # Vite config (@vitejs/plugin-react only)
├─ eslint.config.js           # ESLint 9 flat config
├─ package.json               # scripts + dependencies
├─ STARTUP.md                 # local setup guide (backend + frontend)
└─ src/
   ├─ main.jsx                # React root + BrowserRouter routes
   ├─ App.jsx                 # "/"  → ProjectManager (project/participant select)
   ├─ components/
   │  ├─ project/             # project & participant selection screens
   │  │  ├─ ProjectTable.jsx
   │  │  └─ SilabSimulationSelect.jsx
   │  ├─ dashboard/           # "/dashboard" screen
   │  │  ├─ Dashboard.jsx           # socket owner, header status, store ingestion
   │  │  ├─ DashboardGrid.jsx       # grid placement / drag-resize (react-rnd)
   │  │  ├─ WidgetCard.jsx          # picks the widget body by widget.view + memo
   │  │  ├─ widgetConfig.js         # SENSOR_WIDGETS registry + helpers
   │  │  ├─ widgetSizing.js         # grid geometry + preferred widget sizes
   │  │  ├─ Sidebar.jsx             # add widgets, save/load/delete layouts
   │  │  └─ StartSensorPopup.jsx    # sensor availability (heartbeat + latency)
   │  └─ widgets/             # the actual widget renderers
   │     ├─ EyeTracker.jsx
   │     ├─ silab/            # SilabCockpit, SilabSignalChart/Text, silabSignals.js
   │     └─ shimmer/          # ShimmerSignalChart/Text, shimmerSignals.js
   ├─ utils/
   │  ├─ telemetryStore.js    # rolling buffer for SiLab chart signals
   │  └─ shimmerStore.js      # rolling buffer for Shimmer chart signals
   └─ styles/                 # DashboardStyle.css, Popup.css, Sidebar.css, ...
```

Routing (`src/main.jsx`): `/` → `App` (project/participant manager), `/dashboard`
→ `Dashboard`. The dashboard reads the selected `project` / `participant` from
`location.state` (passed via `navigate` after a participant is chosen).

---

## 6. Architecture & data flow

A single Socket.IO connection is created in `Dashboard.jsx`. Every
`sensor_update` payload is the single source of truth for one render frame and is
fanned out to the widgets through `sensorData`. Chart widgets additionally read
from shared rolling buffers (`telemetryStore` / `shimmerStore`) so their history
survives a widget being removed and re-added.

```
Flask backend
     │  socket.io  "sensor_update"  { silab, shimmer, eyetracker,
     │                                rgb_frame, rgb_frame2, tof_scelet,
     ▼                                heartbeat, sensor_latency }
Dashboard.jsx  (single socket owner)
     ├─ setSensorData(payload)            → latest frame for all widgets
     ├─ setLastPacketTime(new Date())     → "Last packet" header badge
     ├─ payload.silab   → telemetryStore.addDataPoint(...)   (throttled, 200 ms)
     ├─ payload.shimmer → shimmerStore.addDataPoint(...)     (throttled, 1000 ms)
     └─ payload.heartbeat / payload.sensor_latency
                                          → header SensorStatusBadge + StartSensorPopup
     │
     ▼  sensorData (+ connected, running)
DashboardGrid.jsx  (react-rnd placement, grid units ↔ pixels, autosave layout)
     │
     ▼  widget + sensorData
WidgetCard.jsx     (memo(WidgetCard, areWidgetPropsEqual))
     │  selects body by widget.view / mode:
     ├─ "silab"      → SilabCockpit | SilabSignalChart | SilabSignalText | raw JSON
     ├─ "shimmer"    → ShimmerSignalChart | ShimmerSignalText | raw JSON
     ├─ "eyetracker" → EyeTracker | raw JSON
     └─ "tof" / "rgb_front" / "rgb_back" → <img> from frame bytes (Blob → objectURL)
```

### Key pieces

- **`Dashboard.jsx`** — owns the socket (`io(SOCKET_URL)`), tracks `connected` /
  `running`, and is the *single owner of telemetry ingestion*. On each
  `sensor_update` it throttles SiLab points into `telemetryStore` and Shimmer
  points into `shimmerStore`, then calls `setSensorData(payload)`. The header
  renders six `SensorStatusBadge`s from `sensorData.heartbeat`, each with a
  hover/restart icon that emits `restart_sensor` for that one sensor.
- **`widgetConfig.js`** — the `SENSOR_WIDGETS` registry (key, label, default
  mode, icon, modes). Helpers: `getSensorConfig`, `getSensorTitle`,
  `getDefaultMode`, `getModeOptions`, `getNormalizedMode`. Both the sidebar
  (add-widget buttons) and `WidgetCard` (mode dropdown) derive from it.
- **`widgetSizing.js`** — single source of truth for grid geometry
  (`GRID_COLS = 12`, `GRID_ROW_HEIGHT = 36`, `GRID_MARGIN = 4`) and per-widget
  preferred sizes. `getPreferredWidgetGridSize(view, mode)` converts a preferred
  pixel size to grid units (used when a widget is created or its view/mode
  changes). Image widgets derive their aspect ratio from `STREAM_RESOLUTION`.
- **`WidgetCard.jsx`** — chooses the body component from `widget.view` and the
  normalized `mode`, and reads its slice of `sensorData` (`silab`, `shimmer`,
  `eyetracker`, `rgb_frame`, `rgb_frame2`, `tof_scelet`). Image modes turn the
  frame bytes into a `Blob` → `URL.createObjectURL` and revoke it on cleanup. It
  is wrapped in `memo(WidgetCard, areWidgetPropsEqual)` so a widget only
  re-renders when *its* relevant data changes.
- **`telemetryStore` / `shimmerStore`** — singleton rolling buffers
  (`subscribe` / `addDataPoint` / `getData` / `reset`). The chart components
  (`SilabSignalChart`, `ShimmerSignalChart`) subscribe directly and self-update,
  which is why `areWidgetPropsEqual` returns `true` (skip prop re-render) for
  `line` charts and only re-renders the *text* display when the selected signal's
  value actually changes.
- **`StartSensorPopup.jsx`** — opened by "Start Sensor". It tracks per-sensor
  start time, marks each sensor "Verbunden" once its `heartbeat[key]` arrives,
  and shows `sensor_latency[key].latency_ms`. The **OK** button is enabled only
  when `allReady` (every sensor in its `SENSORS` list has connected).

---

## 7. Available sensors / widgets

From `SENSOR_WIDGETS` in `widgetConfig.js` (the registry used by the sidebar and
the mode dropdown). `defaultMode` is shown in **bold**.

| key | label | modes (`value` → label) |
|-----|-------|-------------------------|
| `silab` | SiLab | **`cockpit`** → Cockpit, `line` → Signal, `raw` → Raw |
| `shimmer` | Shimmer | **`line`** → Signal, `raw` → Raw |
| `eyetracker` | Eyetracker | **`gaze`** → Gaze, `raw` → Raw |
| `tof` | ToF Camera | **`image`** → Image |
| `rgb_front` | RGB Front | **`image`** → Image |
| `rgb_back` | RGB Back | **`image`** → Image |

> Note the **two key spaces**. The widget registry / `widget.view` uses
> `tof` / `rgb_front` / `rgb_back`, while the `sensor_update` payload (and the
> header / popup) uses the backend keys `tof_scelet` / `rgb_frame` / `rgb_frame2`.
> `WidgetCard` maps between them.

### SiLab signals (`line` mode)

`silabSignals.js` exposes `SILAB_SIGNALS`: `speed`, `steering`, `gas`, `brake`,
`clutch`, `rpm`, `x`, `y`, `z`, `pitch`, `roll`, `gear`. Each can be shown as a
**Chart** or as **Text**.

### Shimmer signals (`line` mode)

`shimmerSignals.js` exposes `SHIMMER_SIGNALS`: `hr` (Heart rate), `rmssd`,
`sdnn`, `skin_resistance` — each with backend field aliases and a **Chart** /
**Text** display.

---

## 8. Adding a new sensor

For the end-to-end procedure (backend logger, payload, etc.), follow the existing
project documentation.

**Frontend touchpoints** (this app only):

- **`widgetConfig.js`** — add an entry to `SENSOR_WIDGETS` (`key`, `label`,
  `defaultMode`, `icon`, `modes`). This automatically adds the sidebar button and
  the mode dropdown.
- **`WidgetCard.jsx`** — render the new body for `widget.view` (and read the
  correct `sensorData[...]` key), **and** add a matching branch to
  `areWidgetPropsEqual` so the widget actually re-renders on new data (see
  [Troubleshooting](#9-troubleshooting)).
- **`widgetSizing.js`** — give it a preferred size in `getPreferredWidgetSize`
  (and a `STREAM_RESOLUTION` entry if it is an image/stream widget).
- **`Dashboard.jsx`** — add the sensor to the header status array
  (`[["silab","SiLab"], …]`) using its **payload key** so a `SensorStatusBadge`
  appears; if it is a charted signal, add the corresponding store ingestion in
  the `sensor_update` handler.
- **`StartSensorPopup.jsx`** — add it to the `SENSORS` list (with `getSensorIcon`)
  so it is tracked for heartbeat/latency and counted in `allReady`.
- (Charts only) add a `*Signals.js` definition and a store under `utils/` mirroring
  `telemetryStore` / `shimmerStore`.

---

## 9. Troubleshooting

- **A widget doesn't update with live data.** `WidgetCard` is wrapped in
  `memo(WidgetCard, areWidgetPropsEqual)`. If a new `widget.view` has no branch in
  `areWidgetPropsEqual`, the function falls through to `return true`, telling React
  to **skip** the re-render. Add a branch comparing the relevant
  `sensorData[...]` slice (or return `false` for always-live data like `raw`
  mode, which already short-circuits to `return false`).
- **The "Start Sensor" popup's OK button stays disabled.** OK is gated by
  `allReady`, which requires **every** sensor in `StartSensorPopup`'s `SENSORS`
  list to have reported a `heartbeat`. If one sensor never sends a heartbeat (not
  running / not connected), the button stays disabled. Check the per-sensor row
  ("Suche…" vs "Verbunden") and the backend heartbeat for that `key`. Adding a new
  sensor to `SENSORS` also makes it a precondition for OK.
- **Header shows "Socket disconnected" / no frames.** The dashboard could not
  reach the backend. Verify the Flask backend is running and that `VITE_SOCKET_URL`
  (or the `http://localhost:9999` default) and the REST `API_URL` point at it. The
  **Last packet** badge shows "no packets yet" until the first `sensor_update`.
- **Image widget shows "No frame yet."** No frame bytes for that view have arrived
  in `sensorData` yet — start the corresponding sensor. Remember the payload key
  (`tof_scelet` / `rgb_frame` / `rgb_frame2`) differs from the widget key.
- **Layout doesn't save / "Fremdes Layout."** Layout autosave only runs when the
  loaded layout belongs to the current project (`project === layoutProject`).
  Layouts from another project can only be saved under a new name (see the sidebar
  warning).
```
