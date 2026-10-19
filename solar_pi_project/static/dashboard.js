// Solar Panel Dashboard - JavaScript
// Handles real-time updates, chart initialization, and user interactions

/* Global state */
let charts = {}; // Chart.js instances for each graph
let lastUpdate = 0;
const UPDATE_INTERVAL = 1000; // ms (matching 1s sensor sampling)

/* Initialize page on load */
document.addEventListener('DOMContentLoaded', function() {
    initCharts();
    fetchInitialData();
    startPeriodicUpdates();
});

// Chart initialization
function initCharts() {
    const ctxColors = {
        voltage: { background: 'rgba(231, 76, 60, 0.1)', border: 'var(--color-volt)' },
        current: { background: 'rgba(52, 152, 219, 0.1)', border: 'var(--color-amp)' },
        power: { background: 'rgba(46, 204, 113, 0.1)', border: 'var(--color-watt)' }
    };

    // Voltage chart
    charts.voltage = new Chart(
        document.getElementById('voltageChart'),
        {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Voltage (V)',
                    data: [],
                    borderColor: ctxColors.voltage.border,
                    backgroundColor: ctxColors.voltage.background,
                    tension: 0.2,
                    fill: true,
                    pointRadius: 0,
                    pointHoverRadius: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 0
                },
                scales: {
                    y: {
                        beginAtTrue: true,
                        grid: { color: 'var(--color-border)' },
                        ticks: { color: var(--color-text) }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: var(--color-text) }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: var(--color-card),
                        titleColor: var(--color-text),
                        bodyColor: var(--color-volt)
                    }
                }
            }
        }
    );

    // Current chart
    charts.current = new Chart(
        document.getElementById('currentChart'),
        {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Current (mA)',
                    data: [],
                    borderColor: ctxColors.current.border,
                    backgroundColor: ctxColors.current.background,
                    tension: 0.2,
                    fill: true,
                    pointRadius: 0,
                    pointHoverRadius: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 0
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'var(--color-border)' },
                        ticks: { color: var(--color-text) }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: var(--color-text) }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: var(--color-card),
                        titleColor: var(--color-text),
                        bodyColor: var.current.border
                    }
                }
            }
        }
    );

    // Power chart
    charts.power = new Chart(
        document.getElementById('powerChart'),
        {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Power (W)',
                    data: [],
                    borderColor: ctxColors.power.border,
                    backgroundColor: ctxColors.power.background,
                    tension: 0.2,
                    fill: true,
                    pointRadius: 0,
                    pointHoverRadius: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 0
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'var(--color-border)' },
                        ticks: { color: var(--color-text) }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: var(--color-text) }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: var(--color-card),
                        titleColor: var(--color-text),
                        bodyColor: var(--color-watt)
                    }
                }
            }
        }
    );
}

