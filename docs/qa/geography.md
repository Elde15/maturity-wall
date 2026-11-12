# Geography

Every distinct property address (from property records and the largest-property fields on loan records) gets a county and a metro (`clean/geography.py`). Sources are the Census Geocoder, the Census 2020 ZCTA-to-county relationship file (Connecticut from the 2022 planning-region file) and the OMB July 2023 metropolitan delineation. Fetch dates and hashes: `data/meta/geo/sources.json`.

- Distinct addresses: 25,627. With a county: 25,463 (99.4%). In a metro or micro area: 24,738. With a point (geocoder match): 22,590.
- Geocoder matches outside the filer's own state, discarded: 4.
- Where the geocoder matched, the ZIP crosswalk names the same county 96.5% of the time (n=22,451) and the filer's reported county name 99.2% (n=22,030).

| county source | addresses | share |
| --- | --- | --- |
| geocoder | 22590 | 88.1% |
| reported_name | 2781 | 10.9% |
| none | 164 | 0.6% |
| zip_crosswalk | 92 | 0.4% |

| geocoder result | addresses |
| --- | --- |
| Match | 22594 |
| No_Match | 2319 |
| Skipped | 402 |
| Tie | 312 |

## Why not a ZIP prefix

California ZIPs starting 900 to 935 are often treated as Los Angeles. Of 1,404 such addresses here, 583 (42%) sit outside the Los Angeles-Long Beach-Anaheim metro:

| metro | addresses |
| --- | --- |
| Riverside-San Bernardino-Ontario, CA | 266 |
| San Diego-Chula Vista-Carlsbad, CA | 181 |
| Oxnard-Thousand Oaks-Ventura, CA | 44 |
| Bakersfield-Delano, CA | 26 |
| Santa Maria-Santa Barbara, CA | 23 |
| Visalia, CA | 12 |

