export function getPreferredWidgetSize(view, mode) {
  if (view === "silab") {
    if (mode === "pedals") return { w: 6, h: 3 }
    return { w: 6, h: 3 }
  }

  if (view === "shimmer") {
    if (mode === "chart") return { w: 12, h: 6 }
    if (mode === "metrics") return { w: 12, h: 6 }
    return { w: 12, h: 6 }
  }

  if (view === "tof" || view === "rgb_front" || view === "rgb_back") {
    if (mode === "image") return { w: 4, h: 3 }
    return { w: 4, h: 3 }
  }

  if (view === "eyetracker") {
    return { w: 6, h: 3 }
  }

  return { w: 4, h: 4 }
}

export function getWidgetConstraints(view) {
  if (view === "silab") {
    return { minW: 2, minH: 3 }
  }

  if (view === "shimmer") {
    return { minW: 3, minH: 4 }
  }

  if (view === "tof" || view === "rgb_front" || view === "rgb_back") {
    return { minW: 3, minH: 3 }
  }

  return { minW: 2, minH: 2 }
}
