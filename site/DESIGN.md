# DESIGN.md: Maturity Wall (site)

Read this before touching any page. It is the brief every page is built against.

## 1. Feeling

Exact and calm, like a hydrographic survey sheet: every number has a gauge mark and a source line, and nothing on the page is decoration. Reference collision: a USGS flood-gauge sheet crossed with the Federal Reserve's Financial Stability Report. The one metaphor, used quietly: the refinance gap is water standing above a wall.

## 2. Aesthetic

Swiss / International Typographic (#1 in the playbook) with a survey-sheet layer: a visible 12-column grid, a narrow gauge column on the left that carries section numbers and tick marks, flush-left text, extreme size contrast between the big numbers and the body. Rotation check: the last three sites were organic graph-pad, dark academia and institutional print (the personal site), so this one is cool, gridded and sans-only.

## 3. Typography

- Display: Geologica (variable, self-hosted via Fontsource), weights 700 to 800, `letter-spacing: -0.025em`, line-height 1.02 to 1.1.
- Body and UI: Public Sans (variable, Fontsource; the US Web Design System's face, chosen for the government-report voice), 400 body, 600 labels, tabular figures in tables and axes.
- No serif, no monospace anywhere.
- Scale tokens (px): 12, 14, 16, 20, 28, 40, 64, with the hero number fluid via `clamp(2.75rem, 6vw + 1rem, 5.5rem)`.
- Labels in small caps style: uppercase 12px, tracking 0.08em, Public Sans 600.
- Measure: body copy capped at 66ch. `text-wrap: balance` on headings, `pretty` on paragraphs.

## 4. Color (light only for v1)

| token | hex | use |
| --- | --- | --- |
| `--paper` | `#F4F5F2` | page and chart surface (cool survey paper) |
| `--ink` | `#111417` | headings, numbers |
| `--ink-2` | `#41474D` | body text |
| `--muted` | `#5F666C` | metadata, axis labels (5.3:1 on paper) |
| `--rule` | `#C8CCC7` | hairlines |
| `--grid` | `#E1E4DF` | chart gridlines |
| `--wall` | `#7A8187` | the part of a bar that a lender would refinance (3.6:1 on paper) |
| `--water` | `#2A78D6` | the refinance gap, risk, the one accent |
| `--water-ink` | `#1C5CAB` | links and accent text (6.1:1 on paper) |

Risk ramp (sequential, one hue): `#CDE2FB #9EC5F4 #6DA7EC #3987E5 #2A78D6 #1C5CAB #104281 #0D366B`.

Property types (charts and chips only; validated adjacent-pair order, worst CVD Delta E 9.1, normal 22.9, on `--paper`): office `#EB6834`, retail `#1BAF7A`, multifamily `#EDA100`, lodging `#008300`, industrial `#E87BA4`, self-storage `#6250D6`, mixed use and other `#E34948`. Three of these sit under 3:1 on paper, so every type chart carries direct labels or a table. Blue is kept out of the type palette: blue always means the gap or risk.

Status (always with an icon and a word): critical `#B42318` (matured unpaid, special servicing), warning `#8A5A00` (30+ days delinquent), neutral `--muted` (performing).

## 5. Border language

Radius 0 everywhere. 1px hairlines in `--rule`. No shadows, except a 1px ring plus `0 2px 8px rgb(17 20 23 / 0.08)` on tooltips and the filter dropdown, the only things that float.

## 6. Texture

Flat. The only ornament is functional: gauge tick marks in the left column and on chart axes.

## 7. Motion

Calm and precise. On first view the hero wall rises bar by bar (40 ms stagger by year, 280 ms, `cubic-bezier(0.2, 0.7, 0.2, 1)`), then the water fills. Hover and focus transitions 120 ms. Under `prefers-reduced-motion: reduce` everything renders in place.

## 8. Layout spine

A 12-column grid, max 1200px, with a 2-column gauge rail on the left for section numbers ("01", "02") and labels; content in columns 3 to 12. The hero is the maturity wall chart itself, full content width, with the headline number crossing the chart's top edge (the one deliberate grid break). Every chart has: a question as its title, the chart, a one-line takeaway, a source line, and a "show table" toggle.

## 9. Don't

No purple or indigo, no gradients outside the risk ramp, no rounded corners, no card grids of three, no icon library (status glyphs are hand-drawn inline SVG), no emoji, no stock imagery, no glassmorphism, no centered paragraphs, no em dashes in copy, no firm logos. Every score, bid and return shows its scenario and the not-investment-advice line.
