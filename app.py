#!/usr/bin/env python3
"""
Tiny Flask app: pick a date in the browser, see music releases
from that month/day across a range of years using the MusicBrainz API.
"""

import time
from datetime import datetime

import requests
from flask import Flask, request, render_template_string

API_BASE = "https://musicbrainz.org/ws/2/release"
# MusicBrainz asks for a descriptive User-Agent with contact
USER_AGENT = "EricMusicDateFinder/1.0 (eric.s.jaffe@gmail.com)"

# Max number of years we’ll process in a single request
MAX_YEARS_PER_REQUEST = 25

app = Flask(__name__)

HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>On This Day in Music</title>
  <style>
    body { font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           margin: 2rem; background: #0f172a; color: #e5e7eb; }
    h1 { margin-bottom: 0.5rem; }
    p { color: #9ca3af; }
    form { margin: 1.5rem 0; padding: 1rem; background: #111827; border-radius: 0.5rem; }
    label { display: inline-block; margin-right: 0.5rem; }
    input[type="date"], input[type="number"] {
      padding: 0.3rem 0.4rem; border-radius: 0.25rem; border: 1px solid #4b5563;
      background: #020617; color: #e5e7eb;
    }
    input[type="submit"] {
      padding: 0.4rem 0.8rem;
      border: none;
      border-radius: 0.25rem;
      background: #22c55e;
      color: #022c22;
      font-weight: 600;
      cursor: pointer;
      margin-left: 0.5rem;
    }
    input[type="submit"]:hover {
      background: #16a34a;
    }
    table {
      border-collapse: collapse;
      width: 100%;
      margin-top: 1.5rem;
      background: #020617;
      border-radius: 0.5rem;
      overflow: hidden;
    }
    th, td {
      padding: 0.5rem 0.75rem;
      border-bottom: 1px solid #1f2937;
      font-size: 0.9rem;
    }
    th {
      text-align: left;
      background: #111827;
      color: #e5e7eb;
    }
    tr:nth-child(even) td {
      background: #020617;
    }
    tr:nth-child(odd) td {
      background: #030712;
    }
    a { color: #38bdf8; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .error { color: #f97373; margin-top: 0.5rem; }
    .summary { margin-top: 1rem; font-weight: 500; }
    .chip {
      display: inline-block;
      padding: 0.1rem 0.4rem;
      border-radius: 999px;
      font-size: 0.75rem;
      background: #1d4ed8;
      color: #e5e7eb;
      margin-left: 0.5rem;
    }
  </style>
</head>
<body>
  <h1>On This Day in Music</h1>
  <p>Pick a date and a year range. We&apos;ll ask MusicBrainz what releases came out on that month/day across those years.</p>

  <form method="post">
    <div style="margin-bottom: 0.5rem;">
      <label for="date">Date:</label>
      <input type="date" id="date" name="date"
             value="{{ date_value or '' }}" required>
    </div>
    <div style="margin-bottom: 0.5rem;">
      <label for="start_year">Start year:</label>
      <input type="number" id="start_year" name="start_year"
             value="{{ start_year or '' }}" min="1900" max="{{ current_year }}">
      <label for="end_year" style="margin-left:1rem;">End year:</label>
      <input type="number" id="end_year" name="end_year"
             value="{{ end_year or '' }}" min="1900" max="{{ current_year }}">
      <span class="chip">Tip: keep ranges small (e.g. 1990–2025)</span>
    </div>
    <input type="submit" value="Find releases">
    {% if error %}
      <div class="error">{{ error }}</div>
    {% endif %}
  </form>

  {% if results is not none %}
    <div class="summary">
      Found {{ results|length }} releases for {{ pretty_date }} across {{ start_year }}–{{ end_year }}.
    </div>
    {% if results %}
      <table>
        <thead>
          <tr>
            <th>Year</th>
            <th>Artist</th>
            <th>Title</th>
            <th>Date</th>
            <th>Link</th>
          </tr>
        </thead>
        <tbody>
          {% for r in results %}
            <tr>
              <td>{{ r.year }}</td>
              <td>{{ r.artist or 'Unknown artist' }}</td>
              <td>{{ r.title }}</td>
              <td>{{ r.date or 'N/A' }}</td>
              <td>
                {% if r.url %}
                  <a href="{{ r.url }}" target="_blank">View</a>
                {% else %}
                  &mdash;
                {% endif %}
              </td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    {% endif %}
  {% endif %}
</body>
</html>
"""


def search_releases_for_date(year: int, mm_dd: str, limit: int = 50):
    """
    Call MusicBrainz search:
      /ws/2/release/?query=date:YYYY-MM-DD&fmt=json&limit=...
    Returns list of releases (dicts).
    """
    ymd = f"{year}-{mm_dd}"  # e.g. 2019-11-22
    params = {
        "query": f"date:{ymd}",
        "fmt": "json",
        "limit": str(limit),
    }
    headers = {
        "User-Agent": USER_AGENT,
    }

    resp = requests.get(API_BASE, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("releases", [])


@app.route("/", methods=["GET", "POST"])
def index():
    error = None
    results = None
    current_year = datetime.now().year

    # Defaults for first load / GET
    date_value = datetime.now().strftime("%Y-%m-%d")
    start_year = 1990
    end_year = current_year
    pretty_date = ""

    if request.method == "POST":
        # Get form values
        date_value = request.form.get("date", "").strip()
        start_str = request.form.get("start_year", "").strip()
        end_str = request.form.get("end_year", "").strip()

        # Parse date
        try:
            _dt = datetime.strptime(date_value, "%Y-%m-%d")
            mm_dd = date_value[5:]  # "YYYY-MM-DD" -> "MM-DD"
            pretty_date = _dt.strftime("%B %d")  # e.g. "November 22"
        except ValueError:
            error = "Invalid date. Please use the date picker."
            mm_dd = None

        # Parse years with defaults
        try:
            start_year = int(start_str) if start_str else 1990
            end_year = int(end_str) if end_str else current_year
            if end_year < start_year:
                start_year, end_year = end_year, start_year
        except ValueError:
            error = (error + " | " if error else "") + "Start/end year must be numbers."
            start_year = 1990
            end_year = current_year

        # Clamp the range so we don't time out
        if not error and mm_dd:
            year_span = end_year - start_year + 1
            if year_span > MAX_YEARS_PER_REQUEST:
                original_end = end_year
                end_year = start_year + MAX_YEARS_PER_REQUEST - 1
                if end_year > current_year:
                    end_year = current_year
                error = (error + " | " if error else "") + (
                    f"Year range too large ({year_span} years). "
                    f"Showing only {start_year}–{end_year}. "
                    f"Try smaller chunks like 1990–2010, then 2011–{current_year}."
                )

            results = []
            for year in range(start_year, end_year + 1):
                try:
                    releases = search_releases_for_date(year, mm_dd, limit=50)
                except requests.HTTPError as e:
                    error = f"HTTP error for year {year}: {e}"
                    break
                except Exception as e:
                    error = f"Error for year {year}: {e}"
                    break

                for r in releases:
                    title = r.get("title")
                    date = r.get("date")
                    artist = None
                    ac = r.get("artist-credit") or []
                    if ac and isinstance(ac, list) and "name" in ac[0]:
                        artist = ac[0]["name"]
                    mbid = r.get("id")
                    url = f"https://musicbrainz.org/release/{mbid}" if mbid else None

                    # use a tiny object so template can do r.year, r.title, etc.
                    results.append(
                        type("Release", (object,), {
                            "year": year,
                            "title": title,
                            "artist": artist,
                            "date": date,
                            "url": url,
                        })
                    )

                # Be polite with MusicBrainz but not too slow
                time.sleep(0.1)

            # Sort nicely
            if results:
                results.sort(key=lambda x: (x.year, x.artist or "", x.title or ""))

    return render_template_string(
        HTML_TEMPLATE,
        error=error,
        results=results,
        date_value=date_value,
        start_year=start_year,
        end_year=end_year,
        pretty_date=pretty_date or "",
        current_year=current_year,
    )


if __name__ == "__main__":
    # Local dev only; Render will use gunicorn app:app
    app.run(host="0.0.0.0", port=5000, debug=True)
