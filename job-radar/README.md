# Job Radar — engineering jobs near PwC offices

**Standalone website:** Open /job-radar/ on the Netlify deployment connected to this repository. This folder is isolated from the root portfolio website; the scanner runs on GitHub Actions and the website reads its latest data from GitHub.

## What it does

- Scans selected **public Greenhouse, Lever and Ashby job boards** every ~15 minutes using GitHub Actions.
- Scores postings for an early-career mechanical/manufacturing/design/process/automation/quality/operations engineering profile. Filters senior titles, internships and postings with clearly incompatible experience/start requirements.
- Compares the worksite to **64 PwC US office addresses**, transcribed from [PwC's directory](https://www.pwc.com/us/en/about-us/pwc-office-locations.html).
- Distinguishes **Verified ≤20 min** from **Check commute**. No city-only location is ever treated as a verified street-level 20-minute drive.
- Shows source, fit score, dates, PwC office, Google Maps directions and direct employer application form.
- Stores Saved/Applied states in **your current browser only**; these are not synced to your GitHub account.
- Supports optional SMTP alerts for newly discovered postings.

## Important setup: actual 20-minute driving routes

1. Create an [openrouteservice](https://openrouteservice.org/dev/#/signup) API key.
2. In this GitHub repository, open **Settings → Secrets and variables → Actions → New repository secret**.
3. Name the secret **ORS_API_KEY**, and paste the key.
4. Open [Job Radar scanner in GitHub Actions](https://github.com/dylaneburkey/dylanburkey/actions/workflows/job-radar.yml) and choose **Run workflow**.

The scanner uses [openrouteservice driving-car routes](https://openrouteservice.org/dev/#/api-docs) and Census street-address geocoding where a street address is available. Routing uses non-traffic-adjusted travel times. Without the API key, **the site still finds and ranks potential jobs, but does not claim a verified commute**. Because most ATS listings give only a city, many jobs will remain in **Check commute**, even with the key. Use Check drive to inspect the employer's actual worksite.

The user profile assumes **May 2027 graduation, available July 2027**, and relevant internships/research. A high match score is a heuristic, not a guarantee of qualifications or an interview. Generic early-career listings with no specified 2027 start may still be for immediate hires; confirm the date before applying.

## Activate email alerts (optional)

Add these GitHub Actions repository secrets:

| Secret | Description |
|---|---|
| SMTP_HOST | Your email provider's SMTP server |
| SMTP_PORT | TLS port, usually 587 |
| SMTP_USER | SMTP login name |
| SMTP_PASSWORD | SMTP app password / credential |
| ALERT_TO | Destination email address |
| ALERT_FROM | Optional sender; defaults to SMTP_USER |
| ORS_API_KEY | Driving directions key (strongly recommended) |

If the email secrets are absent, alerts are simply off. The automated dashboard does not require any personal email access.

## Extend company coverage

Edit the **SOURCES** array in [scan.py](scan.py) to include public ATS boards for target employers. Each entry is (provider, board_slug, display_company_name). Only publicly available GET endpoints are used, and boards that do not exist or fail temporarily are safely skipped.

Supported providers:
- Greenhouse: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
- Lever: https://api.lever.co/v0/postings/{slug}?mode=json
- Ashby: https://api.ashbyhq.com/posting-api/job-board/{slug}

Many employers, including those using Workday or custom career websites, **are not covered in this first version**. This isn't a universal LinkedIn/Indeed scraper. Entries do not imply each configured board is live; the scanner reports successful source count.

## Running locally

Python 3.12+, standard library only:

    python job-radar/scan.py
    python -m http.server 8000

Open http://localhost:8000/job-radar/ . The UI retrieves the published data from GitHub's raw file.

## Operations

- GitHub workflow: [job-radar.yml](../.github/workflows/job-radar.yml)
- Data: [jobs.json](data/jobs.json), [geocache.json](data/geocache.json), [route_cache.json](data/route_cache.json)
- To view scanner errors: GitHub → Actions → Job Radar scanner → latest run → Scan job boards step.
- GitHub scheduling is **best effort**, can run late, and does not guarantee immediate discovery. The first_seen date is when **this scanner first discovered** the posting, not necessarily the employer's original publish date.
- All job feed/cache data is public in this repository; do not commit private resumes, passwords, or personal information.
- The workflow writes only to job-radar/data/ . It does not alter the portfolio homepage.
- Location geocoding: [US Census Geocoder](https://geocoding.geo.census.gov/) for street-level US worksite addresses and [Open-Meteo](https://open-meteo.com/en/docs/geocoding-api) for approximate city centers. Do not interpret city-center driving routes as confirmed worksite commutes.
- Routing: [openrouteservice](https://openrouteservice.org/) (requires your API key). Map attribution and attribution requirements apply to each service.