// Fetch initial data from API
function fetchInitialData() {
    // Get current readings
    fetch('/api/readings')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateDisplay(data);
            }
        })
        .catch(error => {
            console.error('Error fetching initial readings:', error);
        });

    // Get historical data for the day
    const today = new Date().toISOString().split('T')[0];
    fetch(`/api/history?date=${today}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.entries.length > 0) {
                updateHistoryList(data.entries);
            }
        })
        .catch(error => {
            console.error('Error fetching history:', error);
        });
}

// Update display with current reading data
function updateDisplay(data) {
    // Update summary values
    const voltageEl = document.getElementById('voltageValue');
    const currentEl = document.getElementById('currentValue');
    const powerEl = document.getElementById('powerValue');
    const energyTodayEl = document.getElementById('energyToday');
    const totalTodayEl = document.getElementById('totalToday');
    const totalAccumulatedEl = document.getElementById('totalAccumulated');
    const totalAvgPowerEl = document.getElementById('totalAvgPower');
    const sensorStatus = document.getElementById('sensorStatus');

    // Voltage
    voltageEl.textContent = data.voltage_V !== undefined 
        ? `${parseFloat(data.voltage_V).toFixed(2)} V` 
        : '— V';

    // Current
    currentEl.textContent = data.current_mA !== undefined
        ? `${parseFloat(data.current_mA).toFixed(1)} mA`
        : '— mA';

    // Power
    powerEl.textContent = data.power_W !== undefined
        ? `${parseFloat(data.power_W).toFixed(3)} W`
        : '— W';

    // Energy today from API response if available
    if (data.daily_Wh !== undefined) {
        energyTodayEl.textContent = `${parseFloat(data.daily_Wh).toFixed(2)} Wh`;
    }

    // Sensor status indicator
    if (data.sensor_status === 'ok') {
        sensorStatus.classList.add('connected');
        sensorStatus.querySelector('span:last-child').textContent = 'Connected';
        sensorStatus.querySelector('.dot').style.background = '#2ecc71';
    } else if (data.sensor_status !== 'unknown') {
        sensorStatus.classList.remove('connected');
        sensorStatus.querySelector('span:last-child').textContent = 'Error';
        sensorStatus.querySelector('.dot').style.background = '#e74c3c';
    }

    // Update charts
    updateCharts(data);
}

// Update historical graphs
function updateCharts(data) {
    const now = new Date().toLocaleTimeString();

    // Add data points to each chart
    if (data.history_timestamps && data.history_voltages) {
        // Voltage chart
        charts.voltage.data.labels.push(now);
        charts.voltage.data.datasets[0].data.push(parseFloat(data.history_voltages[data.history_voltages.length - 1]) || 0);
        // Keep only last 50 points
        if (charts.voltage.data.labels.length > 50) {
            charts.voltage.data.labels.shift();
            charts.voltage.data.datasets[0].data.shift();
        }
        charts.voltage.update('none');
    }

    if (data.history_currents) {
        // Current chart
        charts.current.data.labels.push(now);
        charts.current.data.datasets[0].data.push(parseFloat(data.history_currents[data.history_currents.length - 1]) || 0);
        if (charts.current.data.labels.length > 50) {
            charts.current.data.labels.shift();
            charts.current.data.datasets[0].data.shift();
        }
        charts.current.update('none');
    }

    if (data.history_powers) {
        // Power chart
        charts.power.data.labels.push(now);
        charts.power.data.datasets[0].data.push(parseFloat(data.history_powers[data.history_powers.length - 1]) || 0);
        if (charts.power.data.labels.length > 50) {
            charts.power.data.labels.shift();
            charts.power.data.datasets[0].data.shift();
        }
        charts.power.update('none');
    }
}

// Update the history reading list
function updateHistoryList(entries) {
    const historyList = document.getElementById('historyList');
    if (!historyList) return;

    if (entries.length === 0) {
        historyList.innerHTML = '<p class="small-link" style="color: #6c757d;">No readings for today yet</p>';
        return;
    }

    let html = '';
    // Show last 10 entries
    const recent = entries.slice(-10);

    recent.forEach(entry => {
        const dt = new Date(entry.timestamp);
        const timeStr = dt.toLocaleTimeString();
        const v = entry.voltage_V !== undefined ? `${parseFloat(entry.voltage_V).toFixed(2)}V` : '—';
        const i = entry.current_mA !== undefined ? `${parseFloat(entry.current_mA).toFixed(1)}mA` : '—';
        const p = entry.power_W !== undefined ? `${parseFloat(entry.power_W).toFixed(3)}W` : '—';

        html += `
            <div class="history-item">
                <span class="time">${timeStr}</span>
                <div class="values">
                    <span class="value">${v}</span>
                    <span class="value">${i}</span>
                    <span class="value">${p}</span>
                </div>
            </div>
        `;
    });

    historyList.innerHTML = html;
}

// Start periodic updates
function startPeriodicUpdates() {
    // Initial fetch already done
    // Set up recurring update
    window.setInterval(function() {
        fetch('/api/readings')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateDisplay(data);
                }
            })
            .catch(error => {
                console.error('Error in periodic update:', error);
            });
    }, UPDATE_INTERVAL);
}

// CSV export handler
function exportCsv(dateStr) {
    const today = new Date().toISOString().split('T')[0];
    const dateToUse = dateStr || today;
    
    window.location.href = `/api/csv_export?date=${dateToUse}`;
}

// Date selector change handler
function initDateSelector() {
    const todayInput = document.getElementById('todayDate');
    if (todayInput) {
        const today = new Date().toISOString().split('T')[0];
        todayInput.value = today;
        
        todayInput.addEventListener('change', function() {
            const selectedDate = this.value;
            fetch(`/api/readings?date=${selectedDate}`)  // This won't work as-is, just for illustration
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updateDisplay(data);
                    }
                });
        });
    }
}
</script>