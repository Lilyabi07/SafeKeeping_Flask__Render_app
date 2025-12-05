import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, send_from_directory
import psycopg2
import psycopg2.extras

# Optional Adafruit IO client
try:
    from Adafruit_IO import Client as AIOClient
    AIO_AVAILABLE = True
except Exception:
    AIO_AVAILABLE = False

# ----------------------------------------------------------------------
# FLASK APP SETUP
# ----------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(BASE_DIR, "config.json")

app = Flask(__name__, static_folder="static", template_folder="templates")

# Load config.json
CONFIG = {}
if os.path.exists(CFG_PATH):
    with open(CFG_PATH, "r") as f:
        CONFIG = json.load(f)

# ----------------------------------------------------------------------
# DATABASE (Neon)
# ----------------------------------------------------------------------
def get_pg_conn():
    """Return NEW Neon connection."""
    return psycopg2.connect(
        os.getenv("NEON_DB_URL"),
        cursor_factory=psycopg2.extras.RealDictCursor
    )

# ----------------------------------------------------------------------
# OPTIONAL ADAFRUIT IO
# ----------------------------------------------------------------------
aio = None
if AIO_AVAILABLE and CONFIG.get("ADAFRUIT_IO_USERNAME") and CONFIG.get("ADAFRUIT_IO_KEY"):
    try:
        aio = AIOClient(CONFIG["ADAFRUIT_IO_USERNAME"], CONFIG["ADAFRUIT_IO_KEY"])
    except Exception:
        aio = None

# ----------------------------------------------------------------------
# ROUTES
# ----------------------------------------------------------------------
@app.route("/")
def home():
    live = {}

    if aio:
        feeds = {
            "temperature": "temperature",
            "humidity": "humidity",
            "motion": "motion_feed",
            "pressure": "pressure"
        }
        for key, feed_name in feeds.items():
            try:
                v = aio.receive(feed_name).value
                live[key] = float(v) if key != "motion" else int(v)
            except:
                pass

    public_drive = CONFIG.get("PUBLIC_DRIVE_FOLDER_LINK", "")
    return render_template("home.html", live=live, public_drive=public_drive)


@app.route("/environmental")
def environmental():
    return render_template("environmental.html")


@app.route("/device-control")
def device_control():
    actuators = CONFIG.get("ACTUATORS", {"LEDs":0, "Buzzer":0, "Servo":0, "Camera":0})
    return render_template("device_control.html", actuators=actuators)


@app.route("/manage-security")
def manage_security():
    return render_template("manage_security.html")


@app.route("/about")
def about():
    return render_template("about.html")

# ----------------------------------------------------------------------
# STATIC IMAGES
# ----------------------------------------------------------------------
IMAGES_DIR = os.path.join(BASE_DIR, "..", "images")
if not os.path.exists(IMAGES_DIR):
    IMAGES_DIR = os.path.join(BASE_DIR, "static", "images")

@app.route("/images/<path:filename>")
def images(filename):
    return send_from_directory(IMAGES_DIR, filename)

# ----------------------------------------------------------------------
# SENSOR INGEST
# ----------------------------------------------------------------------
@app.route("/api/sensor", methods=["POST"])
def ingest_sensor():
    data = request.json
    sensor_type = data.get("sensor_type")
    value = data.get("value")
    source = data.get("source", "pi-001")

    if not sensor_type or value is None:
        return jsonify({"error": "Missing fields"}), 400

    try:
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO sensor_readings (timestamp, sensor_type, value, source)
                    VALUES (NOW(), %s, %s, %s)
                """, (sensor_type, value, source))

    except Exception as e:
        print("Neon ingestion error:", e)
        return jsonify({"status": "db_error"}), 500

    return jsonify({"status": "ok"})

# ----------------------------------------------------------------------
# LIVE SENSORS
# ----------------------------------------------------------------------
@app.route("/api/live-sensors")
def api_live_sensors():
    result = {}

    if aio:
        feeds = ["temperature", "humidity", "motion_feed", "pressure"]
        for feed in feeds:
            try:
                v = aio.receive(feed).value
                key = "motion" if "motion" in feed else feed
                result[key] = float(v) if key != "motion" else int(v)
            except:
                pass

    try:
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT sensor_type, value
                    FROM sensor_readings
                    WHERE timestamp > now() - interval '1 hour'
                    ORDER BY timestamp DESC
                    LIMIT 30
                """)
                rows = cur.fetchall()

        for r in rows:
            st = r["sensor_type"]
            v = float(r["value"])

            if "temp" in st and "temperature" not in result:
                result["temperature"] = v
            if "humid" in st and "humidity" not in result:
                result["humidity"] = v
            if "pressure" in st and "pressure" not in result:
                result["pressure"] = v

    except:
        pass

    return jsonify(result)

