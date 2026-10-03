import streamlit as st

import app

app.prepare_page("CI/CD")

st.title("CI/CD")
app.render_cicd_metrics()
st.write(
    "Each update that lands on main creates the next GitHub release. "
    "A deployed copy of this app rebuilds from that same update."
)

st.header("When it runs")
st.write(
    "A change reaches main when its pull request is merged. That push starts the "
    "Release workflow in `.github/workflows/release.yml`. A branch that has not "
    "been merged does not start it. Tests run locally with pytest before the merge."
)

st.header("The release job")
st.markdown(
    """
1. The job checks whether this commit already has a release. If it does, the job stops and leaves that release in place.
2. Otherwise it reads the highest `v` number and creates the next one, aimed at this commit. GitHub writes the notes from the commits since the previous release.
3. If that tag was just taken, the job tries the following number, up to five times.
4. Overlapping pushes wait in one line, so two jobs do not claim the same number.
"""
)
st.mermaid_chart(
    """
flowchart TD
  merge[Merge to main] --> workflow[Release workflow]
  workflow --> check{Release already exists for this commit?}
  check -->|Yes| keep[Keep the existing release]
  check -->|No| next[Create the next version and its notes]
  merge --> deploy[Deployed app rebuilds from main]
  next --> releases[Releases page]
"""
)

st.header("What you see")
st.write(
    "The numbers above use the newest release GitHub has published. "
    "The Releases page shows that version and the notes for the one you pick. "
    "A new release shows up within a minute. The first release covers the history "
    "up to that commit. Later releases cover only what changed since the one before."
)

st.header("The deployed app")
st.write(
    "When this app is deployed from main on Streamlit Community Cloud, the same "
    "push rebuilds the running app. The briefing and the sidebar pages then match "
    "the commit that was just released. A private repository still needs "
    "`GITHUB_TOKEN` in the app secrets before the Releases page can read those notes."
)
