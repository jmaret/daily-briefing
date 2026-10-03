from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import feedparser
import requests
import streamlit as st

PREFS_PATH = Path(
    os.environ.get("DAILY_BRIEFING_PREFS", Path(__file__).with_name("preferences.json"))
)
ASSETS_DIR = Path(__file__).with_name("assets")
BACKGROUND_PATH = ASSETS_DIR / "city-weather-background.jpg"
ICON_PATH = ASSETS_DIR / "city-weather-icon.jpg"
LOGO_PATH = ASSETS_DIR / "city-weather-logo.jpg"

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
    if not isinstance(saved, dict):
        return dict(DEFAULT_PREFS)

    prefs = dict(DEFAULT_PREFS)
    city = saved.get("city")
    if isinstance(city, str) and city.strip():
        prefs["city"] = city
    if saved.get("units") in ("celsius", "fahrenheit"):
        prefs["units"] = saved["units"]
    if isinstance(saved.get("show_air_quality"), bool):
        prefs["show_air_quality"] = saved["show_air_quality"]
    feeds = saved.get("feeds")
    if isinstance(feeds, list):
        prefs["feeds"] = [name for name in feeds if isinstance(name, str) and name in FEEDS]
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


FEED_HEADERS = {"User-Agent": "daily-briefing/0.1"}
RSS2JSON_URL = "https://api.rss2json.com/v1/api.json"


def _headline(title: str | None, link: str | None, published: str | None) -> dict:
    return {
        "title": title or "Untitled",
        "link": link or "",
        "published": published or "",
    }


def _headlines_via_rss2json(url: str, limit: int) -> list[dict]:
    response = requests.get(
        RSS2JSON_URL,
        params={"rss_url": url},
        timeout=15,
        headers=FEED_HEADERS,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "ok":
        raise requests.HTTPError(payload.get("message") or "backup feed reader failed")
    return [
        _headline(entry.get("title"), entry.get("link"), entry.get("pubDate"))
        for entry in (payload.get("items") or [])[:limit]
    ]


@st.cache_data(ttl=60 * 15, show_spinner=False)
def fetch_headlines(url: str, limit: int = 5) -> list[dict]:
    response = requests.get(url, timeout=15, headers=FEED_HEADERS)
    if response.status_code == 403:
        return _headlines_via_rss2json(url, limit)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    return [
        _headline(entry.get("title"), entry.get("link"), entry.get("published"))
        for entry in parsed.entries[:limit]
    ]


GITHUB_REPO = os.environ.get("DAILY_BRIEFING_REPO", "jmaret/daily-briefing")


def github_token() -> str:
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    try:
        value = st.secrets["GITHUB_TOKEN"]
    except Exception:
        return ""
    return value.strip() if isinstance(value, str) else ""


@st.cache_data(ttl=60 * 15, show_spinner=False)
def fetch_releases(token: str) -> list[dict]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "daily-briefing/0.1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/releases",
        params={"per_page": 100},
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []
    releases = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        tag = item.get("tag_name")
        if not isinstance(tag, str) or not tag.strip():
            continue
        name = item.get("name")
        body = item.get("body")
        published = item.get("published_at")
        url = item.get("html_url")
        releases.append(
            {
                "tag": tag,
                "name": name if isinstance(name, str) and name.strip() else tag,
                "body": body if isinstance(body, str) else "",
                "published": published if isinstance(published, str) else "",
                "url": url if isinstance(url, str) else "",
            }
        )
    return releases


def render_releases() -> None:
    try:
        releases = fetch_releases(github_token())
    except requests.HTTPError as error:
        status = getattr(error.response, "status_code", None)
        if status in (401, 403, 404):
            st.caption(
                "Could not load releases. A private repository needs GITHUB_TOKEN in the environment or in Streamlit secrets."
            )
            return
        st.caption(f"Could not load releases: {error}")
        return
    except requests.RequestException as error:
        st.caption(f"Could not load releases: {error}")
        return
    if not releases:
        st.caption("No GitHub releases yet.")
        return

    latest = releases[0]
    st.caption(f"Release {latest['tag']}")
    tags = [item["tag"] for item in releases]
    choice = st.selectbox("Release", tags, index=0)
    selected = next(item for item in releases if item["tag"] == choice)
    if selected["published"]:
        st.caption(selected["published"])
    if selected["url"]:
        st.markdown(f"[View on GitHub]({selected['url']})")
    st.markdown(selected["body"] or "No notes for this release.")


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


def apply_artwork() -> None:
    encoded = base64.b64encode(BACKGROUND_PATH.read_bytes()).decode()
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpeg;base64,{encoded}");
            background-size: cover;
            background-position: center 42%;
            background-attachment: fixed;
        }}
        [data-testid="stHeader"] {{
            background: transparent;
        }}
        [data-testid="stSidebar"] {{
            background-color: rgba(246, 241, 231, 0.9);
        }}
        [data-testid="stSidebarHeader"] {{
            height: auto;
        }}
        img[data-testid="stSidebarLogo"] {{
            height: 168px;
            width: auto;
        }}
        [data-testid="stMain"] .block-container {{
            max-width: 1100px;
            background: rgba(255, 250, 244, 0.72);
            border-radius: 18px;
            padding: 1.5rem 2rem 2.5rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def prepare_page(title: str) -> None:
    st.set_page_config(page_title=title, page_icon=str(ICON_PATH), layout="wide")
    st.logo(str(LOGO_PATH), icon_image=str(ICON_PATH), size="large")
    apply_artwork()


def run() -> None:
    briefing = st.Page("briefing.py", title="Daily briefing", default=True)
    vision = st.Page(
        "pages/1_Vision_and_requirements.py",
        title="Vision and requirements",
        url_path="vision",
    )
    architecture = st.Page(
        "pages/2_Architecture.py",
        title="Architecture",
        url_path="architecture",
    )
    releases = st.Page("pages/3_Releases.py", title="Releases", url_path="releases")
    st.navigation([briefing, vision, architecture, releases]).run()


if __name__ == "__main__":
    run()
