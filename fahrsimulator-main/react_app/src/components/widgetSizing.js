// Grid geometry (single source of truth, also imported by DashboardGrid).
export const GRID_COLS = 12
export const GRID_ROW_HEIGHT = 36
export const GRID_MARGIN = 4

// Preferred widget sizes in pixels. Use getPreferredWidgetGridSize to get the
// equivalent grid units for the data model.
export function getPreferredWidgetSize(view, mode) {
  if (view === "silab") {
    if (mode === "cockpit") return { width: 600, height: 200 }
    if (mode === "line") return { width: 740, height: 500 }
    return { width: 600, height: 200 }
  }

  if (view === "shimmer") {
    if (mode === "chart") return { width: 660, height: 690 }
    return { width: 660, height: 690 }
  }

  if (view === "tof" || view === "rgb_front" || view === "rgb_back") {
    return { width: 480, height: 300 }
  }

  if (view === "eyetracker") {
    return { width: 470, height: 320 }
  }

  return { width: 480, height: 300 }
}

// Column width derived from the live dashboard width (falls back to the window
// width before the dashboard has mounted). Matches DashboardGrid's math.
function currentColWidth() {
  const dashboard =
    typeof document !== "undefined" ? document.querySelector(".dashboard-area") : null
  const gridWidth = (dashboard?.clientWidth ?? window.innerWidth) - 32
  return (gridWidth - GRID_MARGIN * (GRID_COLS + 1)) / GRID_COLS
}

// Preferred size converted from pixels to grid units for the widget data model.
export function getPreferredWidgetGridSize(view, mode) {
  const { width, height } = getPreferredWidgetSize(view, mode)
  const colWidth = currentColWidth()
  return {
    w: (width + GRID_MARGIN) / (colWidth + GRID_MARGIN),
    h: (height + GRID_MARGIN) / (GRID_ROW_HEIGHT + GRID_MARGIN),
  }
}
