from __future__ import annotations

import json
import os
from pathlib import Path

import feedparser
import requests
import streamlit as st

PREFS_PATH = Path(
    os.environ.get("DAILY_BRIEFING_PREFS", Path(__file__).with_name("preferences.json"))
)

FEEDS = {
    "BBC News": "https://feeds.bbci.co.uk/news/rss.xml",
    "NPR News": "https://feeds.npr.org/1001/rss.xml",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
}

DEFAULT_PREFS = {
    "city": "New York",
    "units": "fahrenheit",
    "show_air_quality": True,
    "feeds": ["BBC News", "NPR News"],
}

WEATHER_LABELS = {
    0: "Clear",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Rain showers",
    82: "Heavy rain showers",
    85: "Snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with hail",
}


def load_prefs() -> dict:
    if not PREFS_PATH.exists():
        return dict(DEFAULT_PREFS)
    try:
        saved = json.loads(PREFS_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_PREFS)
    prefs = dict(DEFAULT_PREFS)
    prefs.update({key: saved[key] for key in DEFAULT_PREFS if key in saved})
    prefs["feeds"] = [name for name in prefs["feeds"] if name in FEEDS]
    if prefs["units"] not in ("celsius", "fahrenheit"):
        prefs["units"] = DEFAULT_PREFS["units"]
    return prefs


def save_prefs(prefs: dict) -> None:
    PREFS_PATH.write_text(json.dumps(prefs, indent=2) + "\n")


def weather_label(code: int | None) -> str:
    if code is None:
        return "Unknown"
    return WEATHER_LABELS.get(int(code), f"Code {int(code)}")


def aqi_label(aqi: float | None) -> str:
    if aqi is None:
        return "Unavailable"
    value = int(round(aqi))
    if value <= 50:
        band = "Good"
    elif value <= 100:
        band = "Moderate"
    elif value <= 150:
        band = "Unhealthy for sensitive groups"
    elif value <= 200:
        band = "Unhealthy"
    elif value <= 300:
        band = "Very unhealthy"
    else:
        band = "Hazardous"
    return f"{value} · {band}"


@st.cache_data(ttl=60 * 30, show_spinner=False)
def geocode(city: str) -> dict | None:
    response = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "en", "format": "json"},
        timeout=15,
    )
    response.raise_for_status()
    results = response.json().get("results") or []
    return results[0] if results else None


@st.cache_data(ttl=60 * 15, show_spinner=False)
def fetch_weather(latitude: float, longitude: float, units: str) -> dict:
    temperature_unit = "fahrenheit" if units == "fahrenheit" else "celsius"
    wind_unit = "mph" if units == "fahrenheit" else "kmh"
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "temperature_unit": temperature_unit,
            "wind_speed_unit": wind_unit,
            "timezone": "auto",
            "forecast_days": 5,
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=60 * 15, show_spinner=False)
def fetch_air_quality(latitude: float, longitude: float) -> dict:
    response = requests.get(
        "https://air-quality-api.open-meteo.com/v1/air-quality",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": "us_aqi,pm2_5,pm10",
            "timezone": "auto",
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=60 * 15, show_spinner=False)
def fetch_headlines(url: str, limit: int = 5) -> list[dict]:
    response = requests.get(
        url,
        timeout=15,
        headers={"User-Agent": "daily-briefing/0.1"},
    )
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    headlines = []
    for entry in parsed.entries[:limit]:
        headlines.append(
            {
                "title": entry.get("title") or "Untitled",
                "link": entry.get("link") or "",
                "published": entry.get("published") or "",
            }
        )
    return headlines


def place_name(place: dict) -> str:
    parts = [place.get("name"), place.get("admin1"), place.get("country")]
    return ", ".join(part for part in parts if part)


