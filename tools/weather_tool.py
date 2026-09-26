# ============================================
# tools/weather_tool.py  — with Smart Alerts
# ============================================

import logging
import os

import requests
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@tool
def get_weather(city: str) -> dict:
    """
    Get current weather and agricultural forecast for a Pakistani city.
    Useful for irrigation planning, spray scheduling, and harvest timing.

    Args:
        city: City name (e.g., 'Lahore', 'Faisalabad', 'Multan', 'Karachi', 'Peshawar')

    Returns:
        Weather data including temperature, humidity, wind, and farming advice.
    """
    api_key = os.getenv("OPENWEATHER_API_KEY", "")

    if api_key and api_key != "your_openweather_api_key_here":
        try:
            url = (
                f"https://api.openweathermap.org/data/2.5/weather"
                f"?q={city},PK&appid={api_key}&units=metric"
            )
            resp = requests.get(url, timeout=8)
            resp.raise_for_status()
            data = resp.json()

            weather = data.get("weather", [{}])[0]
            main = data.get("main", {})
            wind = data.get("wind", {})
            temp = main.get("temp", 25)
            wind_kmh = round(wind.get("speed", 0) * 3.6, 1)
            condition = weather.get("main", "Clear")
            tip = _farming_tip(temp, main.get("humidity", 50), condition)

            # ── ALERT HOOK ───────────────────────────────────
            try:
                from utils.alert_manager import get_alert_manager
                alert = get_alert_manager()
                alert.send_weather_alert(
                    city=city, temp=temp,
                    wind_kmh=wind_kmh, condition=condition,
                    farming_advice=tip
                )
            except Exception:
                # Alert failure must not prevent weather data from being returned,
                # but it must be visible in application logs.
                logger.exception("Failed to send weather alert for %s", city)
            # ─────────────────────────────────────────────────

            return {
                "city": city,
                "description": weather.get("description", "N/A"),
                "temperature_c": temp,
                "feels_like_c": main.get("feels_like"),
                "humidity_pct": main.get("humidity"),
                "wind_speed_kmh": wind_kmh,
                "farming_tip": tip,
            }
        except requests.RequestException as exc:
            logger.warning("Weather API request failed for %s: %s", city, exc)
        except ValueError as exc:
            logger.error("Weather API returned invalid JSON for %s: %s", city, exc)
        except Exception:
            logger.exception("Unexpected error while retrieving weather for %s", city)
    else:
        logger.warning("OPENWEATHER_API_KEY is missing or still uses the placeholder value")

    return {
        "city": city,
        "note": "Live weather unavailable. Add OPENWEATHER_API_KEY to .env for real-time data.",
        "general_advice": (
            f"For {city}: Check Pakistan Meteorological Department (pmd.gov.pk) "
            "for latest forecasts. Plan irrigation based on soil moisture, not fixed schedules."
        )
    }


def _farming_tip(temp: float, humidity: float, condition: str) -> str:
    tips = []
    if temp > 38:
        tips.append("Extreme heat — increase irrigation frequency. Avoid spraying pesticides.")
    elif temp < 5:
        tips.append("Risk of frost — protect young crops. Delay transplanting.")
    else:
        tips.append("Temperature is suitable for most field operations.")
    if humidity > 80:
        tips.append("High humidity — monitor for fungal diseases (blight, rust).")
    elif humidity < 30:
        tips.append("Low humidity — crops may face moisture stress. Check soil.")
    if "rain" in condition.lower():
        tips.append("Rain expected — postpone pesticide/fertilizer application.")
    return " | ".join(tips) if tips else "Conditions normal for farming."
