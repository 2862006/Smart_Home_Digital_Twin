import requests
from datetime import datetime

LAT, LON = 20.27, 85.84  # Bhubaneswar

WEATHER_CODES = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Fog", 51: "Drizzle", 53: "Drizzle", 55: "Drizzle",
    61: "Rain", 63: "Rain", 65: "Heavy rain", 80: "Showers",
    81: "Showers", 82: "Heavy showers", 95: "Thunderstorm",
}

FALLBACK = {
    "temp": 35.0, "humidity": 70.0, "feels": 38.0, "precip": 0.0,
    "pressure": 1008.0, "wind": 9.0, "visibility": 10.0,
    "condition": "Offline (fallback)", "sunrise": "05:45", "sunset": "17:35",
    "forecast": [
        {"day": "Day 1", "max": 34, "min": 25, "condition": "Clear"},
        {"day": "Day 2", "max": 33, "min": 25, "condition": "Partly cloudy"},
        {"day": "Day 3", "max": 32, "min": 24, "condition": "Rain"},
    ],
}


def get_weather():
    """Live outside weather + 3 din ka forecast. Fail ho to fallback values."""
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": LAT,
                "longitude": LON,
                "current": ("temperature_2m,relative_humidity_2m,apparent_temperature,"
                            "precipitation,weather_code,surface_pressure,"
                            "wind_speed_10m,visibility"),
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset",
                "timezone": "auto",
                "forecast_days": 4,
            },
            timeout=5,
        )
        j = r.json()
        c, d = j["current"], j["daily"]
        vis = c.get("visibility")
        forecast = []
        for i in range(1, 4):
            forecast.append({
                "day": datetime.strptime(d["time"][i], "%Y-%m-%d").strftime("%a"),
                "max": round(d["temperature_2m_max"][i]),
                "min": round(d["temperature_2m_min"][i]),
                "condition": WEATHER_CODES.get(d["weather_code"][i], "Unknown"),
            })
        return {
            "temp": c["temperature_2m"],
            "humidity": c["relative_humidity_2m"],
            "feels": c["apparent_temperature"],
            "precip": c["precipitation"],
            "pressure": round(c["surface_pressure"], 1),
            "wind": c["wind_speed_10m"],
            "visibility": round(vis / 1000, 1) if vis is not None else None,
            "condition": WEATHER_CODES.get(c["weather_code"], "Unknown"),
            "sunrise": d["sunrise"][0][11:16],
            "sunset": d["sunset"][0][11:16],
            "forecast": forecast,
        }
    except Exception as e:
        print("Weather API error:", e)
        return dict(FALLBACK)