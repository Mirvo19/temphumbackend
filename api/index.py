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
    """Interactive documentation and web interface"""
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Temp & Humidity IoT API</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg: #090d16;
                --card-bg: #121827;
                --border: #1e293b;
                --primary: #38bdf8;
                --primary-glow: rgba(56, 189, 248, 0.15);
                --accent: #f43f5e;
                --text: #f8fafc;
                --text-muted: #94a3b8;
                --code-bg: #030712;
            }
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: 'Inter', sans-serif;
                background-color: var(--bg);
                color: var(--text);
                line-height: 1.6;
                padding: 2rem 1rem;
            }
            .container { max-width: 900px; margin: 0 auto; }
            header {
                text-align: center;
                margin-bottom: 3rem;
                padding-bottom: 2rem;
                border-bottom: 1px solid var(--border);
            }
            h1 {
                font-size: 2.5rem;
                font-weight: 700;
                background: linear-gradient(135deg, #38bdf8, #818cf8);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 0.5rem;
            }
            .badge {
                display: inline-block;
                padding: 0.25rem 0.75rem;
                background: var(--primary-glow);
                color: var(--primary);
                border: 1px solid var(--primary);
                border-radius: 9999px;
                font-size: 0.85rem;
                font-weight: 600;
            }
            .card {
                background: var(--card-bg);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 1.5rem;
                margin-bottom: 2rem;
                box-shadow: 0 10px 25px -5px rgba(0,0,0,0.3);
            }
            h2 { font-size: 1.4rem; color: var(--primary); margin-bottom: 1rem; }
            .endpoint {
                display: flex;
                align-items: center;
                gap: 0.75rem;
                margin-bottom: 1rem;
                font-family: monospace;
            }
            .method {
                padding: 0.25rem 0.5rem;
                border-radius: 6px;
                font-weight: bold;
                font-size: 0.85rem;
            }
            .method.post { background: #059669; color: white; }
            .method.get { background: #0284c7; color: white; }
            .method.delete { background: #e11d48; color: white; }
            pre {
                background: var(--code-bg);
                padding: 1rem;
                border-radius: 8px;
                border: 1px solid var(--border);
                overflow-x: auto;
                font-size: 0.9rem;
                color: #e2e8f0;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 1rem;
            }
            th, td {
                padding: 0.75rem;
                text-align: left;
                border-bottom: 1px solid var(--border);
            }
            th { color: var(--text-muted); font-size: 0.85rem; text-transform: uppercase; }
            .live-pulse {
                width: 8px;
                height: 8px;
                background-color: #22c55e;
                border-radius: 50%;
                display: inline-block;
                box-shadow: 0 0 8px #22c55e;
                margin-right: 6px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1><span class="live-pulse"></span>Temp & Humidity API</h1>
                <p style="color: var(--text-muted);">Flask REST Backend deployed on Vercel (CORS Enabled)</p>
                <div style="margin-top: 1rem;">
                    <span class="badge">Status: Active</span>
                    <span class="badge" style="border-color: #818cf8; color: #818cf8; background: rgba(129, 140, 248, 0.15);">CORS: Allowed (*)</span>
                </div>
            </header>

            <div class="card">
                <h2>📥 1. Store Temperature & Humidity Data</h2>
                <div class="endpoint">
                    <span class="method post">POST</span>
                    <span>/api/data</span> (or /api/store)
                </div>
                <p style="color: var(--text-muted); font-size: 0.95rem; margin-bottom: 1rem;">
                    Send readings from your IoT device (ESP32, ESP8266, Raspberry Pi) or client application. Accepts JSON, Form Data, or Query Parameters.
                </p>
                <p style="font-weight: 600; margin-bottom: 0.5rem; font-size: 0.9rem;">JSON Request Body Example:</p>
                <pre><code>{
  "devid": "device_01",
  "temp": 24.5,
  "humidity": 60.2
}</code></pre>
                <p style="font-weight: 600; margin-top: 1rem; margin-bottom: 0.5rem; font-size: 0.9rem;">cURL Example:</p>
                <pre><code>curl -X POST "{{ request.host_url }}api/data" \
  -H "Content-Type: application/json" \
  -d '{"devid": "device_01", "temp": 24.5, "humidity": 60.2}'</code></pre>
            </div>

            <div class="card">
                <h2>📤 2. Read Data by Device ID</h2>
                <div class="endpoint">
                    <span class="method get">GET</span>
                    <span>/api/data/&lt;devid&gt;</span> or <span>/api/data?devid=&lt;devid&gt;</span>
                </div>
                <p style="color: var(--text-muted); font-size: 0.95rem; margin-bottom: 1rem;">
                    Fetch humidity and temperature readings for a specific <code>devid</code>. Supports optional query parameters: <code>limit=50</code> and <code>latest=true</code>.
                </p>
                <p style="font-weight: 600; margin-bottom: 0.5rem; font-size: 0.9rem;">cURL Examples:</p>
                <pre><code># Fetch all readings for device_01
curl "{{ request.host_url }}api/data/device_01"

# Fetch latest reading only
curl "{{ request.host_url }}api/data/device_01?latest=true"</code></pre>
            </div>

            <div class="card">
                <h2>📊 3. List Registered Devices</h2>
                <div class="endpoint">
                    <span class="method get">GET</span>
                    <span>/api/devices</span>
                </div>
                <p style="color: var(--text-muted); font-size: 0.95rem;">
                    Returns a list of all active device IDs with their latest reading.
                </p>
            </div>
        </div>
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
