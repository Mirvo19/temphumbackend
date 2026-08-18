import os
import sqlite3
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS

app = Flask(__name__)

# Enable CORS for all routes and origins
CORS(app, resources={r"/*": {"origins": "*"}})

# Add CORS headers after each request to guarantee cross-origin access
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response

# Database configuration (uses /tmp on Vercel or serverless environments)
def get_db_path():
    env_path = os.environ.get("DATABASE_PATH")
    if env_path:
        return env_path
    
    # On Vercel, writeable storage is restricted to /tmp
    is_vercel = os.environ.get("VERCEL") == "1" or os.environ.get("VERCEL_ENV") is not None
    if is_vercel:
        return "/tmp/temphum.db"
    
    # Local fallback
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "..", "temphum.db")

def get_db_connection():
    db_path = get_db_path()
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            devid TEXT NOT NULL,
            temp REAL NOT NULL,
            humidity REAL NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_devid ON readings(devid)")
    conn.commit()
    conn.close()

# Ensure table exists upon initialization
try:
    init_db()
except Exception as e:
    print(f"Database init warning: {e}")


def extract_param(param_names, default=None):
    """Utility to extract parameter from JSON body, Form data, or Query params"""
    req_json = request.get_json(silent=True) or {}
    for name in param_names:
        if name in req_json and req_json[name] is not None:
            return req_json[name]
        if name in request.form and request.form[name] != "":
            return request.form[name]
        if name in request.args and request.args[name] != "":
            return request.args[name]
    return default


