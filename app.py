import threading
import time
from flask import Flask, jsonify, request, render_template
from simulation import SmartRoom, label
from weather import get_weather
import database as db

app = Flask(__name__)
db.init_db()

weather_info = get_weather()
room = SmartRoom(temp=30, humidity=60,
                 outside_temp=weather_info["temp"],
                 outside_humidity=weather_info["humidity"])

# Pichla saved state restore karo
for dev, (state, ver) in db.load_devices().items():
    if dev in room.devices:
        room.devices[dev] = state
        room.versions[dev] = ver
saved = db.load_settings()
if saved:
    for k, v in saved.items():
        if k in room.settings and k != "members":
            room.settings[k] = v
    room.settings["members"].update(saved.get("members", {}))
room.energy.update(db.load_energy())

# Safety: window open ho to heater OFF
if room.devices["window"] and room.devices["heater"]:
    room.devices["heater"] = False
    db.save_device("heater", False, room.versions["heater"], label("heater", False))

lock = threading.Lock()


def persist(save_cfg=False):
    """Events (automation/scene/settings) ko database mein save karo. Lock ke andar call karo."""
    for e in room.pop_events():
        if e["device"]:
            db.save_device(e["device"], e["state"], room.versions[e["device"]],
                           label(e["device"], e["state"]))
        if e["msg"]:
            db.save_log(e["msg"], e["status"])
    if save_cfg:
        db.save_settings(room.settings)


def simulation_loop():
    last_weather = time.time()
    while True:
        time.sleep(2)
        try:
            if time.time() - last_weather > 300:
                nw = get_weather()
                last_weather = time.time()
                with lock:
                    room.outside_temp = nw["temp"]
                    room.outside_humidity = nw["humidity"]
                    weather_info.update(nw)
            with lock:
                room.tick()
                persist()
                s = room.status()
                db.save_room(s["temperature"], s["humidity"])
                db.save_energy(room.energy)
        except Exception as e:
            print("Simulation loop error:", e)


threading.Thread(target=simulation_loop, daemon=True).start()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    with lock:
        data = room.status()
        data["weather"] = dict(weather_info)
    data["logs"] = [f"[{l['time']}] {l['activity']} - {l['status']}" for l in db.get_logs(10)]
    data["notifications"] = db.get_notifications(6)
    return jsonify(data)


@app.route("/api/history")
def history():
    n = max(5, min(500, request.args.get("n", 30, type=int)))
    rows = db.get_room_history(n)
    return jsonify([
        {"t": r["date"][11:], "temp": r["temperature"], "hum": r["humidity"]}
        for r in rows
    ])


@app.route("/api/command", methods=["POST"])
def command():
    body = request.get_json()
    device = body["device"]
    state = bool(body["state"])
    version = int(body["version"])
    with lock:
        ok, msg = room.send_command(device, state, version)
        if ok:
            db.save_device(device, state, version, label(device, state))
            db.save_log(msg, "Successful")
        else:
            db.save_log(msg, "Failed")
        persist()
    return jsonify({"success": ok, "message": msg})


@app.route("/api/settings", methods=["POST"])
def settings():
    body = request.get_json() or {}
    with lock:
        try:
            if "member" in body:
                ok, msg = room.set_member(body["member"], bool(body["home"]))
            else:
                key = next(iter(body))
                ok, msg = room.set_setting(key, body[key])
        except (ValueError, TypeError, StopIteration):
            ok, msg = False, "Invalid value"
        persist(save_cfg=True)
    return jsonify({"success": ok, "message": msg})


@app.route("/api/scene", methods=["POST"])
def scene():
    body = request.get_json() or {}
    with lock:
        ok, msg = room.apply_scene(body.get("scene", ""))
        persist(save_cfg=True)
    return jsonify({"success": ok, "message": msg})


@app.route("/api/records")
def records():
    return jsonify({"logs": db.get_logs(30)})


@app.route("/api/raw")
def raw():
    per = max(1, min(50, request.args.get("per", 10, type=int)))
    total = db.count_room()
    pages = max(1, -(-total // per))
    page = max(1, min(pages, request.args.get("page", 1, type=int)))
    return jsonify({"rows": db.get_room_page(page, per), "page": page,
                    "pages": pages, "total": total})


if __name__ == "__main__":
    app.run(debug=False, port=5000)