"""
Weather for GehunGuru.

* Live 7-day forecast from Open-Meteo (free, no API key, no personal data sent:
  only the district's latitude/longitude).
* Sample "scenario" weeks for demos (a January cold-humid spell, a March heat
  wave, ...) so every rule can be shown regardless of the real season.
* Deterministic alert RULES. The AI never decides whether an alert fires; it
  only explains the alerts. This keeps safety-relevant logic predictable.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, timedelta

import requests

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# name -> (lat, lon, state, foothill_rust_hotspot)
DISTRICTS: dict[str, tuple[float, float, str, bool]] = {
    "Ludhiana": (30.901, 75.857, "Punjab", False),
    "Amritsar": (31.634, 74.872, "Punjab", False),
    "Gurdaspur": (32.041, 75.405, "Punjab", True),
    "Hoshiarpur": (31.532, 75.911, "Punjab", True),
    "Patiala": (30.340, 76.386, "Punjab", False),
    "Bathinda": (30.211, 74.945, "Punjab", False),
    "Karnal": (29.686, 76.990, "Haryana", False),
    "Ambala": (30.378, 76.777, "Haryana", True),
    "Yamunanagar": (30.129, 77.268, "Haryana", True),
    "Hisar": (29.149, 75.722, "Haryana", False),
    "Sirsa": (29.536, 75.028, "Haryana", False),
    "Meerut": (28.984, 77.706, "Uttar Pradesh", False),
    "Muzaffarnagar": (29.473, 77.708, "Uttar Pradesh", False),
    "Delhi (NCT)": (28.644, 77.216, "Delhi", False),
    "Sri Ganganagar": (29.904, 73.877, "Rajasthan", False),
}


@dataclass
class Day:
    date: date
    tmax: float
    tmin: float
    rain_mm: float
    rain_prob: float
    wind_max: float
    rh_mean: float

    def label(self) -> str:
        return self.date.strftime("%a %d %b")


@dataclass
class Alert:
    level: str   # "high" | "warn" | "info" | "good"
    code: str
    title: str
    message: str

    def as_dict(self) -> dict:
        return asdict(self)


class WeatherUnavailable(Exception):
    pass


# --------------------------------------------------------------------------- live


def fetch_forecast(lat: float, lon: float, timeout: float = 8.0) -> list[Day]:
    """Fetch a 7-day daily forecast from Open-Meteo. Raises WeatherUnavailable."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join([
            "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
            "precipitation_probability_max", "wind_speed_10m_max",
        ]),
        "hourly": "relative_humidity_2m",
        "timezone": "Asia/Kolkata",
        "forecast_days": 7,
    }
    try:
        r = requests.get(OPEN_METEO_URL, params=params, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return parse_open_meteo(data)
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        raise WeatherUnavailable(str(exc)) from exc


def parse_open_meteo(data: dict) -> list[Day]:
    daily = data["daily"]
    hourly = data.get("hourly", {})
    # daily mean relative humidity from hourly values
    rh_by_day: dict[str, list[float]] = {}
    for t, v in zip(hourly.get("time", []), hourly.get("relative_humidity_2m", [])):
        if v is not None:
            rh_by_day.setdefault(t[:10], []).append(float(v))

    def num(key: str, i: int, default: float = 0.0) -> float:
        vals = daily.get(key) or []
        v = vals[i] if i < len(vals) else None
        return float(v) if v is not None else default

    days = []
    for i, d in enumerate(daily["time"]):
        rh = rh_by_day.get(d, [])
        days.append(Day(
            date=date.fromisoformat(d),
            tmax=num("temperature_2m_max", i),
            tmin=num("temperature_2m_min", i),
            rain_mm=num("precipitation_sum", i),
            rain_prob=num("precipitation_probability_max", i),
            wind_max=num("wind_speed_10m_max", i),
            rh_mean=round(sum(rh) / len(rh), 0) if rh else 60.0,
        ))
    if not days:
        raise ValueError("empty forecast")
    return days


# ---------------------------------------------------------------------- scenarios

SCENARIOS: dict[str, dict] = {
    "cold_humid": {
        "label": "Sample: cold & humid spell (January)",
        # tmax, tmin, rain, prob, wind, rh  per day
        "days": [(17, 7, 0, 10, 7, 86), (15, 6, 1, 30, 6, 90), (14, 8, 2, 40, 6, 92),
                 (16, 7, 0, 20, 8, 88), (17, 6, 0, 10, 7, 85), (18, 7, 0, 5, 9, 80), (18, 8, 0, 5, 8, 78)],
    },
    "heat_wave": {
        "label": "Sample: early heat wave (March)",
        "days": [(31, 16, 0, 0, 11, 42), (33, 17, 0, 0, 12, 38), (35, 19, 0, 0, 14, 35),
                 (36, 20, 0, 0, 13, 33), (34, 19, 0, 5, 10, 40), (33, 18, 0, 5, 9, 42), (32, 17, 0, 0, 9, 45)],
    },
    "rain_wind": {
        "label": "Sample: rain and strong wind",
        "days": [(22, 10, 0, 20, 12, 70), (19, 11, 18, 85, 26, 88), (18, 10, 8, 70, 22, 90),
                 (21, 9, 0, 20, 14, 78), (22, 9, 0, 10, 10, 70), (23, 10, 0, 5, 9, 65), (23, 10, 0, 5, 8, 62)],
    },
    "frost": {
        "label": "Sample: clear nights with frost risk",
        "days": [(17, 3, 0, 0, 5, 78), (16, 1, 0, 0, 4, 80), (15, 0, 0, 0, 4, 82),
                 (16, 2, 0, 0, 5, 76), (18, 4, 0, 0, 6, 72), (19, 5, 0, 0, 7, 70), (19, 5, 0, 0, 7, 68)],
    },
    "mild_winter": {
        "label": "Sample: mild, dry week (no risks)",
        "days": [(22, 8, 0, 5, 8, 62), (23, 9, 0, 5, 9, 60), (22, 8, 0, 10, 8, 64),
                 (21, 8, 0, 10, 7, 66), (22, 9, 0, 5, 8, 62), (23, 9, 0, 5, 9, 60), (23, 10, 0, 5, 9, 58)],
    },
}


def scenario_days(key: str, start: date) -> list[Day]:
    rows = SCENARIOS[key]["days"]
    return [Day(start + timedelta(days=i), *map(float, r)) for i, r in enumerate(rows)]


# -------------------------------------------------------------------------- rules

RUST_STAGES = {"tillering", "jointing", "booting", "heading"}
HEAT_STAGES = {"heading", "milk", "dough"}
LATE_STAGES = {"booting", "heading", "milk", "dough"}


def evaluate_alerts(days: list[Day], stage_key: str, status: str, foothill: bool = False) -> list[Alert]:
    """Apply fixed agronomy rules to the forecast. Pure function (unit-tested)."""
    alerts: list[Alert] = []
    if not days:
        return alerts
    sown = status == "growing"
    next3 = days[:3]

    # 1. Rain soon
    rainy = [d for d in next3 if d.rain_mm >= 5 or d.rain_prob >= 60]
    if rainy:
        d = rainy[0]
        if sown:
            msg = ("Hold irrigation and urea top-dressing until after the rain, and do not spray "
                   "within 24 hours before rain.")
        else:
            msg = "Do not work wet soil; plan sowing once the field comes back to proper moisture (vattar)."
        alerts.append(Alert("warn", "RAIN_SOON",
                            f"Rain likely on {d.label()} (~{d.rain_mm:.0f} mm, {d.rain_prob:.0f}% chance)", msg))

    # 2. Heavy rain
    heavy = [d for d in days if d.rain_mm >= 20]
    if heavy:
        d = heavy[0]
        alerts.append(Alert("high" if sown else "warn", "HEAVY_RAIN", f"Heavy rain on {d.label()} ({d.rain_mm:.0f} mm)",
                            "Keep drainage channels open; standing water turns young wheat yellow."))

    # 3. Wind
    windy = [d for d in next3 if d.wind_max >= 15]
    if windy:
        d = windy[0]
        late = sown and stage_key in LATE_STAGES
        msg = "Avoid spraying on windy days (drift and poor coverage)."
        if late:
            msg += " At this stage do not irrigate just before strong wind; the crop may lodge."
        alerts.append(Alert("warn" if late else "info", "WINDY",
                            f"Wind up to {d.wind_max:.0f} km/h on {d.label()}", msg))

    # 4. Yellow rust weather
    if sown and stage_key in RUST_STAGES:
        rust_days = [d for d in days if d.tmax <= 22 and 4 <= d.tmin <= 13 and d.rh_mean >= 70]
        if len(rust_days) >= 2:
            where = " Your district is a known yellow-rust hotspot." if foothill else ""
            alerts.append(Alert("high" if foothill else "warn", "RUST_RISK",
                                f"Cool, humid weather on {len(rust_days)} days favours yellow rust",
                                "Walk the field this week and check leaves for yellow powdery stripes, "
                                "especially near tree lines." + where))

    # 5. Terminal heat
    if sown and stage_key in HEAT_STAGES:
        hottest = max(days, key=lambda d: d.tmax)
        if hottest.tmax >= 35:
            alerts.append(Alert("high", "HEAT_SEVERE", f"Severe heat: {hottest.tmax:.0f} °C on {hottest.label()}",
                                "Grain filling is at risk. Give a light irrigation in the evening and keep the "
                                "crop free of water stress (avoid irrigating before strong wind)."))
        elif hottest.tmax >= 32:
            alerts.append(Alert("warn", "HEAT", f"Heat stress: {hottest.tmax:.0f} °C on {hottest.label()}",
                                "Keep soil moist during grain filling; a light evening irrigation helps."))

    # 6. Frost
    if sown:
        coldest = min(days, key=lambda d: d.tmin)
        if coldest.tmin <= 2:
            lvl = "high" if stage_key in {"heading", "booting"} else "warn"
            alerts.append(Alert(lvl, "FROST", f"Frost risk: {coldest.tmin:.0f} °C on the night of {coldest.label()}",
                                "A light irrigation in the evening before a frosty night keeps the field warmer."))

    # 7./8. Sowing temperature (pre-sowing only)
    if not sown:
        first5 = days[:5]
        mean_t = sum((d.tmax + d.tmin) / 2 for d in first5) / len(first5)
        if mean_t > 24:
            alerts.append(Alert("info", "TOO_WARM_TO_SOW",
                                f"Still warm for sowing wheat (average {mean_t:.0f} °C)",
                                "Wheat germinates and tillers best when the average day temperature is about "
                                "20-22 °C, usually from late October to mid-November here. Use this time to "
                                "manage paddy straw without burning and arrange seed."))
        elif 16 <= mean_t <= 24 and not heavy:
            alerts.append(Alert("good", "SOWING_WEATHER_OK", f"Temperature suits sowing (average {mean_t:.0f} °C)",
                                "If your field has proper moisture (vattar), this is a good week to sow."))

    if sown and not alerts:
        alerts.append(Alert("good", "NO_RISK", "No weather risks this week",
                            "Continue normal operations for this stage."))

    order = {"high": 0, "warn": 1, "info": 2, "good": 3}
    alerts.sort(key=lambda a: order.get(a.level, 9))
    return alerts


def summary_for_prompt(days: list[Day], source_label: str) -> str:
    lines = [f"Source: {source_label}"]
    for d in days:
        lines.append(
            f"- {d.label()}: max {d.tmax:.0f} °C, min {d.tmin:.0f} °C, rain {d.rain_mm:.0f} mm "
            f"({d.rain_prob:.0f}%), wind {d.wind_max:.0f} km/h, humidity {d.rh_mean:.0f}%"
        )
    return "\n".join(lines)
