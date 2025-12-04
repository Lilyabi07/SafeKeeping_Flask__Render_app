# app.py
import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, send_from_directory, url_for



# optional Adafruit IO client
try:
    from Adafruit_IO import Client as AIOClient
    AIO_AVAILABLE = True
except Exception:
    AIO_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# load local config
CFG_PATH = os.path.join(BASE_DIR, "config.json")
CONFIG = {}
if os.path.exists(CFG_PATH):
    with open(CFG_PATH, "r") as f:
        CONFIG = json.load(f)

app = Flask(__name__, static_folder="static", template_folder="templates")

# Adafruit IO client (server-side reads)
aio = None
if AIO_AVAILABLE and CONFIG.get("ADAFRUIT_IO_USERNAME") and CONFIG.get("ADAFRUIT_IO_KEY"):
    aio = AIOClient(CONFIG["ADAFRUIT_IO_USERNAME"], CONFIG["ADAFRUIT_IO_KEY"])

# helper: postgres connection to Neon (cloud)
def get_pg_conn():
    url = CONFIG.get("NEON_DB_URL")
    if not url:
        raise RuntimeError("NEON_DB_URL not configured in config.json")
    return psycopg2.connect(dsn=url, cursor_factory=psycopg2.extras.RealDictCursor)

# Home / Dashboard
@app.route("/")
def home():
    # try to get live sensor values (server-side via Adafruit IO) as tiles
    live = {}
    feeds = {
        "temperature": "temperature",
        "humidity": "Humidity",
        "motion": "motion_feed",
        "pressure": "Pressure"
    }
    if aio:
        try:
            # attempt safe reads; wrap individually to avoid whole failure
            for key, feed_name in [("temperature","temperature"), ("humidity","Humidity"), ("motion","motion_feed"), ("pressure","Pressure")]:
                try:
                    val = aio.receive(feed_name).value
                    if key == "motion":
                        live[key] = int(val)
                    else:
                        live[key] = float(val)
                except Exception:
                    pass
        except Exception:
            pass

    # public drive link if available
    public_drive = CONFIG.get("PUBLIC_DRIVE_FOLDER_LINK", "")
    return render_template("home.html", live=live, public_drive=public_drive)

# Environmental page
@app.route("/environmental")
def environmental():
    return render_template("environmental.html")

# Device control
@app.route("/device-control")
def device_control():
    # minimal server-side actuator list (can also query cloud DB)
    actuators = CONFIG.get("ACTUATORS", {"LEDs":0, "Buzzer":0, "Servo":0, "Camera":0})
    return render_template("device_control.html", actuators=actuators)

# Manage security
@app.route("/manage-security")
def manage_security():
    return render_template("manage_security.html")

# About
@app.route("/about")
def about():
    return render_template("about.html")

# Serve images (if you want to host images on Flask server for preview)
IMAGES_DIR = os.path.join(BASE_DIR, "..", "images")  # common pattern if images are on Pi shared drive
if not os.path.exists(IMAGES_DIR):
    IMAGES_DIR = os.path.join(BASE_DIR, "static", "images")
@app.route("/images/<path:filename>")
def images(filename):
    return send_from_directory(IMAGES_DIR, filename)

