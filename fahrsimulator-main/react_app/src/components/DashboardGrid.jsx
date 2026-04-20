import {useEffect, useState, useMemo} from "react"
import GridLayout from "react-grid-layout"
import "react-grid-layout/css/styles.css"
import "react-resizable/css/styles.css"
import WidgetCard from "./WidgetCard"
import {debounce} from "lodash"

function DashboardGrid({widgets, setWidgets, sensorData, connected, running}) {
    const [gridWidth, setGridWidth] = useState(1000)

    const API_URL = "http://localhost:9999"
    const PROJECT = "demo3"

    const saveLayout = useMemo(
        () =>
            debounce((layout, widgets) => {

                fetch(`http://localhost:9999/api/layout/${PROJECT}`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    credentials: "include",
                    body: JSON.stringify({layout, widgets}),
                }).catch((err) =>
                    console.error("Fehler beim Speichern:", err)
                )
            }, 1000),
        []
    )
    // ✅ Cleanup für debounce (wichtig gegen Memory Leaks)
    useEffect(() => {
        return () => {
            saveLayout.cancel()
        }
    }, [saveLayout])


    useEffect(() => {
        const updateGridWidth = () => {
            const sidebarOffset = window.innerWidth <= 1024 ? 40 : 340
            setGridWidth(Math.max(320, window.innerWidth - sidebarOffset))
        }

        updateGridWidth()
        window.addEventListener("resize", updateGridWidth)
        return () => window.removeEventListener("resize", updateGridWidth)
    }, [])

    const layout = widgets.map((widget) => ({
        i: widget.i,
        x: widget.x,
        y: widget.y,
        w: widget.w,
        h: widget.h,
        minW: 2,
        minH: 2,
    }))

    const handleLayoutChange = (newLayout) => {
        setWidgets((currentWidgets) => {
            const updatedWidgets = currentWidgets.map((widget) => {
                const layoutItem = newLayout.find((item) => item.i === widget.i)
                return layoutItem ? {...widget, ...layoutItem} : widget
            })

            saveLayout(newLayout, updatedWidgets)

            return updatedWidgets
        })
    }


    if (widgets.length === 0) {
        return (
            <div className="empty-state">
                <h3>Dashboard is empty</h3>
                <p>Add widgets from the left panel to start building your layout.</p>
            </div>
        )
    }

    return (
        <GridLayout
            className="layout"
            layout={layout}
            cols={12}
            rowHeight={36}
            width={gridWidth}
            margin={[12, 12]}
            onLayoutChange={handleLayoutChange}
            draggableHandle=".widget-header"
        >
            {widgets.map((widget) => (
                <div key={widget.i}>
                    <WidgetCard
                        widget={widget}
                        onDelete={(id) => setWidgets((items) => items.filter((item) => item.i !== id))}
                        onChangeView={(id, nextView) => {
                            setWidgets((items) =>
                                items.map((item) =>
                                    item.i === id
                                        ? {
                                            ...item,
                                            view: nextView,
                                            title: nextView.charAt(0).toUpperCase() + nextView.slice(1),
                                        }
                                        : item,
                                ),
                            )
                        }}
                        sensorData={sensorData}
                        connected={connected}
                        running={running}
                    />
                </div>
            ))}
        </GridLayout>
    )
}

export default DashboardGrid
