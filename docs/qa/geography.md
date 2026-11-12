# Geography

Every distinct property address (from property records and the largest-property fields on loan records) gets a county and a metro (`clean/geography.py`). Sources are the Census Geocoder, the Census 2020 ZCTA-to-county relationship file (Connecticut from the 2022 planning-region file) and the OMB July 2023 metropolitan delineation. Fetch dates and hashes: `data/meta/geo/sources.json`.

- Distinct addresses: 34,040. With a county: 33,496 (98.4%). In a metro or micro area: 32,510. With a point (geocoder match): 29,493.
- Geocoder matches outside the filer's own state, discarded: 27.
- Where the geocoder matched, the ZIP crosswalk names the same county 96.5% of the time (n=29,271) and the filer's reported county name 99.2% (n=28,360).

| county source | addresses | share |
| --- | --- | --- |
| geocoder | 29493 | 86.6% |
| reported_name | 3798 | 11.2% |
| none | 544 | 1.6% |
| zip_crosswalk | 205 | 0.6% |

| geocoder result | addresses |
| --- | --- |
| Match | 29520 |
| No_Match | 3110 |
| Skipped | 1001 |
| Tie | 409 |

## Why not a ZIP prefix

California ZIPs starting 900 to 935 are often treated as Los Angeles. Of 1,865 such addresses here, 736 (39%) sit outside the Los Angeles-Long Beach-Anaheim metro:

| metro | addresses |
| --- | --- |
| Riverside-San Bernardino-Ontario, CA | 334 |
| San Diego-Chula Vista-Carlsbad, CA | 230 |
| Oxnard-Thousand Oaks-Ventura, CA | 59 |
| Santa Maria-Santa Barbara, CA | 29 |
| Bakersfield-Delano, CA | 27 |
| Visalia, CA | 18 |

