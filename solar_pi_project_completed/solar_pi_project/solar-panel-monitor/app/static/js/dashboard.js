/* Solar Panel Performance Monitor — Dashboard frontend.

Polls the JSON API for live readings, updates the measurement cards, live
charts, historical energy chart, and history table without refreshing the
page. Handles loading, empty-data, and disconnected-sensor states.
*/

(function () {
  "use strict";

  const POLL_INTERVAL_MS = 2000;
  const MAX_LIVE_POINTS = 60;
  const DEFAULT_TABLE_LIMIT = 50;

  const els = {
    voltage: document.getElementById("val-voltage"),
    current: document.getElementById("val-current"),
    power: document.getElementById("val-power"),
    energyToday: document.getElementById("val-energy-today"),
    energyTotal: document.getElementById("val-energy-total"),
    miniVoltage: document.getElementById("mini-voltage"),
    miniCurrent: document.getElementById("mini-current"),
    miniPower: document.getElementById("mini-power"),
    miniEnergyToday: document.getElementById("mini-energy-today"),
    miniEnergyTotal: document.getElementById("mini-energy-total"),
    modeBadge: document.getElementById("mode-badge"),
    sensorBadge: document.getElementById("sensor-badge"),
    errorBanner: document.getElementById("error-banner"),
    errorBannerText: document.getElementById("error-banner-text"),
    tableWrap: document.getElementById("table-wrap"),
    historyBody: document.getElementById("history-body"),
    emptyState: document.getElementById("empty-state"),
    disconnectedState: document.getElementById("disconnected-state"),
    tableCount: document.getElementById("table-count"),
    filterStart: document.getElementById("filter-start"),
    filterEnd: document.getElementById("filter-end"),
    btnApplyFilters: document.getElementById("btn-apply-filters"),
    btnClearFilters: document.getElementById("btn-clear-filters"),
  };

  // Live chart rolling buffers.
  const live = {
    voltage: { t: [], v: [] },
    current: { t: [], v: [] },
    power: { t: [], v: [] },
  };

  let charts = {};
  let pollingTimer = null;
  let lastCurrent = null;
  let isDisconnectedShown = false;

  // ------------------------------------------------------------------ #
  // Helpers
  // ------------------------------------------------------------------ #
  function $q(url, { signal } = {}) {
    return fetch(url, { signal, headers: { Accept: "application/json" } });
  }

  function showError(message) {
    if (!message) {
      els.errorBanner.classList.add("hidden");
      return;
    }
    els.errorBannerText.textContent = message;
    els.errorBanner.classList.remove("hidden");
  }

  function hideError() {
    showError(null);
  }

  function fmtNum(value, decimals) {
    if (value === null || value === undefined || Number.isNaN(value)) return "--";
    return Number(value).toFixed(decimals ?? 2);
  }

  function fmtTime(iso) {
    if (!iso) return "--";
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch (e) {
      return iso;
    }
  }

  function fmtDate(iso) {
    if (!iso) return "--";
    try {
      const d = new Date(iso);
      return d.toLocaleDateString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (e) {
      return iso;
    }
  }

  function setCard(valueEl, unitEl, miniEl, value, unit, mini, decimals) {
    const text = fmtNum(value, decimals);
    const stale = value === null || value === undefined || Number.isNaN(value);
    valueEl.textContent = text;
    valueEl.classList.toggle("stale", stale);
    if (unitEl) unitEl.textContent = unit;
    if (miniEl) {
      miniEl.textContent = mini !== undefined ? mini : "--";
      miniEl.classList.toggle("stale", stale);
    }
  }

  // ------------------------------------------------------------------ #
  // Charts
  // ------------------------------------------------------------------ #
  function createLiveChart(ctxId, label, color) {
    const ctx = document.getElementById(ctxId).getContext("2d");
    return new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label,
            borderColor: color,
            backgroundColor: color + "22",
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
            fill: true,
            data: [],
          },
        ],
      },
      options: {
        animation: { duration: 0 },
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "nearest", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: { mode: "index", intersect: false },
        },
        scales: {
          x: { display: false },
          y: {
            beginAtZero: true,
            grid: { color: "#1e3a5f" },
            ticks: { color: "#94a3b8", font: { size: 10 } },
          },
        },
      },
    });
  }

  function initCharts() {
    charts.voltage = createLiveChart("chart-voltage", "Voltage (V)", "#38bdf8");
    charts.current = createLiveChart("chart-current", "Current (mA)", "#4ade80");
    charts.power = createLiveChart("chart-power", "Power (W)", "#fbbf24");
    charts.energy = createEnergyChart();
  }

  function createEnergyChart() {
    const ctx = document.getElementById("chart-energy").getContext("2d");
    return new Chart(ctx, {
      type: "bar",
      data: { labels: [], datasets: [{ label: "Energy (Wh/day)", data: [], backgroundColor: "#22c55e" }] },
      options: {
        animation: { duration: 0 },
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { mode: "index", intersect: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: "#94a3b8", font: { size: 10 } } },
          y: {
            beginAtZero: true,
            grid: { color: "#1e3a5f" },
            ticks: { color: "#94a3b8", font: { size: 10 } },
          },
        },
      },
    });
  }

  function pushLive(buffer, time, value) {
    buffer.t.push(time);
    buffer.v.push(value === null || value === undefined ? null : value);
    if (buffer.t.length > MAX_LIVE_POINTS) {
      buffer.t.shift();
      buffer.v.shift();
    }
  }

  function updateLiveChart(chart, buffer) {
    chart.data.labels = buffer.t;
    chart.data.datasets[0].data = buffer.v;
    chart.update("none");
  }

  function updateEnergyChart(daily) {
    const chart = charts.energy;
    chart.data.labels = daily.map((d) => d.date);
    chart.data.datasets[0].data = daily.map((d) => d.energy_wh);
    chart.update("none");
  }

  // ------------------------------------------------------------------ //
  // API fetch helpers
  // ------------------------------------------------------------------ #
  async function fetchJson(path) {
    const res = await fetch(path, { headers: { Accept: "application/json" } });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    return res.json();
  }

  // ------------------------------------------------------------------ #
  # UI updates
  # ------------------------------------------------------------------ #
  function updateStatusBadge(status) {
    if (!status) return;
    const modeEl = els.modeBadge;
    const sensorEl = els.sensorBadge;

    const isSim = status.mode === "simulation";
    modeEl.textContent = isSim ? "Simulation" : "Hardware";
    modeEl.className = "badge" + (isSim ? " mode-sim" : " mode-hw");

    const connected = status.connected;
    sensorEl.textContent = connected ? "Connected" : "Disconnected";
    sensorEl.className = "badge status-badge" + (connected ? " status-ok" : " status-off");

    // Show disconnected banner once when the physical sensor is unavailable.
    if (!isSim && !connected && !isDisconnectedShown) {
      isDisconnectedShown = true;
      els.disconnectedState.classList.remove("hidden");
      showError("INA219 sensor disconnected — readings unavailable until it recovers.");
    } else if (connected || isSim) {
      isDisconnectedShown = false;
      els.disconnectedState.classList.add("hidden");
    }
  }

  function updateCards(reading, summary) {
    if (reading) {
      setCard(els.voltage, null, els.miniVoltage, reading.voltage_v, "V", fmtNum(reading.voltage_v, 3) + " V", 3);
      setCard(els.current, null, els.miniCurrent, reading.current_ma, "mA", fmtNum(reading.current_a, 4) + " A", 2);
      setCard(els.power, null, els.miniPower, reading.power_w, "W", "--", 2);

      const ts = reading.timestamp;
      pushLive(live.voltage, fmtTime(ts), reading.voltage_v);
      pushLive(live.current, fmtTime(ts), reading.current_ma);
      pushLive(live.power, fmtTime(ts), reading.power_w);
      updateLiveChart(charts.voltage, live.voltage);
      updateLiveChart(charts.current, live.current);
      updateLiveChart(charts.power, live.power);
    }

    if (summary) {
      setCard(els.energyToday, null, els.miniEnergyToday, summary.total_energy_wh, "Wh", "--", 2);
      setCard(els.energyTotal, null, els.miniEnergyTotal, summary.total_energy_wh, "Wh", summary.sample_count + " samples", 2);
    }
  }

  function renderHistoryTable(measurements) {
    const body = els.historyBody;
    body.innerHTML = "";

    if (!measurements || measurements.length === 0) {
      els.tableWrap.classList.add("hidden");
      els.emptyState.classList.remove("hidden");
      els.tableCount.textContent = "0 readings";
      return;
    }

    els.tableWrap.classList.remove("hidden");
    els.emptyState.classList.add("hidden");

    for (const m of measurements) {
      const row = document.createElement("tr");
      const ok = m.sensor_ok !== false;
      row.innerHTML = `
        <td class="mono">${fmtDate(m.timestamp)}</td>
        <td class="mono">${fmtNum(m.voltage_v, 3)}</td>
        <td class="mono">${fmtNum(m.current_ma, 2)}</td>
        <td class="mono">${fmtNum(m.power_w, 3)}</td>
        <td><span class="badge ${ok ? "status-ok" : "status-off"}">${ok ? "OK" : "ERR"}</span></td>
      `;
      body.appendChild(row);
    }
    els.tableCount.textContent = measurements.length + " readings";
  }

  async function loadHistory(start, end) {
    let url = "/api/measurements/history?limit=" + DEFAULT_TABLE_LIMIT;
    if (start) url += "&start=" + encodeURIComponent(start);
    if (end) url += "&end=" + encodeURIComponent(end);

    try {
      const data = await fetchJson(url);
      renderHistoryTable(data.measurements || []);
    } catch (err) {
      renderHistoryTable([]);
      console.warn("History load failed:", err);
    }
  }

  async function loadDailyEnergy() {
    try {
      const data = await fetchJson("/api/energy/daily");
      updateEnergyChart(data.daily || []);
    } catch (err) {
      console.warn("Daily energy load failed:", err);
      updateEnergyChart([]);
    }
  }

  // ------------------------------------------------------------------ #
  # Main poll loop
  # ------------------------------------------------------------------ #
  async function poll() {
    hideError();
    let current, health;

    try {
      // Fetch current reading and health in parallel.
      const [currentRes, healthRes] = await Promise.all([
        fetchJson("/api/measurements/current"),
        fetchJson("/api/health"),
      ]);
      current = currentRes;
      health = healthRes;
    } catch (err) {
      showError("Unable to reach the monitor API: " + err.message);
      return;
    }

    lastCurrent = current;
    updateStatusBadge(health && health.sensor ? health.sensor : {});

    // Energy summary for "today" and accumulated energy.
    let summary = null;
    try {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const end = new Date();
      end.setHours(23, 59, 59, 999);
      const sumRes = await fetchJson(
        "/api/energy/summary?start=" +
        encodeURIComponent(today.toISOString()) +
        "&end=" + encodeURIComponent(end.toISOString())
      );
      summary = sumRes;
    } catch (err) {
      console.warn("Energy summary load failed:", err);
    }

    updateCards(current, summary);

    // Refresh history + daily energy on each poll (lightweight).
    const startInput = els.filterStart.value;
    const endInput = els.filterEnd.value;
    await loadHistory(startInput || undefined, endInput || undefined);
    await loadDailyEnergy();
  }

  function startPolling() {
    if (pollingTimer) return;
    poll(); // immediate first fetch
    pollingTimer = setInterval(poll, POLL_INTERVAL_MS);
  }

  function stopPolling() {
    if (pollingTimer) {
      clearInterval(pollingTimer);
      pollingTimer = null;
    }
  }

  // ------------------------------------------------------------------ #
  # Filter controls
  // ------------------------------------------------------------------ #
  function setupFilters() {
    els.btnApplyFilters.addEventListener("click", () => {
      poll();
    });
    els.btnClearFilters.addEventListener("click", () => {
      els.filterStart.value = "";
      els.filterEnd.value = "";
      poll();
    });
    // Pressing Enter inside the inputs applies filters.
    [els.filterStart, els.filterEnd].forEach((input) => {
      input.addEventListener("change", () => poll());
    });
  }

  // ------------------------------------------------------------------ #
  # Boot
  # ------------------------------------------------------------------ #
  function boot() {
    const init = window.SOLAR_INIT || {};
    hideError();

    // Apply server-rendered initial state immediately so the page is never
    // blank on first paint.
    if (init.status) updateStatusBadge(init.status);
    if (init.current) updateCards(init.current, null);

    initCharts();
    startPolling();
    setupFilters();

    // Load daily energy once at boot.
    loadDailyEnergy();

    // Visibility API: pause polling when the tab is hidden to save CPU.
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stopPolling();
      else startPolling();
    });

    window.addEventListener("beforeunload", stopPolling);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
