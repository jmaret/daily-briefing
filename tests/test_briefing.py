import json
from pathlib import Path

import pytest
import requests
from streamlit.testing.v1 import AppTest

import app

RSS = b"""<?xml version="1.0"?>
<rss><channel>
  <item>
    <title>Sample headline</title>
    <link>https://example.com/story</link>
    <pubDate>Fri, 02 Oct 2026 12:00:00 GMT</pubDate>
  </item>
</channel></rss>
"""


class FakeResponse:
    def __init__(self, payload=None, content=b"", status_code=200):
        self._payload = payload if payload is not None else {}
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._payload


def fake_get(url, **kwargs):
    params = kwargs.get("params") or {}
    if "geocoding-api" in url:
        if params.get("name") == "Nowhereville":
            return FakeResponse({"results": []})
        return FakeResponse(
            {
                "results": [
                    {
                        "name": "New York",
                        "admin1": "New York",
                        "country": "United States",
                        "latitude": 40.71,
                        "longitude": -74.01,
                    }
                ]
            }
        )
    if "air-quality-api" in url:
        return FakeResponse({"current": {"us_aqi": 42, "pm2_5": 8.2, "pm10": 12.0}})
    if "api.open-meteo.com" in url:
        return FakeResponse(
            {
                "current": {
                    "temperature_2m": 72.2,
                    "apparent_temperature": 70.4,
                    "weather_code": 1,
                    "wind_speed_10m": 8.2,
                },
                "daily": {
                    "time": ["2026-10-02"],
                    "weather_code": [3],
                    "temperature_2m_max": [75.2],
                    "temperature_2m_min": [60.1],
                    "precipitation_probability_max": [20],
                },
            }
        )
    if url in app.FEEDS.values():
        return FakeResponse(content=RSS)
    raise AssertionError(f"unexpected URL {url}")


@pytest.fixture
def prefs_path(monkeypatch, tmp_path):
    path = tmp_path / "preferences.json"
    monkeypatch.setattr(app, "PREFS_PATH", path)
    return path


def test_labels_cover_known_and_missing_values():
    assert app.weather_label(None) == "Unknown"
    assert app.weather_label(1) == "Mainly clear"
    assert app.weather_label(123) == "Code 123"
    assert app.aqi_label(None) == "Unavailable"
    assert app.aqi_label(42) == "42 · Good"
    assert app.aqi_label(64.2) == "64 · Moderate"
    assert app.place_name(
        {"name": "New York", "admin1": "New York", "country": "United States"}
    ) == "New York, New York, United States"


def test_preferences_round_trip_and_fallbacks(prefs_path):
    assert app.load_prefs()["city"] == "New York"

    app.save_prefs(
        {
            "city": "Paris",
            "units": "celsius",
            "show_air_quality": False,
            "feeds": ["BBC News", "Not a feed"],
        }
    )
    loaded = app.load_prefs()
    assert loaded["city"] == "Paris"
    assert loaded["feeds"] == ["BBC News"]
    assert loaded["show_air_quality"] is False

    prefs_path.write_text("{", encoding="utf-8")
    assert app.load_prefs()["city"] == "New York"

    prefs_path.write_text(
        json.dumps({"city": "Berlin", "units": "kelvin", "feeds": ["NPR News"]}),
        encoding="utf-8",
    )
    repaired = app.load_prefs()
    assert repaired["city"] == "Berlin"
    assert repaired["units"] == "fahrenheit"
    assert repaired["show_air_quality"] is True

    prefs_path.write_text("null", encoding="utf-8")
    assert app.load_prefs() == app.DEFAULT_PREFS

    prefs_path.write_text(
        json.dumps({"city": "Paris", "feeds": None, "show_air_quality": "yes"}),
        encoding="utf-8",
    )
    partial = app.load_prefs()
    assert partial["city"] == "Paris"
    assert partial["feeds"] == app.DEFAULT_PREFS["feeds"]
    assert partial["show_air_quality"] is True


def test_briefing_page_uses_saved_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("DAILY_BRIEFING_PREFS", str(tmp_path / "preferences.json"))
    monkeypatch.setattr(requests, "get", fake_get)

    page = AppTest.from_file(str(Path(app.__file__)))
    page.run(timeout=30)

    assert not page.exception
    assert page.title[0].value == "Daily briefing"
    assert page.subheader[0].value == "New York, New York, United States"
    metrics = {item.label: item.value for item in page.metric}
    assert metrics["Temperature"] == "72°F"
    assert metrics["Conditions"] == "Mainly clear"
    assert metrics["Wind"] == "8 mph"
    assert metrics["US AQI"] == "42 · Good"
    assert any("Sample headline" in item.value for item in page.markdown)


def test_unknown_city_shows_a_warning(monkeypatch, tmp_path):
    monkeypatch.setenv("DAILY_BRIEFING_PREFS", str(tmp_path / "preferences.json"))
    monkeypatch.setattr(requests, "get", fake_get)

    page = AppTest.from_file(str(Path(app.__file__)))
    page.run(timeout=30)
    page.sidebar.text_input[0].set_value("Nowhereville").run(timeout=30)

    assert not page.exception
    assert page.warning[0].value.startswith("No match for")
    assert page.metric == []
