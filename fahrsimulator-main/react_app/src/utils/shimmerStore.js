// Rolling buffer for Shimmer (HR / HRV / skin resistance) telemetry. Mirrors
// telemetryStore: ingestion has a single owner (Dashboard) and any number of
// ShimmerChart widgets read from here, so the history survives a widget being
// removed and re-added instead of resetting with the component.
const THROTTLE_MS = 1000;
const MAX_WINDOW_MINUTES = 30;
const MAX_POINTS = Math.ceil(((MAX_WINDOW_MINUTES * 60 * 1000) / THROTTLE_MS) * 1.5);

class ShimmerStore {
  constructor() {
    this.data = [];
    this.startTime = null;
    this.listeners = new Set();
  }

  initStartTime() {
    if (!this.startTime) {
      this.startTime = Date.now();
    }
    return this.startTime;
  }

  addDataPoint(point) {
    this.data.push(point);
    if (this.data.length > MAX_POINTS) {
      this.data.shift();
    }
    this.notify();
  }

  getData() {
    return [...this.data];
  }

  getStartTime() {
    return this.startTime;
  }

  reset() {
    this.data = [];
    this.startTime = null;
    this.notify();
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  notify() {
    this.listeners.forEach(listener => listener());
  }
}

export const shimmerStore = new ShimmerStore();
export { THROTTLE_MS, MAX_POINTS };
