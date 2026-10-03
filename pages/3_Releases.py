import streamlit as st

import app

app.prepare_page("Releases")

st.title("Releases")
app.render_releases()
