# D3 Ohio XC — Program Development (2015–2024)

An interactive, staged data pipeline tracking how **NCAA Division III Ohio
cross country programs** have developed over the last 10 seasons, ending in a
**Streamlit + Plotly dashboard**.

Programs are framed by **NCAA D3 Region VI (Great Lakes)** — the regional
championship Ohio D3 teams run to qualify for nationals — across the **OAC**,
**NCAC**, **HCAC**, and **UAA** conferences.

## What "development" means here

- **Athlete progression** — season-best times normalized to pace, tracked
  year-over-year; plus best-effort **high-school → college** improvement.
- **Most improved** — athletes (debut season → career best) and teams
  (regional placement gained).
- **Conference** — placement trend and conference titles (wins).
- **Great Lakes Regional** and **NCAA Championships** — placement + qualifiers.
- **Coaching changes** — curated tenures overlaid on every team timeline.

## Pipeline stages

```
scrape ─▶ store ─▶ analyze ─▶ visualize
TFRRS     SQLite    pandas     Streamlit + Plotly
```

| Layer | Module | Notes |
|-------|--------|-------|
| scrape | `d3xc.scrape.http` | polite cached, rate-limited session (retry/backoff) |
| scrape | `d3xc.scrape.tfrrs` | team/athlete/meet parsers + meet-kind classifier (pure functions, unit-tested) |
| scrape | `d3xc.scrape.athletic_net` | HS-mark linkage w/ fuzzy name matching + confidence |
| store | `d3xc.store.db` | SQLAlchemy 2.0 ORM schema |
| store | `d3xc.store.loaders` | config + scraped records → DB |
| analyze | `d3xc.analyze.metrics` | development metrics (pace-normalized) |
| **LacTiC** | `d3xc.lactic.ratings` | meet-adjusted runner ratings (ridge two-way model) |
| **LacTiC** | `d3xc.lactic.programs` | program strength, trajectory, KMeans tiers |
| **LacTiC** | `d3xc.lactic.projection` | gradient-boosted development model (improvement vs expected) |
| visualize | `d3xc.dashboard.app` | interactive dashboard (incl. LacTiC Rankings view) |

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1) build a demo dataset (synthetic but plausible) so everything runs offline
python scripts/seed_sample.py

# 2) launch the dashboard
streamlit run src/d3xc/dashboard/app.py
```

Open the URL Streamlit prints. The sidebar switches gender / view / conference;
views are also shareable via `?view=Most%20improved&gender=women`.

## Real data (live scrape)

TFRRS team-page slugs in `config/teams.yaml` are **best-effort guesses** flagged
`verified: false`. Resolve them first, then scrape:

```bash
python scripts/resolve_slugs.py          # probe which slugs actually resolve
python scripts/run_scrape.py --limit 2   # smoke test on 2 teams
python scripts/run_scrape.py             # full run (slow, polite: ~3s/request)
```

### Meet-results scraper (team placements + past rosters)

Athlete pages only cover *current* rosters. To get official **team placements**
(conference/regional/national) and *past-roster* individual results, scrape the
meet-result pages. Meet URLs are discovered automatically from already-cached
athlete/team pages (no extra network to find them):

```bash
python scripts/scrape_meets.py                          # discover from cache, scrape all
python scripts/scrape_meets.py --kinds conference,regional,national
python scripts/scrape_meets.py --limit 5 --no-individuals
```

Each meet page yields a `meet_kind` (via `classify_meet_kind`), team placements
for **every** tracked team present (even ones whose rosters weren't scraped), and
individual results de-duplicated against athlete-page data. Team names are
normalized (`'Wilmington (Ohio)' -> 'Wilmington'`).

The HTTP layer caches every page under `data/raw/http_cache/`, so re-parsing is
free and re-runs won't re-hit the network.

## Honest data caveats

- **High school data is not on TFRRS.** HS marks come from Athletic.net /
  MileSplit and are linked to college athletes by fuzzy name + grad-year
  matching. Links carry a `match_confidence` (0–1) and the HS→College view is
  confidence-gated. Treat low-confidence links as approximate. A live
  Athletic.net crawler is intentionally **not** shipped; curate
  `config/hs_marks.csv` or enable it only with permission.
- **Coaching changes are curated**, not scraped — edit `config/coaches.csv`
  (it currently holds clearly-labeled PLACEHOLDER rows to show the format).
- **Marks are pace-normalized** (sec/km) then projected to each gender's
  championship distance (men 8k, women 6k) so 5k/6k/8k results are comparable.

## Config

- `config/teams.yaml` — Ohio D3 programs, conferences, TFRRS slugs.
- `config/coaches.csv` — curated head-coach tenures (`team,gender,coach_name,start_year,end_year,source`).

## LacTiC — ML rankings for runners & programs

LacTiC ranks athletes and programs and quantifies development with ML:

- **Runner rating** — a regularized (ridge) two-way model per gender/season,
  `pace ~ athlete_effect + meet_effect`. The meet effect absorbs course/weather/
  field difficulty, so ratings compare runners fairly across different races.
  Reported as a neutral-course **adjusted pace** and a 0–100 **rating**.
- **Program rating** — mean adjusted pace of each team's **top 5**; the OLS
  slope across seasons is the **development trajectory**; **KMeans** groups
  programs into tiers (Elite / Contender / Developing) by strength × trajectory.
- **Development model** — a `GradientBoostingRegressor` projects next-season
  pace from prior pace, experience, recent trend, team strength, and HS mark.
  The **out-of-fold residual** (actual − predicted) surfaces *most improved
  versus expectation* — a cleaner signal than raw improvement — and forward
  **projections** for returning athletes.

```bash
python scripts/run_analysis.py     # writes reports/lactic_analysis.md
streamlit run src/d3xc/dashboard/app.py   # "LacTiC Rankings" view (default)
```

The design scales to real data: the ratings model uses sparse one-hot design
matrices, so thousands of athletes × hundreds of meets fit comfortably.

## Tests

```bash
pytest            # 35 tests: time utils, parsers, meet scraper, HS linkage,
                  # metrics, LacTiC ratings/programs/projection, dashboard views
```

Dashboard view tests run each Streamlit view in an isolated subprocess (the
AppTest harness segfaults if multiple app instances share one process).
