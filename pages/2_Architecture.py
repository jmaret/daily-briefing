import re
from pathlib import Path

import streamlit as st

import app

ARCHITECTURE_DOC = Path(__file__).resolve().parents[1] / "docs" / "architecture.md"


def architecture_diagrams() -> list[str]:
    text = ARCHITECTURE_DOC.read_text(encoding="utf-8")
    return re.findall(r"```mermaid\n(.*?)```", text, flags=re.DOTALL)


app.prepare_page("Architecture")

st.title("Architecture")
st.page_link("briefing.py", label="Back to the briefing")

conceptual, logical, physical = architecture_diagrams()

st.header("Conceptual")
st.write(
    "The reader has a briefing, plus two short explanations: this architecture "
    "and the vision and requirements. Four ideas sit behind the briefing: a place, "
    "the weather there, the air there, and a short list of headlines. Preferences "
    "remember how the reader wants that page set up."
)
st.mermaid_chart(conceptual)

st.header("Logical")
st.write(
    "`app.py` registers the pages and runs the one you opened. The briefing lives in "
    "`briefing.py`. Its sidebar reads and writes preferences. "
    "The main column asks for a place, then weather, then air quality when it is "
    "enabled, then headlines. Each outside call can fail on its own. A failed city "
    "lookup stops the rest of the page. A failed forecast, air-quality call, or feed "
    "does not hide the other sections. If a feed answers 403, the app reads that same feed through `api.rss2json.com`. The briefing also shows the latest GitHub release and its notes, and the reader can open an older release from the same list. The two explanation pages are "
    "`pages/1_Vision_and_requirements.py` and `pages/2_Architecture.py`. The briefing links to both."
)
st.mermaid_chart(logical)
st.markdown(
    """
| Concern | What it does | How long a result is reused |
| --- | --- | --- |
| Preferences | Load and save city, units, air-quality toggle, and feeds | Until the reader changes them |
| Place | Turn a city name into a location | 30 minutes |
| Weather | Current conditions and five daily rows | 15 minutes |
| Air quality | US AQI, PM2.5, and PM10 | 15 minutes |
| Headlines | Up to five items per selected feed | 15 minutes |
| Releases | Latest version and its notes, with older releases available | 15 minutes |
"""
)
st.write(
    "Saved feeds that are no longer in the catalog are dropped. An unrecognized unit "
    "falls back to Fahrenheit. A missing, unreadable, or wrongly shaped preferences "
    "file falls back to New York, Fahrenheit, air quality on, and BBC News plus NPR News. "
    "A file that is JSON but not an object, or a setting that is not the expected type, "
    "is treated the same way for that setting."
)

st.header("Physical")
st.write(
    "The app is one Python process, started with `streamlit run app.py` from a local "
    "virtual environment (`.venv`). The page is served at `http://localhost:8501`."
)
st.mermaid_chart(physical)
st.markdown(
    """
| Piece | Where it lives |
| --- | --- |
| Entrypoint | `app.py` |
| Briefing | `briefing.py` |
| Vision summary | `pages/1_Vision_and_requirements.py` |
| Architecture summary | `pages/2_Architecture.py` |
| Artwork | `assets/` city, icon, and logo pictures |
| Theme | `.streamlit/config.toml` |
| Dependencies | `requirements.txt`, installed into `.venv` |
| Preferences | `preferences.json` beside `app.py`, unless `DAILY_BRIEFING_PREFS` points somewhere else |
| Tests | `tests/`, run with `.venv/bin/python -m pytest` |
| Place and weather | `geocoding-api.open-meteo.com`, `api.open-meteo.com` |
| Air quality | `air-quality-api.open-meteo.com` |
| Headlines | BBC, NPR, and Ars Technica RSS URLs in `FEEDS`. A 403 is retried through `api.rss2json.com` |
| Releases | GitHub Releases for `jmaret/daily-briefing`, created by `.github/workflows/release.yml` on each push to `main` |
"""
)
st.write(
    "Tests mock those HTTP calls. They do not need a network connection or a running Streamlit server."
)
