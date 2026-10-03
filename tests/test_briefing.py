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
    if url.endswith("/releases") and "api.github.com/repos/" in url:
        return FakeResponse(
            [
                {
                    "tag_name": "v2",
                    "name": "v2",
                    "body": "NPR backup",
                    "published_at": "2026-10-02T23:00:00Z",
                    "html_url": "https://github.com/jmaret/daily-briefing/releases/tag/v2",
                },
                {
                    "tag_name": "v1",
                    "name": "v1",
                    "body": "First look",
                    "published_at": "2026-10-01T23:00:00Z",
                    "html_url": "https://github.com/jmaret/daily-briefing/releases/tag/v1",
                },
            ]
        )
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


def test_briefing_page_uses_saved_defaults(monkeypatch, prefs_path):
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
    assert page.selectbox == []
    assert "Vision and requirements" not in _link_labels(page)
    assert "Architecture" not in _link_labels(page)
    assert "Releases" not in _link_labels(page)


def _nodes(page: AppTest) -> list:
    found = []

    def walk(node) -> None:
        found.append(node)
        children = getattr(node, "children", None)
        if isinstance(children, dict):
            for child in children.values():
                walk(child)

    walk(page._tree)
    return found


def _link_labels(page: AppTest) -> list[str]:
    return [
        node.label
        for node in _nodes(page)
        if type(node).__name__ == "UnknownElement" and getattr(node, "label", None)
    ]


def test_sidebar_opens_the_summaries_and_releases(monkeypatch, prefs_path):
    monkeypatch.setattr(requests, "get", fake_get)

    page = AppTest.from_file(str(Path(app.__file__)))
    page.run(timeout=30)
    page.switch_page("pages/1_Vision_and_requirements.py").run(timeout=30)
    assert page.title[0].value == "Vision and requirements"

    page.switch_page("pages/2_Architecture.py").run(timeout=30)
    assert page.title[0].value == "Architecture"

    page.switch_page("pages/3_Releases.py").run(timeout=30)
    assert not page.exception
    assert page.title[0].value == "Releases"
    assert any(item.value == "Release v2" for item in page.caption)
    assert page.selectbox[0].value == "v2"
    assert page.selectbox[0].options == ["v2", "v1"]
    assert any("NPR backup" in item.value for item in page.markdown)

    page.selectbox[0].set_value("v1").run()
    assert not page.exception
    assert any("First look" in item.value for item in page.markdown)


def test_vision_page_summarizes_requirements(monkeypatch, prefs_path):
    monkeypatch.setattr(requests, "get", fake_get)

    page = AppTest.from_file(str(Path(app.__file__)))
    page.run(timeout=30)
    page.switch_page("pages/1_Vision_and_requirements.py").run(timeout=30)

    assert not page.exception
    assert page.title[0].value == "Vision and requirements"
    headers = [item.value for item in page.header]
    assert headers == ["Vision", "Who it is for", "Requirements", "Out of scope"]


def test_architecture_page_covers_three_views(monkeypatch, prefs_path):
    monkeypatch.setattr(requests, "get", fake_get)

    page = AppTest.from_file(str(Path(app.__file__)))
    page.run(timeout=30)
    page.switch_page("pages/2_Architecture.py").run(timeout=30)

    assert not page.exception
    assert page.title[0].value == "Architecture"
    headers = [item.value for item in page.header]
    assert headers == ["Conceptual", "Logical", "Physical"]
    diagrams = [item.value for item in page.markdown if "flowchart TD" in item.value]
    assert len(diagrams) == 3


def test_forbidden_feed_is_read_through_the_backup(monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        if url == app.FEEDS["NPR News"]:
            return FakeResponse(status_code=403)
        if url == app.RSS2JSON_URL:
            return FakeResponse(
                payload={
                    "status": "ok",
                    "items": [
                        {
                            "title": "From the backup",
                            "link": "https://www.npr.org/story",
                            "pubDate": "Fri, 02 Oct 2026 12:00:00 GMT",
                        }
                    ],
                }
            )
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(requests, "get", get)
    app.fetch_headlines.clear()
    headlines = app.fetch_headlines(app.FEEDS["NPR News"])

    assert calls == [app.FEEDS["NPR News"], app.RSS2JSON_URL]
    assert headlines == [
        {
            "title": "From the backup",
            "link": "https://www.npr.org/story",
            "published": "Fri, 02 Oct 2026 12:00:00 GMT",
        }
    ]


def test_unknown_city_shows_a_warning(monkeypatch, prefs_path):
    monkeypatch.setattr(requests, "get", fake_get)

    page = AppTest.from_file(str(Path(app.__file__)))
    page.run(timeout=30)
    page.sidebar.text_input[0].set_value("Nowhereville").run(timeout=30)

    assert not page.exception
    assert page.warning[0].value.startswith("No match for")
    assert page.metric == []
