import {useEffect, useState, useMemo, useRef} from "react"
import {Rnd} from "react-rnd"
import WidgetCard from "./WidgetCard"
import {getDefaultMode, getSensorTitle} from "./widgetConfig"
import {getPreferredWidgetGridSize, GRID_COLS, GRID_ROW_HEIGHT, GRID_MARGIN} from "./widgetSizing"
import {debounce} from "lodash"

// Grid geometry (single source of truth lives in widgetSizing).
const COLS = GRID_COLS
const ROW_HEIGHT = GRID_ROW_HEIGHT
const MARGIN = GRID_MARGIN

function DashboardGrid({
                           sidebarCollapsed,
                           widgets,
                           setWidgets,
                           sensorData,
                           connected,
                           running,
                           saveEnabled = true,
                           project,
                           currentLayoutName,
                           layoutProject
                       }) {
    const [gridWidth, setGridWidth] = useState(window.innerWidth)
    const widgetSaveInit = useRef(true)
    const API_URL = "http://localhost:9999"

    const saveLayout = useMemo(
        () =>
            debounce((layout, widgets) => {
                const layoutNameOnly = currentLayoutName?.split("::")[1];

                if (!layoutNameOnly) return;

                fetch(`${API_URL}/api/layout/${project}/${layoutNameOnly}`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    credentials: "include",
                    body: JSON.stringify({
                        layout,
                        widgets,
                    }),
                }).catch((err) =>
                    console.error("Fehler beim Speichern:", err)
                )
            }, 1000),
        [project, currentLayoutName]
    )
    useEffect(() => {
        return () => {
            saveLayout.cancel()
        }
    }, [saveLayout])

    useEffect(() => {

        if (widgetSaveInit.current) {
            widgetSaveInit.current = false
            return
        }

        if (
            !saveEnabled ||
            project !== layoutProject
        ) {
            return
        }

        saveLayout(widgets.map(({i, x, y, w, h}) => ({i, x, y, w, h})), widgets)

    }, [widgets])

    useEffect(() => {

        const updateGridWidth = () => {

            const dashboard =
                document.querySelector(".dashboard-area")

            if (!dashboard) return

            // 40 = .dashboard-area horizontal padding (20px each side).
            setGridWidth(dashboard.clientWidth - 40)
        }

        updateGridWidth()

        window.addEventListener("resize", updateGridWidth)

        return () =>
            window.removeEventListener("resize", updateGridWidth)

    }, [sidebarCollapsed, widgets])

    // Width of a single grid column in pixels (matches react-grid-layout's math).
    const colWidth = (gridWidth - MARGIN * (COLS + 1)) / COLS

    // Grid units <-> pixels conversion so the data model stays in grid units
    // while react-rnd works in absolute pixels.
    const toPx = (widget) => ({
        x: widget.x * (colWidth + MARGIN) + MARGIN,
        y: widget.y * (ROW_HEIGHT + MARGIN) + MARGIN,
        width: widget.w * colWidth + (widget.w - 1) * MARGIN,
        height: widget.h * ROW_HEIGHT + (widget.h - 1) * MARGIN,
    })

    const toGrid = ({x, y, width, height}) => ({
        x: Math.max(0, (x - MARGIN) / (colWidth + MARGIN)),
        y: Math.max(0, (y - MARGIN) / (ROW_HEIGHT + MARGIN)),
        w: (width + MARGIN) / (colWidth + MARGIN),
        h: (height + MARGIN) / (ROW_HEIGHT + MARGIN),
    })

    // Axis-aligned overlap test in grid units. Touching edges do not count.
    const overlaps = (a, b) =>
        a.x < b.x + b.w &&
        a.x + a.w > b.x &&
        a.y < b.y + b.h &&
        a.y + a.h > b.y

    // A placement is only valid if it stays inside the grid. Without this, a
    // widget pushed off the right edge inflates the container's scroll width,
    // which lets bounds="parent" creep ever further right ("infinite" edge).
    const withinGrid = (r) =>
        r.x >= -1e-6 && r.y >= -1e-6 && r.x + r.w <= COLS + 1e-6

    // Slide the candidate out of any widget it overlaps, along the axis of
    // least penetration, so it comes to rest flush against the neighbour
    // instead of resetting to its original spot. Returns null if it cannot be
    // placed without overlap (e.g. fully boxed in).
    const resolveCollisions = (candidate, others) => {
        let resolved = {...candidate}

        for (let iteration = 0; iteration < 20; iteration++) {
            const hit = others.find((widget) => overlaps(resolved, widget))
            if (!hit) return withinGrid(resolved) ? resolved : null

            const overlapX =
                Math.min(resolved.x + resolved.w, hit.x + hit.w) - Math.max(resolved.x, hit.x)
            const overlapY =
                Math.min(resolved.y + resolved.h, hit.y + hit.h) - Math.max(resolved.y, hit.y)

            const candCenterX = resolved.x + resolved.w / 2
            const candCenterY = resolved.y + resolved.h / 2
            const hitCenterX = hit.x + hit.w / 2
            const hitCenterY = hit.y + hit.h / 2

            if (overlapX < overlapY) {
                resolved.x = Math.max(
                    0,
                    candCenterX < hitCenterX ? hit.x - resolved.w : hit.x + hit.w
                )
            } else {
                resolved.y = Math.max(
                    0,
                    candCenterY < hitCenterY ? hit.y - resolved.h : hit.y + hit.h
                )
            }
        }

        if (others.some((widget) => overlaps(resolved, widget))) return null
        return withinGrid(resolved) ? resolved : null
    }

    // Shrink the candidate into the free gap around where it was dropped,
    // keeping it in place instead of moving it elsewhere. The drop anchor is
    // the candidate's centre; neighbours bound that gap on all four sides, so a
    // too-big widget dropped *between* two others shrinks to span the gap
    // (clamped on both the left and right) rather than resetting. Returns null
    // if the anchor lands on a widget or the resulting gap is smaller than 1x1.
    const fitToFreeSpace = (candidate, others) => {
        const cx = candidate.x + candidate.w / 2
        const cy = candidate.y + candidate.h / 2

        // The drop anchor sits inside a neighbour: there is no gap here.
        if (
            others.some(
                (o) => o.x <= cx && cx <= o.x + o.w && o.y <= cy && cy <= o.y + o.h
            )
        ) {
            return null
        }

        // Walls of the free gap that contains the anchor.
        let left = 0
        let right = COLS
        let top = 0
        let bottom = Infinity

        for (const other of others) {
            const verticallyOverlaps =
                candidate.y < other.y + other.h && candidate.y + candidate.h > other.y
            if (verticallyOverlaps) {
                if (other.x + other.w <= cx) left = Math.max(left, other.x + other.w)
                if (other.x >= cx) right = Math.min(right, other.x)
            }

            const horizontallyOverlaps =
                candidate.x < other.x + other.w && candidate.x + candidate.w > other.x
            if (horizontallyOverlaps) {
                if (other.y + other.h <= cy) top = Math.max(top, other.y + other.h)
                if (other.y >= cy) bottom = Math.min(bottom, other.y)
            }
        }

        const x = Math.max(left, Math.min(candidate.x, right))
        const y = Math.max(top, Math.min(candidate.y, bottom))
        const w = Math.min(candidate.w, right - x)
        const h = Math.min(candidate.h, bottom - y)
        if (w < 1 || h < 1) return null

        const shrunk = {...candidate, x, y, w, h}
        return others.some((widget) => overlaps(shrunk, widget)) ? null : shrunk
    }

    const commitWidget = (id, geometry) => {
        setWidgets((currentWidgets) => {
            const current = currentWidgets.find((widget) => widget.i === id)
            const candidate = {...current, ...toGrid(geometry)}
            const others = currentWidgets.filter((widget) => widget.i !== id)

            // Snap flush against neighbours; if boxed in, shrink to fit the gap
            // at the drop spot. Only reset if even a 1x1 won't fit there.
            const resolved =
                resolveCollisions(candidate, others)
                ?? fitToFreeSpace(candidate, others)
            if (!resolved) {
                return [...currentWidgets]
            }

            const updatedWidgets = currentWidgets.map((widget) =>
                widget.i === id ? resolved : widget
            )

            if (saveEnabled && project === layoutProject) {
                saveLayout(updatedWidgets.map(({i, x, y, w, h}) => ({i, x, y, w, h})), updatedWidgets)
            }

            return updatedWidgets
        })
    }

    // Container height so the relatively-positioned area grows with content.
    // Extra slack below the content gives room to resize/drag downward, since
    // bounds="parent" would otherwise clamp at the current bottom-most widget.
    const contentBottom = widgets.reduce((max, widget) => {
        const {y, height} = toPx(widget)
        return Math.max(max, y + height + MARGIN)
    }, 0)
    const containerHeight = contentBottom + ROW_HEIGHT * 12

    if (widgets.length === 0) {
        return (
            <div className="empty-state">
                <h3>Dashboard is empty</h3>
                <p>Add widgets from the left panel to start building your layout.</p>
            </div>
        )
    }

    return (
        <div
            className="rnd-layout"
            style={{position: "relative", width: gridWidth, height: containerHeight}}
        >
            {widgets.map((widget) => {
                const px = toPx(widget)
                return (
                    <Rnd
                        key={widget.i}
                        bounds="parent"
                        position={{x: px.x, y: px.y}}
                        size={{width: px.width, height: px.height}}
                        minWidth={colWidth}
                        minHeight={ROW_HEIGHT}
                        dragHandleClassName="widget-body"
                        onDragStop={(e, d) =>
                            commitWidget(widget.i, {x: d.x, y: d.y, width: px.width, height: px.height})
                        }
                        onResizeStop={(e, direction, ref, delta, position) =>
                            commitWidget(widget.i, {
                                x: position.x,
                                y: position.y,
                                width: ref.offsetWidth,
                                height: ref.offsetHeight,
                            })
                        }
                    >
                        <WidgetCard
                            widget={widget}
                            onDelete={(id) => setWidgets((items) => items.filter((item) => item.i !== id))}
                            onChangeView={(id, nextView) => {
                                setWidgets((items) =>
                                    items.map((item) =>
                                        item.i === id
                                            ? (() => {
                                                const nextMode = getDefaultMode(nextView)
                                                const preferred = getPreferredWidgetGridSize(nextView, nextMode)

                                                return {
                                                    ...item,
                                                    view: nextView,
                                                    mode: nextMode,
                                                    title: getSensorTitle(nextView),
                                                    w: preferred.w,
                                                    h: preferred.h,
                                                }
                                            })()
                                            : item,
                                    ),
                                )
                            }}
                            onChangeMode={(id, nextMode) => {
                                setWidgets((items) =>
                                    items.map((item) => {
                                        if (item.i !== id) return item

                                        const preferred = getPreferredWidgetGridSize(item.view, nextMode)
                                        return {
                                            ...item,
                                            mode: nextMode,
                                            w: preferred.w,
                                            h: preferred.h,
                                        }
                                    }),
                                )
                            }}
                            onUpdateWidget={(id, patch) => {
                                setWidgets((items) =>
                                    items.map((item) =>
                                        item.i === id ? {...item, ...patch} : item,
                                    ),
                                )
                            }}
                            sensorData={sensorData}
                            connected={connected}
                            running={running}
                        />
                    </Rnd>
                )
            })}
        </div>
    )
}

export default DashboardGrid