@app.route("/", methods=["GET"])
def home():
    """Interactive device telemetry dashboard and documentation"""
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>IoT Telemetry Dashboard</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg: #09090b;
                --surface: #121215;
                --surface-hover: #1c1c21;
                --border: #27272a;
                --border-light: #3f3f46;
                --text-primary: #f4f4f5;
                --text-secondary: #a1a1aa;
                --text-tertiary: #71717a;
                --accent: #e4e4e7;
                --status-green: #10b981;
                --status-green-bg: rgba(16, 185, 129, 0.1);
            }
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                background-color: var(--bg);
                color: var(--text-primary);
                line-height: 1.5;
                padding: 2.5rem 1.5rem;
                min-height: 100vh;
            }
            .container { max-width: 1080px; margin: 0 auto; }
            
            header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 2.5rem;
                padding-bottom: 1.5rem;
                border-bottom: 1px solid var(--border);
            }
            .brand h1 {
                font-size: 1.4rem;
                font-weight: 600;
                letter-spacing: -0.02em;
                color: var(--text-primary);
                display: flex;
                align-items: center;
                gap: 0.6rem;
            }
            .brand p {
                font-size: 0.875rem;
                color: var(--text-secondary);
                margin-top: 0.25rem;
            }
            .status-badge {
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.35rem 0.75rem;
                background: var(--status-green-bg);
                border: 1px solid rgba(16, 185, 129, 0.2);
                border-radius: 9999px;
                font-size: 0.8rem;
                font-weight: 500;
                color: var(--status-green);
            }
            .status-dot {
                width: 6px;
                height: 6px;
                background-color: var(--status-green);
                border-radius: 50%;
            }

            .section-title {
                font-size: 0.95rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                color: var(--text-tertiary);
                margin-bottom: 1rem;
            }

            /* Devices Grid */
            .devices-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                gap: 1rem;
                margin-bottom: 2.5rem;
            }
            .device-card {
                background: var(--surface);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 1.25rem;
                cursor: pointer;
                transition: all 0.15s ease;
            }
            .device-card:hover {
                background: var(--surface-hover);
                border-color: var(--border-light);
            }
            .device-card.active {
                border-color: var(--text-primary);
                background: var(--surface-hover);
            }
            .device-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1rem;
            }
            .device-id {
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.95rem;
                font-weight: 600;
                color: var(--text-primary);
            }
            .device-metrics {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 0.75rem;
            }
            .metric-label {
                font-size: 0.75rem;
                color: var(--text-secondary);
                text-transform: uppercase;
                letter-spacing: 0.03em;
            }
            .metric-val {
                font-size: 1.35rem;
                font-weight: 600;
                color: var(--text-primary);
                font-family: 'JetBrains Mono', monospace;
                margin-top: 0.1rem;
            }
            .metric-val span {
                font-size: 0.85rem;
                color: var(--text-tertiary);
                font-weight: 400;
            }
            .device-updated {
                font-size: 0.75rem;
                color: var(--text-tertiary);
                margin-top: 1rem;
                padding-top: 0.75rem;
                border-top: 1px solid rgba(255,255,255,0.05);
            }

            /* Main Layout */
            .panel {
                background: var(--surface);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 1.5rem;
                margin-bottom: 2.5rem;
            }
            .panel-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1.25rem;
                padding-bottom: 1rem;
                border-bottom: 1px solid var(--border);
            }
            .panel-title {
                font-size: 1.1rem;
                font-weight: 600;
                color: var(--text-primary);
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }
            .selected-device-pill {
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.85rem;
                padding: 0.2rem 0.6rem;
                background: var(--bg);
                border: 1px solid var(--border);
                border-radius: 4px;
                color: var(--text-secondary);
            }

            /* Table Styling */
            .table-container {
                overflow-x: auto;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                text-align: left;
                font-size: 0.9rem;
            }
            th {
                padding: 0.75rem 1rem;
                font-size: 0.75rem;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                color: var(--text-tertiary);
                border-bottom: 1px solid var(--border);
                font-weight: 600;
            }
            td {
                padding: 0.85rem 1rem;
                border-bottom: 1px solid var(--border);
                color: var(--text-secondary);
            }
            tr:last-child td { border-bottom: none; }
            tr:hover td { color: var(--text-primary); background: rgba(255,255,255,0.01); }
            .mono { font-family: 'JetBrains Mono', monospace; }

            /* Test Data Ingestion Box */
            .quick-test-grid {
                display: grid;
                grid-template-columns: 2fr 1fr 1fr auto;
                gap: 0.75rem;
                align-items: end;
            }
            .form-group label {
                display: block;
                font-size: 0.75rem;
                color: var(--text-secondary);
                margin-bottom: 0.4rem;
                text-transform: uppercase;
                letter-spacing: 0.03em;
            }
            .form-group input {
                width: 100%;
                background: var(--bg);
                border: 1px solid var(--border);
                border-radius: 6px;
                padding: 0.6rem 0.8rem;
                color: var(--text-primary);
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.9rem;
            }
            .form-group input:focus {
                outline: none;
                border-color: var(--text-primary);
            }
            .btn {
                background: var(--text-primary);
                color: var(--bg);
                border: none;
                border-radius: 6px;
                padding: 0.65rem 1.2rem;
                font-size: 0.875rem;
                font-weight: 600;
                cursor: pointer;
                transition: opacity 0.15s ease;
                height: 38px;
            }
            .btn:hover { opacity: 0.9; }

            /* Code Docs */
            pre {
                background: var(--bg);
                padding: 1rem;
                border-radius: 6px;
                border: 1px solid var(--border);
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.85rem;
                color: var(--text-secondary);
                overflow-x: auto;
                margin-top: 0.75rem;
            }

            .empty-state {
                text-align: center;
                padding: 3rem 1rem;
                color: var(--text-tertiary);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div class="brand">
                    <h1><span class="status-dot"></span> IoT Telemetry Console</h1>
                    <p>Python Flask Backend deployed on Vercel</p>
                </div>
                <div class="status-badge">
                    <span class="status-dot"></span> System Online
                </div>
            </header>

            <div class="section-title">Registered Devices</div>
            <div class="devices-grid" id="devicesContainer">
                <div class="empty-state" style="grid-column: 1/-1;">Loading device registry...</div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">
                        Telemetry Readings
                        <span class="selected-device-pill" id="selectedDevicePill">Select a Device</span>
                    </div>
                </div>

                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Device ID</th>
                                <th>Temperature (°C)</th>
                                <th>Humidity (%)</th>
                                <th>Timestamp (UTC)</th>
                            </tr>
                        </thead>
                        <tbody id="readingsTableBody">
                            <tr>
                                <td colspan="5" class="empty-state">Select a device above to view telemetry log.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">Simulate Ingestion</div>
                </div>
                <form id="testIngestForm" class="quick-test-grid">
                    <div class="form-group">
                        <label>Device ID</label>
                        <input type="text" id="inputDevId" value="esp32_room_01" required>
                    </div>
                    <div class="form-group">
                        <label>Temp (°C)</label>
                        <input type="number" step="0.1" id="inputTemp" value="24.5" required>
                    </div>
                    <div class="form-group">
                        <label>Humidity (%)</label>
                        <input type="number" step="0.1" id="inputHumidity" value="58.2" required>
                    </div>
                    <button type="submit" class="btn">Send Data</button>
                </form>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">API Quick Reference</div>
                </div>
                <p style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 0.5rem;">Read Endpoint (GET):</p>
                <pre>curl "{{ request.host_url }}api/data/esp32_room_01?latest=true"</pre>

                <p style="font-size: 0.875rem; color: var(--text-secondary); margin-top: 1rem; margin-bottom: 0.5rem;">Store Endpoint (POST):</p>
                <pre>curl -X POST "{{ request.host_url }}api/data" \
  -H "Content-Type: application/json" \
  -d '{"devid": "esp32_room_01", "temp": 24.5, "humidity": 58.2}'</pre>
            </div>
        </div>

        <script>
            let currentSelectedDevice = null;

            async function loadDevices() {
                try {
                    const res = await fetch('/api/devices');
                    const data = await res.json();
                    const container = document.getElementById('devicesContainer');
                    
                    if (!data.devices || data.devices.length === 0) {
                        container.innerHTML = '<div class="empty-state" style="grid-column: 1/-1;">No active devices detected yet. Send data to create one.</div>';
                        return;
                    }

                    container.innerHTML = data.devices.map(dev => `
                        <div class="device-card ${currentSelectedDevice === dev.devid ? 'active' : ''}" onclick="selectDevice('${dev.devid}')">
                            <div class="device-header">
                                <div class="device-id">${dev.devid}</div>
                            </div>
                            <div class="device-metrics">
                                <div>
                                    <div class="metric-label">Temp</div>
                                    <div class="metric-val">${dev.latest_temp.toFixed(1)}<span>°C</span></div>
                                </div>
                                <div>
                                    <div class="metric-label">Humidity</div>
                                    <div class="metric-val">${dev.latest_humidity.toFixed(1)}<span>%</span></div>
                                </div>
                            </div>
                            <div class="device-updated">Last update: ${new Date(dev.last_updated).toLocaleString()}</div>
                        </div>
                    `).join('');

                    if (!currentSelectedDevice && data.devices.length > 0) {
                        selectDevice(data.devices[0].devid);
                    }
                } catch (err) {
                    console.error('Failed to load devices:', err);
                }
            }

            async function selectDevice(devid) {
                currentSelectedDevice = devid;
                document.getElementById('selectedDevicePill').innerText = devid;
                
                // Highlight active device card
                document.querySelectorAll('.device-card').forEach(card => {
                    if (card.querySelector('.device-id').innerText === devid) {
                        card.classList.add('active');
                    } else {
                        card.classList.remove('active');
                    }
                });

                try {
                    const res = await fetch(`/api/data/${devid}`);
                    const data = await res.json();
                    const tbody = document.getElementById('readingsTableBody');

                    if (!data.data || data.data.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No readings found for this device.</td></tr>';
                        return;
                    }

                    tbody.innerHTML = data.data.map(row => `
                        <tr>
                            <td class="mono" style="color: var(--text-tertiary);">${row.id}</td>
                            <td class="mono" style="color: var(--text-primary); font-weight: 500;">${row.devid}</td>
                            <td class="mono" style="color: var(--text-primary);">${row.temp.toFixed(2)} °C</td>
                            <td class="mono" style="color: var(--text-primary);">${row.humidity.toFixed(2)} %</td>
                            <td class="mono" style="font-size: 0.8rem;">${new Date(row.timestamp).toLocaleString()}</td>
                        </tr>
                    `).join('');
                } catch (err) {
                    console.error('Failed to load telemetry:', err);
                }
            }

            document.getElementById('testIngestForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const devid = document.getElementById('inputDevId').value;
                const temp = parseFloat(document.getElementById('inputTemp').value);
                const humidity = parseFloat(document.getElementById('inputHumidity').value);

                try {
                    const res = await fetch('/api/data', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ devid, temp, humidity })
                    });
                    if (res.ok) {
                        await loadDevices();
                        selectDevice(devid);
                    }
                } catch (err) {
                    alert('Error sending data: ' + err.message);
                }
            });

            // Initial load & poll every 5 seconds
            loadDevices();
            setInterval(loadDevices, 5000);
        </script>
    </body>
    </html>
    """
    return render_template_string(html_template)


@app.route("/api/data", methods=["POST", "GET", "OPTIONS"])
@app.route("/api/store", methods=["POST", "GET", "OPTIONS"])
@app.route("/store", methods=["POST", "GET", "OPTIONS"])
def handle_data_generic():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    if request.method == "POST":
        return store_data()
    
    # GET /api/data?devid=xyz or GET /api/data (list all)
    devid = extract_param(["devid", "device_id", "id"])
    if devid:
        return get_device_data(devid)
    else:
        return list_devices()


@app.route("/api/data/<devid>", methods=["GET", "DELETE", "OPTIONS"])
@app.route("/api/read/<devid>", methods=["GET", "OPTIONS"])
def handle_device_by_id(devid):
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    if request.method == "DELETE":
        return delete_device_data(devid)

    return get_device_data(devid)


def store_data():
    """Ingest temperature and humidity data"""
    devid = extract_param(["devid", "device_id", "id"])
    temp = extract_param(["temp", "temperature", "t"])
    humidity = extract_param(["humidity", "hum", "h"])

    missing = []
    if devid is None: missing.append("devid")
    if temp is None: missing.append("temp")
    if humidity is None: missing.append("humidity (or hum)")

    if missing:
        return jsonify({
            "status": "error",
            "message": f"Missing required parameters: {', '.join(missing)}",
            "required": ["devid", "temp", "humidity"]
        }), 400

    try:
        devid = str(devid).strip()
        temp_val = float(temp)
        hum_val = float(humidity)
    except (ValueError, TypeError):
        return jsonify({
            "status": "error",
            "message": "Invalid numeric values for temperature or humidity."
        }), 400

    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        init_db()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO readings (devid, temp, humidity, timestamp) VALUES (?, ?, ?, ?)",
            (devid, temp_val, hum_val, timestamp)
        )
        conn.commit()
        record_id = cursor.lastrowid
        conn.close()

        return jsonify({
            "status": "success",
            "message": "Data stored successfully",
            "data": {
                "id": record_id,
                "devid": devid,
                "temp": temp_val,
                "humidity": hum_val,
                "timestamp": timestamp
            }
        }), 201
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Database storage failed: {str(e)}"
        }), 500


def get_device_data(devid):
    """Retrieve temperature and humidity data for a device ID"""
    if not devid:
        return jsonify({"status": "error", "message": "Device ID is required."}), 400

    is_latest = request.args.get("latest", "false").lower() in ["true", "1", "yes"]
    
    try:
        limit = int(request.args.get("limit", 100))
        limit = max(1, min(limit, 1000))
    except ValueError:
        limit = 100

    try:
        init_db()
        conn = get_db_connection()
        cursor = conn.cursor()

        if is_latest:
            cursor.execute(
                "SELECT id, devid, temp, humidity, timestamp FROM readings WHERE devid = ? ORDER BY id DESC LIMIT 1",
                (devid,)
            )
            row = cursor.fetchone()
            conn.close()

            if not row:
                return jsonify({
                    "status": "error",
                    "message": f"No data found for device ID '{devid}'",
                    "devid": devid
                }), 4404 if False else 404

            return jsonify({
                "status": "success",
                "devid": devid,
                "data": {
                    "id": row["id"],
                    "devid": row["devid"],
                    "temp": row["temp"],
                    "humidity": row["humidity"],
                    "timestamp": row["timestamp"]
                }
            }), 200
        else:
            cursor.execute(
                "SELECT id, devid, temp, humidity, timestamp FROM readings WHERE devid = ? ORDER BY id DESC LIMIT ?",
                (devid, limit)
            )
            rows = cursor.fetchall()
            conn.close()

            data_list = [
                {
                    "id": r["id"],
                    "devid": r["devid"],
                    "temp": r["temp"],
                    "humidity": r["humidity"],
                    "timestamp": r["timestamp"]
                } for r in rows
            ]

            return jsonify({
                "status": "success",
                "devid": devid,
                "count": len(data_list),
                "data": data_list
            }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Database query failed: {str(e)}"
        }), 500


@app.route("/api/devices", methods=["GET", "OPTIONS"])
def list_devices():
    """List all unique device IDs and their latest readings"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    try:
        init_db()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r1.devid, r1.temp, r1.humidity, r1.timestamp
            FROM readings r1
            INNER JOIN (
                SELECT devid, MAX(id) as max_id
                FROM readings
                GROUP BY devid
            ) r2 ON r1.id = r2.max_id
            ORDER BY r1.timestamp DESC
        """)
        rows = cursor.fetchall()
        conn.close()

        devices = [
            {
                "devid": r["devid"],
                "latest_temp": r["temp"],
                "latest_humidity": r["humidity"],
                "last_updated": r["timestamp"]
            } for r in rows
        ]

        return jsonify({
            "status": "success",
            "count": len(devices),
            "devices": devices
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


def delete_device_data(devid):
    """Clear readings for a specific device"""
    try:
        init_db()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM readings WHERE devid = ?", (devid,))
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f"Deleted {deleted_count} records for device '{devid}'"
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# Fallback entrypoint for running directly with python api/index.py or gunicorn
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Temp & Humidity Flask API on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=True)
