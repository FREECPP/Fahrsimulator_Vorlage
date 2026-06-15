const THROTTLE_MS = 200;
const MAX_WINDOW_MINUTES = 30;
const MAX_POINTS = Math.ceil(((MAX_WINDOW_MINUTES * 60 * 1000) / THROTTLE_MS) * 1.5);

class TelemetryStore {
// ...

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

export const telemetryStore = new TelemetryStore();
export { THROTTLE_MS, MAX_POINTS };