# API: live sensors (prefer Adafruit; fallback to cloud Neon DB latest entry)
@app.route("/api/live-sensors")
def api_live_sensors():
    result = {}
    if aio:
        try:
            for feed in ["temperature", "Humidity", "motion_feed", "Pressure"]:
                try:
                    val = aio.receive(feed).value
                    # normalize keys
                    if feed.lower().startswith("temp"):
                        result["temperature"] = float(val)
                    elif feed.lower().startswith("humidity") or feed == "Humidity":
                        result["humidity"] = float(val)
                    elif "motion" in feed:
                        result["motion"] = int(val)
                    elif "pressure" in feed.lower() or feed == "Pressure":
                        result["pressure"] = float(val)
                except Exception:
                    pass
        except Exception:
            pass

    # If any missing values, try Neon DB latest row
    try:
        conn = get_pg_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT sensor_type, value, timestamp FROM environment_readings
            WHERE timestamp > now() - interval '1 hour'
            ORDER BY timestamp DESC
            LIMIT 20
        """)
        rows = cur.fetchall()
        for r in rows:
            st = r["sensor_type"].lower()
            if "temp" in st and "temperature" not in result:
                result["temperature"] = float(r["value"])
            if "humid" in st and "humidity" not in result:
                result["humidity"] = float(r["value"])
            if "pressure" in st and "pressure" not in result:
                result["pressure"] = float(r["value"])
        cur.close()
        conn.close()
    except Exception:
        pass

    return jsonify(result)

# API: historical temperature/humidity for date range (from Neon cloud)
@app.route("/api/temperature-history")
def api_temp_history():
    start = request.args.get("start")  # YYYY-MM-DD or full timestamp
    end = request.args.get("end")
    # default last 24 hours
    if not start or not end:
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=1)
    else:
        start_dt = datetime.fromisoformat(start) if len(start) > 10 else datetime.fromisoformat(start + "T00:00:00")
        end_dt = datetime.fromisoformat(end) if len(end) > 10 else datetime.fromisoformat(end + "T23:59:59")

    labels = []
    temps = []
    hums = []
    try:
        conn = get_pg_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT timestamp, sensor_type, value FROM environment_readings
            WHERE timestamp BETWEEN %s AND %s
            AND sensor_type IN ('temperature','Humidity','humidity')
            ORDER BY timestamp ASC
        """, (start_dt, end_dt))
        rows = cur.fetchall()
        # aggregate by timestamp: simple approach - collect matching sensor rows
        for r in rows:
            ts = r["timestamp"].isoformat(sep=" ")
            labels.append(ts)
            if "temp" in r["sensor_type"].lower():
                temps.append(float(r["value"]))
                hums.append(None)
            else:
                # humidity row
                # attempt to align: if last label equals this ts and temps has entry of None, fill appropriately
                temps.append(None)
                hums.append(float(r["value"]))
        cur.close()
        conn.close()
    except Exception:
        # fallback: return empty arrays
        pass

    return jsonify({"labels": labels, "temperature": temps, "humidity": hums})

# API: device control - sends command to Adafruit IO as feed
@app.route("/api/device/<device_name>/set", methods=["POST"])
def api_device_set(device_name):
    payload = request.get_json() or {}
    state = payload.get("state", 0)
    # send to Adafruit IO feed: <device_name>_control (normalized)
    feed_name = device_name.lower().replace(" ", "_")
    feed_send = f"{feed_name}_control"
    sent = False
    if aio:
        try:
            aio.send(feed_send, int(bool(state)))
            sent = True
        except Exception as e:
            print("Adafruit send error:", e)
            sent = False
    # We still return success (UI is optimistic)
    return jsonify({"device": device_name, "state": int(bool(state)), "sent_to_aio": sent})

# API: security list for a date (intrusion events) from Neon
@app.route("/api/security/list")
def api_security_list():
    date = request.args.get("date")
    if not date:
        return jsonify({"error": "date required (YYYY-MM-DD)"}), 400
    start_ts = f"{date}T00:00:00"
    end_ts = f"{date}T23:59:59"
    try:
        conn = get_pg_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, timestamp, event_type, image_url, processed FROM intrusion_events
            WHERE timestamp BETWEEN %s AND %s
            ORDER BY timestamp DESC
        """, (start_ts, end_ts))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        out = []
        for r in rows:
            out.append({"id": r["id"], "timestamp": r["timestamp"].isoformat(sep=" "), "event_type": r["event_type"], "image_url": r["image_url"], "processed": r["processed"]})
        return jsonify(out)
    except Exception as e:
        print("Neon query failed:", e)
        return jsonify([])

if __name__ == "__main__":
    # development server (no auth as requested)
    app.run(host="0.0.0.0", port=5000, debug=True)
