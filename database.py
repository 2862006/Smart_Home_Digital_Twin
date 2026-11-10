import json
import sqlite3

DB_FILE = "smart_home.db"
DEVICES = ("ac", "heater", "window", "light", "fan", "tv", "camera", "door")
ON_STATES = ("ON", "OPEN", "UNLOCKED")


def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS room_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            temperature REAL,
            humidity REAL,
            date TEXT
        );
        CREATE TABLE IF NOT EXISTS device_status (
            device TEXT PRIMARY KEY,
            status TEXT,
            version INTEGER
        );
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity TEXT,
            status TEXT,
            time TEXT
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS energy (
            device TEXT PRIMARY KEY,
            kwh REAL
        );
    """)
    for d in DEVICES:
        conn.execute("INSERT OR IGNORE INTO device_status VALUES (?, ?, ?)", (d, "OFF", 0))
    conn.commit()
    conn.close()


# ---------- room data ----------
def save_room(temp, hum):
    conn = get_conn()
    conn.execute(
        "INSERT INTO room_data (temperature, humidity, date) "
        "VALUES (?, ?, datetime('now','localtime'))",
        (temp, hum),
    )
    conn.commit()
    conn.close()


def get_room_history(limit=30):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM room_data ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows][::-1]


def count_room():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM room_data").fetchone()[0]
    conn.close()
    return n


def get_room_page(page=1, per_page=10):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM room_data ORDER BY id DESC LIMIT ? OFFSET ?",
        (per_page, (page - 1) * per_page),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- devices ----------
def save_device(device, state, version, label):
    conn = get_conn()
    conn.execute(
        "UPDATE device_status SET status=?, version=? WHERE device=?",
        (label, version, device),
    )
    conn.commit()
    conn.close()


def load_devices():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM device_status").fetchall()
    conn.close()
    return {r["device"]: (r["status"] in ON_STATES, r["version"]) for r in rows}


# ---------- logs ----------
def save_log(activity, status):
    conn = get_conn()
    conn.execute(
        "INSERT INTO activity_logs (activity, status, time) "
        "VALUES (?, ?, datetime('now','localtime'))",
        (activity, status),
    )
    conn.commit()
    conn.close()


def get_logs(limit=50):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM activity_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_notifications(limit=8):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM activity_logs WHERE status IN ('Alarm','Auto','Failed') "
        "ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- settings ----------
def save_settings(settings):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", ("all", json.dumps(settings)))
    conn.commit()
    conn.close()


def load_settings():
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key='all'").fetchone()
    conn.close()
    return json.loads(row["value"]) if row else None


# ---------- energy ----------
def save_energy(energy):
    conn = get_conn()
    conn.executemany(
        "INSERT OR REPLACE INTO energy VALUES (?, ?)",
        [(k, round(v, 5)) for k, v in energy.items()],
    )
    conn.commit()
    conn.close()


def load_energy():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM energy").fetchall()
    conn.close()
    return {r["device"]: r["kwh"] for r in rows}