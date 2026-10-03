import requests
import streamlit as st

import app

app.prepare_page("Daily briefing")
prefs = app.load_prefs()

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
    feeds = st.multiselect("Feeds", options=list(app.FEEDS), default=prefs["feeds"])

updated = {
    "city": city or prefs["city"],
    "units": units,
    "show_air_quality": show_air_quality,
    "feeds": feeds,
}
if updated != prefs:
    app.save_prefs(updated)

st.title("Daily briefing")
st.caption("Weather from Open-Meteo and headlines from the feeds you pick.")

if city:
    try:
        place = app.geocode(city)
    except requests.RequestException as error:
        st.error(f"Could not look up that city: {error}")
    else:
        if place is None:
            st.warning(f"No match for “{city}”. Try a more specific name.")
        else:
            try:
                app.render_weather(place, units)
            except requests.RequestException as error:
                st.error(f"Could not load the forecast: {error}")

            if show_air_quality:
                try:
                    app.render_air_quality(place)
                except requests.RequestException as error:
                    st.error(f"Could not load air quality: {error}")

            app.render_headlines(feeds)
else:
    st.info("Enter a city in the sidebar.")