def render_weather(place: dict, units: str) -> None:
    payload = fetch_weather(place["latitude"], place["longitude"], units)
    current = payload.get("current") or {}
    daily = payload.get("daily") or {}
    unit_symbol = "°F" if units == "fahrenheit" else "°C"
    wind_symbol = "mph" if units == "fahrenheit" else "km/h"

    st.subheader(place_name(place))
    temp = current.get("temperature_2m")
    feels = current.get("apparent_temperature")
    wind = current.get("wind_speed_10m")
    columns = st.columns(3)
    columns[0].metric(
        "Temperature",
        f"{temp:.0f}{unit_symbol}" if temp is not None else "—",
        f"Feels {feels:.0f}{unit_symbol}" if feels is not None else None,
    )
    columns[1].metric("Conditions", weather_label(current.get("weather_code")))
    columns[2].metric(
        "Wind",
        f"{wind:.0f} {wind_symbol}" if wind is not None else "—",
    )

    dates = daily.get("time") or []
    if not dates:
        return

    st.markdown("**Next few days**")
    day_columns = st.columns(len(dates))
    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    codes = daily.get("weather_code") or []
    rain = daily.get("precipitation_probability_max") or []
    for index, day in enumerate(dates):
        high = highs[index] if index < len(highs) else None
        low = lows[index] if index < len(lows) else None
        code = codes[index] if index < len(codes) else None
        chance = rain[index] if index < len(rain) else None
        with day_columns[index]:
            st.caption(day[5:] if len(day) >= 10 else day)
            st.write(weather_label(code))
            if high is not None and low is not None:
                st.write(f"{high:.0f}° / {low:.0f}°")
            if chance is not None:
                st.caption(f"Rain {int(chance)}%")


def render_air_quality(place: dict) -> None:
    payload = fetch_air_quality(place["latitude"], place["longitude"])
    current = payload.get("current") or {}
    aqi = current.get("us_aqi")
    pm25 = current.get("pm2_5")
    pm10 = current.get("pm10")
    st.markdown("**Air quality**")
    columns = st.columns(3)
    columns[0].metric("US AQI", aqi_label(aqi))
    columns[1].metric("PM2.5", f"{pm25:.1f} µg/m³" if pm25 is not None else "—")
    columns[2].metric("PM10", f"{pm10:.1f} µg/m³" if pm10 is not None else "—")


def render_headlines(selected_feeds: list[str]) -> None:
    st.subheader("Headlines")
    if not selected_feeds:
        st.caption("Choose at least one feed in the sidebar.")
        return
    for name in selected_feeds:
        st.markdown(f"**{name}**")
        try:
            headlines = fetch_headlines(FEEDS[name])
        except requests.RequestException as error:
            st.error(f"Could not load {name}: {error}")
            continue
        if not headlines:
            st.caption("No headlines returned.")
            continue
        for item in headlines:
            if item["link"]:
                st.markdown(f"- [{item['title']}]({item['link']})")
            else:
                st.markdown(f"- {item['title']}")
            if item["published"]:
                st.caption(item["published"])


def main() -> None:
    st.set_page_config(page_title="Daily briefing", page_icon=":newspaper:", layout="wide")
    prefs = load_prefs()

    with st.sidebar:
        st.header("Settings")
        city = st.text_input("City", value=prefs["city"]).strip()
        units = st.radio(
            "Units",
            options=["fahrenheit", "celsius"],
            index=0 if prefs["units"] == "fahrenheit" else 1,
            format_func=lambda value: "Fahrenheit" if value == "fahrenheit" else "Celsius",
        )
        show_air_quality = st.checkbox("Show air quality", value=bool(prefs["show_air_quality"]))
        feeds = st.multiselect("Feeds", options=list(FEEDS), default=prefs["feeds"])

    updated = {
        "city": city or prefs["city"],
        "units": units,
        "show_air_quality": show_air_quality,
        "feeds": feeds,
    }
    if updated != prefs:
        save_prefs(updated)

    st.title("Daily briefing")
    st.caption("Weather from Open-Meteo and headlines from the feeds you pick.")

    if not city:
        st.info("Enter a city in the sidebar.")
        return

    try:
        place = geocode(city)
    except requests.RequestException as error:
        st.error(f"Could not look up that city: {error}")
        return

    if place is None:
        st.warning(f"No match for “{city}”. Try a more specific name.")
        return

    try:
        render_weather(place, units)
    except requests.RequestException as error:
        st.error(f"Could not load the forecast: {error}")

    if show_air_quality:
        try:
            render_air_quality(place)
        except requests.RequestException as error:
            st.error(f"Could not load air quality: {error}")

    render_headlines(feeds)


if __name__ == "__main__":
    main()