# ----------------------------------------------------------------------
# HISTORICAL DATA
# ----------------------------------------------------------------------
@app.route("/api/temperature-history")
def api_temp_history():
    start = request.args.get("start")
    end = request.args.get("end")

    if not start or not end:
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=1)
    else:
        start_dt = datetime.fromisoformat(start + "T00:00:00")
        end_dt = datetime.fromisoformat(end + "T23:59:59")

    timeline = {}

    try:
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT timestamp, sensor_type, value
                    FROM sensor_readings
                    WHERE timestamp BETWEEN %s AND %s
                    AND sensor_type IN ('temperature','humidity','pressure')
                    ORDER BY timestamp ASC
                """, (start_dt, end_dt))

                rows = cur.fetchall()

        for r in rows:
            ts = r["timestamp"].replace(microsecond=0)
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")

            if ts_str not in timeline:
                timeline[ts_str] = {
                    "temperature": None,
                    "humidity": None,
                    "pressure": None
                }

            val = float(r["value"])
            st = r["sensor_type"]

            timeline[ts_str][st] = val

    except Exception as e:
        print("History query error:", e)

    # Ensure strict timeline order
    ordered = sorted(timeline.keys())

    labels = ordered
    temperature = [timeline[t]["temperature"] for t in ordered]
    humidity = [timeline[t]["humidity"] for t in ordered]
    pressure = [timeline[t]["pressure"] for t in ordered]

    return jsonify({
        "labels": labels,
        "temperature": temperature,
        "humidity": humidity,
        "pressure": pressure
    })

# ----------------------------------------------------------------------
# DEVICE CONTROL
# ----------------------------------------------------------------------
@app.route("/api/device/<device_name>/set", methods=["POST"])
def api_device_set(device_name):
    payload = request.get_json() or {}
    state = int(bool(payload.get("state", 0)))

    feed_name = f"{device_name.lower().replace(' ', '_')}_control"
    sent = False

    if aio:
        try:
            aio.send(feed_name, state)
            sent = True
        except Exception as e:
            print("Adafruit IO error:", e)

    return jsonify({"device": device_name, "state": state, "sent_to_aio": sent})

# ----------------------------------------------------------------------
# SECURITY EVENTS
# ----------------------------------------------------------------------
@app.route("/api/security/list")
def api_security_list():
    date = request.args.get("date")
    if not date:
        return jsonify({"error": "date required"}), 400

    start_ts = f"{date}T00:00:00"
    end_ts = f"{date}T23:59:59"

    out = []

    try:
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, timestamp, event_type, image_url, processed
                    FROM intrusion_events
                    WHERE timestamp BETWEEN %s AND %s
                    ORDER BY timestamp DESC
                """, (start_ts, end_ts))

                rows = cur.fetchall()

        for r in rows:
            out.append({
                "id": r["id"],
                "timestamp": r["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                "event_type": r["event_type"],
                "image_url": r["image_url"],
                "processed": r["processed"]
            })

    except Exception as e:
        print("Security query error:", e)

    return jsonify(out)

# ----------------------------------------------------------------------
# DEVELOPMENT MODE
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
