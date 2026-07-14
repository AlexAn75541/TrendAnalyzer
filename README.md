# PTT Forum Trend Analyzer & Discussion Mining System

## Files

- `ptt_analyzer.py`: Main system. Crawler classes, database, text processing, trend analysis, charts.
- `web_dashboard.py`: Flask web server. Reads from the database and serves the dashboard.
- `templates/dashboard.html`: Browser dashboard. Charts, search, post table.

## Setup

Install dependencies:

```
pip install requests beautifulsoup4 pandas matplotlib flask
```

## Step 1: Run the main pipeline

```
python3 ptt_analyzer.py
```

This generates `ptt_data.db` in the same folder. It also exports `export.json`, `export.csv`, and five PNG charts (heatmap, keyword trend, sentiment, top posters, board comparison).

By default the pipeline uses `generate_sample_data()` instead of a live crawl. PTT's HTML structure and network access can change, so sample data lets you test the full system without depending on the live site.

To try a live crawl, open `ptt_analyzer.py` and change the last line:

```python
run_pipeline(use_sample_data=False)
```

Live crawling needs outbound network access to ptt.cc. If you're testing in a sandboxed environment without internet access, keep `use_sample_data=True`.

## Step 2: Start the web dashboard

```
python3 web_dashboard.py
```

Open your browser to:

```
http://127.0.0.1:5000
```

You'll see total post and comment counts, average sentiment, four charts (sentiment distribution, board comparison, top keywords, top posters), and a searchable post table.

## Step 3: Test the search

Type a keyword in the search box (try "AI" or "Python") and press Search. The table updates with matching posts. You can also filter by board using the dropdown.

## Step 4: Test the API directly

With the server running, open these in your browser or use curl:

```
http://127.0.0.1:5000/api/summary
http://127.0.0.1:5000/api/posts?limit=10
http://127.0.0.1:5000/api/search?q=Python
http://127.0.0.1:5000/api/board-comparison
http://127.0.0.1:5000/api/keywords?limit=10
http://127.0.0.1:5000/api/top-posters
http://127.0.0.1:5000/api/sentiment-distribution
```

Each returns JSON pulled live from `ptt_data.db`.

## Troubleshooting

If the dashboard shows "Database not found," run `ptt_analyzer.py` first. The dashboard reads `ptt_data.db` from the same folder it sits in.

If port 5000 is already in use, edit the last line of `web_dashboard.py`:

```python
app.run(debug=True, port=5001)
```

## What maps to the project proposal

- OOP classes: `PTTCrawler`, `Post`, `Comment`, `Board`
- BeautifulSoup parsing: `parse_post_listing`, `parse_post_content`
- Pagination and over-18 handling: `get_previous_page_url`, session cookie in `PTTCrawler.__init__`
- Decorators: `rate_limit`, `cache_result`
- Multi-threading: `crawl_boards_multithreaded`
- Map/filter/lambda: `extract_keywords_from_posts`, `calculate_sentiment_for_posts`
- SQLite with full-text search: `Database` class, FTS5 virtual table
- JSON/CSV export: `Database.export_json`, `Database.export_csv`
- Pandas trend analysis: `TrendAnalyzer` class
- MatPlotLib visualizations: `Visualizer` class
- Web dashboard: `web_dashboard.py` plus `templates/dashboard.html`
