# Daily briefing: vision and requirements

## Vision

Daily briefing is a personal morning page. You open it on your own computer, see the weather and air quality for a city you care about, and scan a few headlines. It does not ask you to create an account or supply an API key.

## Who it is for

One person, running the app locally. Settings stay on that machine.

## Requirements

1. Look up a city by name and show the matching place.
2. Show the current temperature, how it feels, conditions, and wind, plus a five-day forecast with high, low, and chance of rain.
3. Let the reader choose Fahrenheit or Celsius. Wind uses miles per hour with Fahrenheit and kilometers per hour with Celsius.
4. Show US AQI, PM2.5, and PM10, and let the reader hide that section.
5. Show headlines from the feeds the reader selects: BBC News, NPR News, and Ars Technica. Each item has a title, a link when one exists, and a published time when one exists.
6. Remember the city, units, air-quality choice, and selected feeds in a local file.
7. When a city cannot be found, or a weather, air-quality, or headline request fails, say so on the page and still show whatever else loaded.
8. Reuse recent weather, air-quality, and headline responses so repeat views do not call those services every time.

## Out of scope

Watchlists, meal planning, reading logs, and trip cost estimates are not part of this app.
