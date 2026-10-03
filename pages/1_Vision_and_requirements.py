import streamlit as st

import app

app.prepare_page("Vision and requirements")

st.title("Vision and requirements")
st.page_link("briefing.py", label="Back to the briefing")

st.header("Vision")
st.write(
    "Daily briefing is a personal morning page. You open it on your own computer, "
    "see the weather and air quality for a city you care about, and scan a few headlines. "
    "It does not ask you to create an account or supply an API key."
)

st.header("Who it is for")
st.write("One person, running the app locally. Settings stay on that machine.")

st.header("Requirements")
st.markdown(
    """
1. Look up a city by name and show the matching place.
2. Show the current temperature, how it feels, conditions, and wind, plus a five-day forecast with high, low, and chance of rain.
3. Let the reader choose Fahrenheit or Celsius. Wind uses miles per hour with Fahrenheit and kilometers per hour with Celsius.
4. Show US AQI, PM2.5, and PM10, and let the reader hide that section.
5. Show headlines from the feeds the reader selects: BBC News, NPR News, and Ars Technica. Each item has a title, a link when one exists, and a published time when one exists.
6. Remember the city, units, air-quality choice, and selected feeds in a local file. If that file is missing, unreadable, or not a settings object, open with the defaults instead of stopping.
7. When a city cannot be found, or a weather, air-quality, or headline request fails, say so on the page and still show whatever else loaded.
8. Reuse recent weather, air-quality, and headline responses so repeat views do not call those services every time.
9. Show a city-and-weather illustration behind the page, with a matching picture as the browser icon and the sidebar logo. Keep the briefing itself on a light panel so it stays readable.
10. Link from the briefing to this summary and to a summary of the conceptual, logical, and physical architecture. The architecture summary shows a diagram for each of those three views.
11. Show the latest GitHub release version and its notes, and let the reader open an older release. Each update that lands on `main` creates the next release.
"""
)

st.header("Out of scope")
st.write(
    "Watchlists, meal planning, reading logs, and trip cost estimates are not part of this app."
)
