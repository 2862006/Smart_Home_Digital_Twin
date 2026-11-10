import random

NAMES = {
    "ac": "Air Conditioner", "heater": "Heater", "window": "Smart Window",
    "light": "Smart Light", "fan": "Fan", "tv": "Smart TV",
    "camera": "Security Camera", "door": "Front Door",
}
LABELS = {"window": ("CLOSED", "OPEN"), "door": ("LOCKED", "UNLOCKED")}
RATE = 7.0  # Rs per kWh


def label(device, state):
    off, on = LABELS.get(device, ("OFF", "ON"))
    return on if state else off


SCENES = {
    "morning": {"title": "Good Morning", "window": True, "heater": False, "ac": False,
                "light": True, "tv": False, "fan": False},
    "movie": {"title": "Movie Night", "window": False, "light": True, "tv": True,
              "fan": True, "brightness": 20},
    "bedtime": {"title": "Bed Time", "window": False, "light": False, "tv": False,
                "heater": False, "ac": True, "fan": False, "door": False, "camera": True},
    "away": {"title": "Away Mode", "window": False, "heater": False, "ac": False,
             "light": False, "tv": False, "fan": False, "door": False, "camera": True},
}


class SmartRoom:
    """Virtual room ka Digital Twin."""

    MIN_TEMP, MAX_TEMP = 16.0, 42.0

    def __init__(self, temp=30.0, humidity=60.0, outside_temp=35.0, outside_humidity=70.0):
        self.temp = temp
        self.humidity = humidity
        self.outside_temp = outside_temp
        self.outside_humidity = outside_humidity

        self.devices = {d: False for d in NAMES}
        self.versions = {d: 0 for d in NAMES}
        self.settings = {
            "target": 24, "auto": False, "alarm": 32, "ac_mode": "cool",
            "fan_speed": 2, "brightness": 70,
            "members": {"Roshan": True, "Dad": False, "Mom": True, "Guest": False},
        }
        self.co2 = 480.0
        self.pm25 = 10.0
        self.alarm = False
        self.energy = {d: 0.0 for d in list(NAMES) + ["wifi"]}
        self.power_hist = []
        self.logs = []
        self.events = []

    # ---------- helpers ----------
    def _log(self, msg):
        self.logs.append(msg)
        print("   LOG:", msg)

    def pop_events(self):
        ev, self.events = self.events, []
        return ev

    def occupants(self):
        return sum(1 for v in self.settings["members"].values() if v)

    def _reject(self, msg):
        self._log(msg)
        return False, msg

    def _force(self, device, state, msg=None, status="Auto"):
        """Server-side change (automation/scene). Version bump hota hai."""
        if self.devices[device] == state:
            return False
        if state and device == "ac" and self.devices["heater"]:
            self._force("heater", False)
        if state and device == "heater":
            if self.devices["window"]:
                return False
            if self.devices["ac"]:
                self._force("ac", False)
        self.devices[device] = state
        self.versions[device] += 1
        self.events.append({"device": device, "state": state, "msg": msg, "status": status})
        if msg:
            self._log(msg)
        return True

    # ---------- commands ----------
    def send_command(self, device, state, version):
        """User command (version ke saath). Returns (success, message)."""
        if device not in self.devices:
            return self._reject("Unknown device")
        name = NAMES[device]

        # Purani / delayed command ignore
        if version <= self.versions[device]:
            return self._reject(
                f"IGNORED stale command: {name} -> {label(device, state)} "
                f"(v{version} <= v{self.versions[device]})")

        if state and device == "ac" and self.devices["heater"]:
            return self._reject("REJECTED: Heater is ON, turn it OFF first")
        if state and device == "heater" and self.devices["ac"]:
            return self._reject("REJECTED: AC is ON, turn it OFF first")
        if state and device == "heater" and self.devices["window"]:
            return self._reject("REJECTED: Window is OPEN, heater locked")

        self.devices[device] = state
        self.versions[device] = version
        self._log(f"APPLIED: {name} -> {label(device, state)} (v{version})")

        # Rule: WHEN window OPEN -> THEN heater OFF
        if device == "window" and state and self.devices["heater"]:
            self._force("heater", False, "AUTO: Window opened -> Heater turned OFF")
        return True, f"{name} {label(device, state)}"

    def apply_scene(self, key):
        sc = SCENES.get(key)
        if not sc:
            return False, "Unknown scene"
        for dev, val in sc.items():
            if dev == "title":
                continue
            if dev == "brightness":
                self.settings["brightness"] = val
            else:
                self._force(dev, val)
        msg = f"SCENE: {sc['title']} applied"
        self.events.append({"device": None, "state": None, "msg": msg, "status": "Scene"})
        self._log(msg)
        return True, msg

    def set_setting(self, key, value):
        s = self.settings
        if key == "target":
            v = int(value)
            if not 16 <= v <= 30:
                return False, "Target must be between 16 and 30 C"
            s["target"] = v
            msg = f"Target temperature set to {v} C"
        elif key == "auto":
            s["auto"] = bool(value)
            msg = "Auto thermostat " + ("ENABLED" if s["auto"] else "DISABLED")
        elif key == "alarm":
            v = int(value)
            if not 25 <= v <= 40:
                return False, "Alarm limit must be between 25 and 40 C"
            s["alarm"] = v
            msg = f"Temperature alarm limit set to {v} C"
        elif key == "ac_mode":
            if value not in ("cool", "dry"):
                return False, "Invalid AC mode"
            s["ac_mode"] = value
            msg = f"AC mode set to {value.upper()}"
        elif key == "fan_speed":
            v = int(value)
            if v not in (1, 2, 3):
                return False, "Invalid fan speed"
            s["fan_speed"] = v
            msg = f"Fan speed set to {['', 'LOW', 'MEDIUM', 'HIGH'][v]}"
        elif key == "brightness":
            v = int(value)
            if not 0 <= v <= 100:
                return False, "Invalid brightness"
            s["brightness"] = v
            msg = f"Light brightness set to {v}%"
        else:
            return False, "Unknown setting"
        self._log(msg)
        self.events.append({"device": None, "state": None, "msg": msg, "status": "Successful"})
        return True, msg

    def set_member(self, name, home):
        if name not in self.settings["members"]:
            return False, "Unknown member"
        self.settings["members"][name] = bool(home)
        msg = f"{name} is now {'HOME' if home else 'AWAY'}"
        self._log(msg)
        self.events.append({"device": None, "state": None, "msg": msg, "status": "Successful"})
        return True, msg

    # ---------- simulation ----------
    def _auto(self):
        s, d = self.settings, self.devices
        if not s["auto"]:
            return
        t, tg = self.temp, s["target"]
        if t > tg + 1 and not d["ac"]:
            self._force("ac", True, f"AUTO: {t:.1f} C > target {tg} C -> AC ON")
        elif t < tg - 1 and not d["heater"] and not d["window"]:
            self._force("heater", True, f"AUTO: {t:.1f} C < target {tg} C -> Heater ON")
        elif d["ac"] and t <= tg:
            self._force("ac", False, f"AUTO: Target {tg} C reached -> AC OFF")
        elif d["heater"] and t >= tg:
            self._force("heater", False, f"AUTO: Target {tg} C reached -> Heater OFF")

    def power(self):
        d, s = self.devices, self.settings
        p = {k: 0.0 for k in self.energy}
        if d["ac"]:
            p["ac"] = 1500 if s["ac_mode"] == "cool" else 1100
        if d["heater"]:
            p["heater"] = 2000
        if d["fan"]:
            p["fan"] = 20 + 25 * s["fan_speed"]
        if d["light"]:
            p["light"] = round(60 * s["brightness"] / 100, 1)
        if d["tv"]:
            p["tv"] = 110
        if d["camera"]:
            p["camera"] = 8
        p["wifi"] = 10
        return p

    def tick(self):
        """Simulation ka 1 step (~1 minute)."""
        self._auto()
        d, s = self.devices, self.settings
        occ = self.occupants()

        if d["ac"]:
            if s["ac_mode"] == "cool":
                self.temp -= 0.8
                self.humidity -= 0.5
            else:
                self.temp -= 0.25
                self.humidity -= 1.0
        if d["heater"]:
            self.temp += 0.8
            self.humidity -= 0.2
        if d["fan"]:
            self.temp -= 0.06 * s["fan_speed"]
        if d["tv"]:
            self.temp += 0.02
        if d["light"]:
            self.temp += 0.02
        self.temp += 0.03 * occ
        self.humidity += 0.1 * occ

        k = 0.10 if d["window"] else 0.01
        self.temp += k * (self.outside_temp - self.temp) + random.uniform(-0.05, 0.05)
        self.humidity += k * (self.outside_humidity - self.humidity)
        self.temp = max(self.MIN_TEMP, min(self.MAX_TEMP, self.temp))
        self.humidity = max(0.0, min(100.0, self.humidity))

        # Air quality
        win = d["window"]
        self.co2 += (0 if win else 4 * occ) + (420 - self.co2) * (0.15 if win else 0.005)
        self.co2 = max(400.0, min(2000.0, self.co2))
        target_pm = 8 + (15 if win else 0)
        self.pm25 += (target_pm - self.pm25) * 0.2 + random.uniform(-0.5, 0.5)
        self.pm25 = max(1.0, self.pm25)

        # Temperature alarm
        hot = self.temp > s["alarm"]
        if hot and not self.alarm:
            self.alarm = True
            msg = f"ALARM: Temperature {self.temp:.1f} C crossed limit {s['alarm']} C"
            self.events.append({"device": None, "state": None, "msg": msg, "status": "Alarm"})
            self._log(msg)
        elif not hot and self.alarm:
            self.alarm = False
            msg = "Alarm cleared: temperature back to normal"
            self.events.append({"device": None, "state": None, "msg": msg, "status": "Successful"})
            self._log(msg)

        # Energy (1 tick = 1 simulated minute)
        p = self.power()
        for dev, w in p.items():
            self.energy[dev] += w / 1000 / 60
        self.power_hist.append(round(sum(p.values()) / 1000, 2))
        del self.power_hist[:-30]

    def air_label(self):
        if self.co2 < 800 and self.pm25 < 25:
            return "Good"
        if self.co2 < 1200 and self.pm25 < 40:
            return "Moderate"
        return "Poor"

    def status(self):
        p = self.power()
        kwh = sum(self.energy.values())
        return {
            "temperature": round(self.temp, 1),
            "humidity": round(self.humidity, 1),
            "outside_temp": self.outside_temp,
            "outside_humidity": self.outside_humidity,
            "devices": dict(self.devices),
            "labels": {k: label(k, v) for k, v in self.devices.items()},
            "versions": dict(self.versions),
            "settings": {**self.settings, "members": dict(self.settings["members"])},
            "co2": round(self.co2),
            "pm25": round(self.pm25),
            "air": self.air_label(),
            "alarm": self.alarm,
            "power": {k: round(v) for k, v in p.items()},
            "total_kw": round(sum(p.values()) / 1000, 2),
            "energy": {k: round(v, 3) for k, v in self.energy.items()},
            "kwh_total": round(kwh, 3),
            "cost": round(kwh * RATE, 2),
            "power_hist": list(self.power_hist),
            "occupants": self.occupants(),
            "secure": (not self.devices["door"]) and (not self.devices["window"]),
        }


if __name__ == "__main__":
    room = SmartRoom()
    room.send_command("heater", True, 1)
    room.send_command("window", True, 1)   # heater auto OFF
    room.send_command("heater", True, 2)   # REJECTED
    room.send_command("ac", True, 0)       # stale
    for _ in range(3):
        room.tick()
    print(room.status())