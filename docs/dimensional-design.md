# Dimensional Design: Chicago Crime Data Warehouse on Amazon RDS

This document is the **design** that bridges raw sources (already landing in
the S3 raw zone, see `CLAUDE.md` "Current Ingestion Flow") to a star-schema
data warehouse hosted in **Amazon RDS for PostgreSQL**.

It follows the **4-Step Dimensional Design Process** taught in
`docs/lectures/02 - Retail Sales.md` (slides 5–15), and references:

- **Lecture 01** — DW components, star schema, surrogate keys.
- **Lecture 02** — 4-step process and design techniques (degenerate dim,
  factless fact, role-playing dim, separate Date vs Time, smart keys, additive
  vs semi/non-additive measures).
- **Lecture 03** — fact-table types, conformed dimensions, bus matrix.
- **Lecture 04** — Slowly Changing Dimensions (SCD types 1/2/3, hybrid).
- **Lecture 05** — junk dimensions.
- **Lecture 06** — multi-valued dimensions, bridge tables, outriggers.

The grain, dimensions, and facts proposed below were derived directly from
real columns observed in API samples pulled on 2026-05-10. No column shape is
assumed — every field referenced in this document is grounded in an actual
sampled row.

---

## 1. Purpose and Scope

We are building a **conformed-dimension star schema** to answer business
questions about reported crimes in Chicago, sliced by **time**, **place**,
**crime classification**, **weather conditions**, and **community
socioeconomic context**.

Two business processes are in scope:

| # | Business process | Required by spec? | Source |
|---|---|---|---|
| 1 | **Crime incident reporting** (primary) | Yes (≥ 1 fact required) | Chicago Crimes 2018-2024 |
| 2 | **Arrest events** (enrichment, drives bus matrix) | Optional | Chicago Police Arrests |

The grading rubric (see `requirements/Project_DW_Big_Data_Implementation_2025.md`,
Slides 5–6) asks for:

- ≥ 1 fact table at atomic grain, with **no aggregate fact**.
- A **conformed bus matrix** across processes.
- **All dimension tables must implement SCD**.
- Glue-driven ETL, RDS or S3 storage, QuickSight on top.

This document satisfies all four design points.

---

## 2. Source Data Inventory

Columns and quirks listed below were observed in actual samples. Quirks
matter — they drive the design (degenerate keys, defensive nulls, snapshot
joins).

### 2.1 Chicago Crimes (primary fact source)

API: `https://data.cityofchicago.org/resource/ijzp-q8t2.csv`

Sampled columns (one row per reported incident):

```
id, case_number, date, block, iucr, primary_type, description,
location_description, arrest, domestic, beat, district, ward, community_area,
fbi_code, x_coordinate, y_coordinate, year, updated_on, latitude, longitude,
location
```

Observations from the sample:

- `id` is a numeric stable surrogate from CPD's CLEAR system → use as the
  **natural key** for the fact row.
- `case_number` is the **CPD report/control number** → a textbook
  **degenerate dimension** (Lecture 02 slide 22 — TransID example).
- `date` is the *occurrence* timestamp; `updated_on` is the *report-update*
  timestamp. Two distinct date roles → **role-playing date dim**.
- `community_area`, `district`, `ward`, `beat` can all be NULL on the same
  row (sample row 3 had blank coords + blank community area). Need an
  "Unknown" surrogate row in `dim_location` (Lecture 02 slide 67 — null FK
  rule).
- Numeric `latitude`/`longitude` are useful as **fact-level measures** for map
  visualisations and as **outrigger attributes** of `dim_location` for filters,
  per the "numeric values as both Dim and Fact" rule (Lecture 02 slide 64).
- `arrest`, `domestic` are low-cardinality booleans — candidates for a
  **junk dimension** (Lecture 05).

### 2.2 IUCR Crime Codes (crime-type lookup)

API: `https://data.cityofchicago.org/resource/c7ck-438e.csv`

Sampled columns:

```
iucr, primary_description, secondary_description, index_code, active
```

- ~400 rows. Joins to `fact_crime.iucr` 1:1.
- `index_code` ∈ {I, N} (Index vs Non-Index — UCR Part I/II classification).
- `active` flag flips when CPD retires/replaces a code → `dim_crime_type`
  becomes an **SCD candidate** (Type 1 if we don't care about retirement
  history, Type 2 if we do).

### 2.3 Community Area Socioeconomics (location enrichment)

API: `https://data.cityofchicago.org/resource/kn9c-c2s2.csv`

Sampled columns:

```
ca, community_area_name, percent_of_housing_crowded,
percent_households_below_poverty, percent_aged_16_unemployed,
percent_aged_25_without_high_school_diploma,
percent_aged_under_18_or_over_64, per_capita_income_, hardship_index
```

- 77 rows per snapshot, one per community area.
- These attributes change between census/ACS releases → **strong SCD2 case**
  on `dim_location` (Lecture 04 slide 7 — Type 2 add new row).

### 2.4 Open-Meteo Hourly Weather (date-hour enrichment)

API: `https://archive-api.open-meteo.com/v1/archive` for Chicago centroid
`(41.85, -87.65)`.

Confirmed JSON shape from a 2024-06-01 sample:

```
hourly: {
  time: ISO8601 hourly,
  temperature_2m: °C,
  precipitation: mm,
  wind_speed_10m: km/h,
  weather_code: WMO code,
  relative_humidity_2m: %
}
```

- Grain = one row per hour at one fixed lat/long.
- ~365k rows for 2018-2024.
- Numeric measures kept on `fact_crime` (for aggregations / map overlays);
  bucketed categories (clear / rain / snow / storm) kept on `dim_weather`
  (for slicing) — Lecture 02 slide 64 again.

### 2.5 Chicago Police Arrests (optional enrichment, second business process)

API: `https://data.cityofchicago.org/resource/dpt3-jri9.csv`

Sampled columns:

```
cb_no, case_number, arrest_date, race,
charge_1_statute, charge_1_description, charge_1_type, charge_1_class,
charge_2_*, charge_3_*, charge_4_*,
charges_statute, charges_description, charges_type, charges_class
```

- Up to 4 charges per arrest, plus a denormalised `charges_*` field with
  `|`-separated values. **Multi-valued dimension** (Lecture 06) → bridge
  table.
- Joins to crime via `case_number`.
- Demographics in this feed are limited to `race` (no age/sex in current
  schema — design must not assume them).

---

## 3. The Four-Step Dimensional Design Process

Per Lecture 02 slide 6, the process is:

> Step 0 – Gather requirements
> Step 1 – Choose the business process
> Step 2 – Declare the grain
> Step 3 – Identify the dimensions
> Step 4 – Identify the facts
> Step 5 – Finish up the design

Below, each step is applied explicitly.

### 3.0 Step 0 — Gather Requirements

What questions must the warehouse answer? (Drives everything downstream.)

| # | Business question | Requires |
|---|---|---|
| Q1 | How many crimes occurred per community area, per month, per crime category? | `fact_crime` × `dim_location` × `dim_date` × `dim_crime_type` |
| Q2 | Does precipitation or extreme temperature correlate with violent crime hours? | `fact_crime` × `dim_weather` × `dim_time_of_day` |
| Q3 | Has arrest rate changed over time, by district? | `fact_crime` arrest flag × `dim_date` × `dim_location` |
| Q4 | Do socioeconomically distressed community areas have higher Index Crime rates? | `fact_crime` × `dim_location` (SCD2 socioeconomic) × `dim_crime_type` (index_code) |
| Q5 | What time-of-day pattern do domestic incidents follow? | `fact_crime` × `dim_time_of_day` × junk dim (domestic flag) |
| Q6 | (optional) For arrested cases, what charge categories appear together? | `fact_arrest` × charge bridge × `dim_date` |

These six questions are the acceptance test for the design.

### 3.1 Step 1 — Choose the Business Process

Lecture 02 slide 7: *"A business process is a low-level activity performed by
the organisation… not a department or function."*

The candidate processes from our sources:

| Source | Business process | Includes for V1? |
|---|---|---|
| Chicago Crimes feed | **Reporting a crime incident** | Yes (primary) |
| Chicago Arrests feed | **Arresting / charging a person** | Yes (drives bus matrix) |
| Socioeconomic CSV | (descriptive snapshot — not a process) | No — feeds `dim_location` SCD2 |
| Weather API | (descriptive observation — not a process) | No — feeds `dim_weather` |

So the warehouse hosts two facts: `fact_crime` (process 1) and `fact_arrest`
(process 2, optional). Two processes lets us demonstrate a **non-trivial bus
matrix** (Lecture 03 slide 36).

### 3.2 Step 2 — Declare the Grain

Lecture 02 slide 9: *"Atomic grain refers to the lowest level that data is
captured in the business process… preferably it should be at the most atomic
level possible."*

#### 3.2.1 `fact_crime` grain

> **One row per reported crime incident**, identified by Chicago's `id`.

This is the natural atomic grain — the source already publishes one row per
incident, and `id` is stable across updates. It is a **transaction fact**
(Lecture 03 slide 11) — single point in time, insert-only, never revisited.

Updates to a previously-reported crime (correction, late classification) are
handled by **upsert by `id`** during ETL load — the fact row gets replaced,
*not* a new event row added. This is consistent with `updated_on` being a
mutable column on the source. The previous version is preserved in the **raw
S3 zone** (append-only by ingest_date partition, per CLAUDE.md), so audit is
not lost.

#### 3.2.2 `fact_arrest` grain (optional)

> **One row per arrest event** (one `cb_no`).

Charges are 1..4 per arrest, so we attach a separate **`bridge_arrest_charge`**
table at one row per (arrest, charge), keeping the arrest fact at the
arrest-event grain. This is the standard multi-valued resolution from
Lecture 06.

### 3.3 Step 3 — Identify the Dimensions

Lecture 02 slide 11: *"Who, what, when, why, where, and how associated with
the event?"* and *"only add additional dimensions if they take only one
value under each combination of the primary dimensions."*

For `fact_crime`:

| W-question | Dimension | Source columns it serves |
|---|---|---|
| **When** (date) | `dim_date` | `date` (occurrence), `updated_on` (report) — role-playing |
| **When** (time-of-day) | `dim_time_of_day` | hour from `date` (kept separate per Lecture 02 slide 41) |
| **Where** | `dim_location` | `community_area`, `district`, `ward`, `beat`, `block`, `location_description` |
| **What** | `dim_crime_type` | `iucr`, `primary_type`, `description`, `fbi_code`, `index_code` (from IUCR table) |
| **Under what conditions** | `dim_weather` | weather lookup by occurrence date+hour |
| **How** (low-card flags) | `dim_crime_flags` (junk) | `arrest`, `domestic` |

Each candidate is a single value per fact row → grain holds.

`case_number` is identified as a **degenerate dimension** — kept directly on
`fact_crime` because it has no descriptive attributes worth a separate
table, but is used for grouping fact rows belonging to the same case
(Lecture 02 slide 22).

For `fact_arrest`:

| Dimension | Conformed with `fact_crime`? |
|---|---|
| `dim_date` | **Yes** (same surrogate keys, same attributes) |
| `dim_time_of_day` | **Yes** |
| `dim_arrestee` | No (arrest-only) |
| `dim_crime_type` | **Yes** (joined via charge bridge → IUCR-equivalent code) |
| `dim_location` | Not directly — arrest feed lacks community area; only via the linked crime row through `case_number` |

Conformed dimensions are listed in §4.

### 3.4 Step 4 — Identify the Facts

Lecture 02 slide 13: *"Facts must be true to the grain. Percentages and
ratios are non-additive — store numerator and denominator instead."*

#### `fact_crime` measures

| Measure | Type (per Lecture 02 slide 43) | Stored as |
|---|---|---|
| `incident_count` (constant 1) | Additive | `INTEGER` (=1) |
| `is_arrest` | Semi-additive — boolean cast to int for SUM | `SMALLINT` 0/1 |
| `is_domestic` | Semi-additive — boolean cast to int | `SMALLINT` 0/1 |
| `latitude`, `longitude` | Non-additive (means lose meaning when summed) | `NUMERIC(9,6)` — but only used for visualisation, never SUM-ed |
| `temperature_celsius_at_event` | Additive within a time window for AVG; **non-additive when SUM-ed** | `NUMERIC(5,2)` |
| `precipitation_mm_at_event` | Additive across time | `NUMERIC(6,2)` |
| `hours_to_update` (`updated_on - date`) | Additive | `INTEGER` |

`incident_count = 1` is intentional. It enables `SUM(incident_count)` for
trivial roll-ups and avoids surprises with `COUNT(*)` over outer-joined
queries, exactly as Kimball recommends.

We do **not** store derived ratios (e.g., `arrest_rate`) — they are
non-additive and computed at query time from the additive numerator/denominator
columns above. (Lecture 02 slide 13 + slide 56.)

#### `fact_arrest` measures

| Measure | Type |
|---|---|
| `arrest_count` (constant 1) | Additive |
| `charge_count_at_arrest` | Additive |

`charge_count_at_arrest` is denormalised onto the arrest fact for
performance, even though it could be derived by counting bridge rows.

### 3.5 Step 5 — Finish Up the Design (Fill Details)

Lecture 02 slide 15. Concretely this means: surrogate keys, attribute
hierarchies, current-flag attributes, smart keys, "unknown" rows, defaults
for null FKs.

| Decision | Choice | Rationale |
|---|---|---|
| Surrogate key strategy on dimensions | `BIGINT GENERATED BY DEFAULT AS IDENTITY` | Lecture 01 slide 32 — non-meaningful integer; faster joins; partitioning friendly. |
| `dim_date` PK | **Smart key `YYYYMMDD`** as `INTEGER` | Lecture 02 slide 61 — partition-friendly; can derive date without join. |
| `dim_time_of_day` PK | `INTEGER` 0–86399 (seconds-of-day) or 0–23 (hour bucket); we pick `0–23` (hourly) | Matches weather grain; Lecture 02 slide 41 — separate from date keeps row count tiny. |
| Special unknown rows | Surrogate `0` row in every dim | Lecture 02 slide 67 — null FKs replaced with code `0`. |
| Special "not applicable" row | Surrogate `-1` (e.g., `dim_weather` row for "weather unavailable") | Lecture 03 slide 23 — surrogate keys for special conditions. |
| Fact PK | Surrogate `BIGINT IDENTITY` | Lecture 02 slide 70 — optional but useful for ETL idempotency. |
| Fact natural key | `crime_id` (= source `id`) preserved as a column with `UNIQUE` | Idempotent upserts on re-fetch. |
| Hierarchies | beat → district → ward / community_area; iucr → fbi_code → category | Lecture 01 slide 40. |

---

## 4. Conformed Dimension Bus Matrix

Per Lecture 03 slide 36. Rows are business processes; columns are dimensions.
A check ✓ means the dimension is conformed (same surrogate keys, attribute
names, attribute values) across both fact tables.

|                         | `dim_date` | `dim_time_of_day` | `dim_location` | `dim_crime_type` | `dim_weather` | `dim_crime_flags` (junk) | `dim_arrestee` | charge bridge |
|-------------------------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Crime Incident Reporting** (`fact_crime`) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |   |   |
| **Arrest Events** (`fact_arrest`, optional) | ✓ | ✓ |   | ✓ |   |   | ✓ | ✓ |

Conformance gives us **drill-across** (Lecture 03 slide 43): e.g., "for the
same `dim_date.date_key`, how many *crime reports* vs *arrest events*?". The
two facts can be joined through the conformed dimensions, not directly.

---

## 5. SCD Strategy Per Dimension

Lecture 04 slides 5–17 lays out the SCD types. The project rubric requires
**every dimension** to implement SCD. The decision per dimension:

| Dimension | SCD type | Why |
|---|---|---|
| `dim_date` | **Type 0** (retain original) | Calendar attributes (month, quarter, holiday) never legitimately change. (Lecture 04 slide 5 — Type 0 = no change.) |
| `dim_time_of_day` | **Type 0** | Hour-of-day attributes are static. |
| `dim_location` | **Type 2** with embedded SCD1 attributes (i.e., **SCD7 dual Type 1+2**) | Socioeconomic attributes (poverty %, hardship index, per-capita income) version yearly with each ACS/census snapshot. Static attributes (`community_area`, name) overwrite. (Lecture 04 slides 7–11, 16.) |
| `dim_crime_type` | **Type 2** | When CPD retires/replaces an IUCR code we want historical reports to stay correct against the *then-active* description. (Lecture 04 slide 7.) |
| `dim_weather` | **Type 0** | Each row is an immutable hourly observation — no change concept. |
| `dim_crime_flags` (junk) | **Type 1** (overwrite) | Junk dimension is just the cartesian product of the flag combinations; new combos add a row, never edit. (Lecture 04 slide 6.) |
| `dim_arrestee` | **Type 1** | The only attribute is `race`, which is recorded per arrest and not "owned" by a person across time in this feed. |

Every SCD2 dim carries the standard tracking columns:

```
scd_start_date    DATE        NOT NULL,
scd_end_date      DATE        NOT NULL DEFAULT '9999-12-31',
is_current        BOOLEAN     NOT NULL DEFAULT TRUE,
scd_version       SMALLINT    NOT NULL DEFAULT 1,
scd_hash          BYTEA       NOT NULL  -- hash of SCD2-tracked columns, for change detection
```

The natural key is *not* the PK (Lecture 01 slide 32). The natural key plus
`is_current = TRUE` gives the "current" row; the natural key plus
`scd_start_date <= event_date < scd_end_date` gives the historically correct
row at event time.

---

## 6. Design Techniques Applied

Each technique is from Lecture 02 (design techniques, slides 17–48), Lecture
05 (junk dim), and Lecture 06 (multi-valued and outriggers).

### 6.1 Degenerate Dimension — `case_number`

`case_number` is CPD's report control number. It has no descriptive
attributes that justify a separate dim, but groups fact rows belonging to one
case. Stored directly on `fact_crime` and on `fact_arrest`. (Lecture 02
slide 22.)

### 6.2 Separate `dim_date` and `dim_time_of_day`

Combined date-time dim would be 7 × 365 × 24 = 61,320 rows for our 7-year
slice. Separate dims give 2,557 + 24 = 2,581 rows. (Lecture 02 slide 41.)

### 6.3 Role-Playing Date Dimension

`fact_crime` carries two date FKs:

- `report_date_key` → derived from `updated_on`
- `occurrence_date_key` → derived from `date`

Both reference the same `dim_date` table. Queries use SQL aliases
(`dim_date AS d_occ`, `dim_date AS d_rpt`) — Lecture 02 slide 29 example.

### 6.4 Junk Dimension — `dim_crime_flags`

Two booleans (`is_arrest`, `is_domestic`) → 4 combinations →
`dim_crime_flags` is pre-populated with 4 rows (plus 1 unknown). The fact
column `crime_flags_key` replaces both flag columns and lets QuickSight slice
by the human-readable label (e.g., "Arrest, Non-Domestic"). (Lecture 05.)

We *also* keep raw `is_arrest` and `is_domestic` SMALLINTs as additive
measures on `fact_crime` for SUM-friendly aggregations — the junk dim is for
labels, the measure is for math.

### 6.5 Multi-Valued Dimension via Bridge — `bridge_arrest_charge`

An arrest has 1..4 charges (`charge_1_*` … `charge_4_*` plus a
`|`-delimited `charges_*` field). Per Lecture 06, multi-valued attributes
go in a bridge table:

```
bridge_arrest_charge
  arrest_key       BIGINT   FK → fact_arrest
  charge_type_key  BIGINT   FK → dim_crime_type
  charge_position  SMALLINT (1..4)
  charge_class     CHAR(2)
  charge_statute   TEXT
```

Note: `charge_type_key` reuses the conformed `dim_crime_type`, since IUCR
codes appear in both feeds.

### 6.6 Outrigger / Embedded Snapshot — Socioeconomic Attributes on `dim_location`

Lecture 06 mentions **outriggers** (a dim that hangs off another dim).
Two valid approaches:

A. Keep socioeconomics inside `dim_location` as SCD2-tracked columns
   (recommended — denormalised, fast for QuickSight).
B. Split `dim_socioeconomic_snapshot` as a separate outrigger keyed by
   `community_area_key + snapshot_year`.

**Decision: option A**. Lecture 01 slide 5 endorses denormalisation for DW;
the volume (77 community areas × few snapshots) is trivial.

### 6.7 What We Are *Not* Doing — and Why

| Technique (lecture ref) | Used? | Reason |
|---|---|---|
| Aggregated fact table (Lecture 02 §4) | **No** | Rubric explicitly forbids "aggregate fact" — all reporting is from the atomic `fact_crime`. QuickSight aggregations done at query time. |
| Periodic snapshot fact (Lecture 03 slide 12) | **No** | Crime reporting is a transaction, not a level-tracking process. |
| Accumulating snapshot fact (Lecture 03 slide 21) | **No** | A crime case's life cycle (report → arrest → adjudication) could fit this pattern, but court data is out of scope for V1. |
| SCD3 (add column) on `dim_location` | **No** | We need the *full* history of socioeconomic indicators (>3 snapshots), not just current vs prior. Type 2 is correct. (Lecture 04 slide 13.) |
| Mini-dimension (Lecture 06 slide on RCDs) | **No** | None of our dims change "rapidly" — socioeconomics change yearly at most. |

---

## 7. Star Schema (text diagram)

```
                       +----------------+
                       |   dim_date     |
                       |  date_key (PK) |
                       |  full_date     |
                       |  dow, is_*     |
                       |  month, year   |
                       +-------+--------+
                               |
                               | (occurrence_date_key, report_date_key)
                               |
+----------------+      +------+--------+      +--------------------+
| dim_time_of_day|------|               |------| dim_crime_type     |
| time_key (PK)  |      |  fact_crime   |      | crime_type_key (PK)|
| hour, am_pm    |      |---------------|      | iucr (NK)          |
| period_of_day  |      |  surrogates:  |      | primary_type       |
+----------------+      |  date keys    |      | fbi_code, index    |
                        |  time key     |      | scd_* (Type 2)     |
+----------------+      |  loc key      |      +--------------------+
| dim_location   |------|  type key     |
| location_key PK|      |  weather key  |      +--------------------+
| community_area |      |  flags key    |------| dim_crime_flags    |
| district, ward |      |               |      | flags_key (PK)     |
| beat, block    |      |  measures:    |      | is_arrest          |
| socio_* (SCD2) |      |  incident=1   |      | is_domestic        |
| scd_* (Type 2) |      |  is_arrest    |      | label              |
+----------------+      |  is_domestic  |      +--------------------+
                        |  temp_c       |
+----------------+      |  precip_mm    |
| dim_weather    |------|  lat, lng     |
| weather_key PK |      |  hours_to_upd |      +--------------------+
| date_key (NK)  |      |               |      | dim_arrestee       |
| hour (NK)      |      |  degenerate:  |      | (used by arrest)   |
| weather_cat    |      |  case_number  |      +--------------------+
| temp_band      |      |  crime_id (NK)|
| precip_band    |      +-------+-------+
+----------------+              |
                                |
                       (optional) drill-across via case_number / dim_date / dim_crime_type
                                |
                        +-------+-------+
                        |  fact_arrest  |
                        +-------+-------+
                                |
                       +--------+--------+
                       | bridge_arrest_charge |
                       +-----------------+
                                |
                                v
                       +-----------------+
                       |  dim_arrestee   |
                       +-----------------+
```

---

## 8. Target RDS Implementation

### 8.1 Engine Choice

**Amazon RDS for PostgreSQL 16** is recommended:

- AWS Glue has a native PostgreSQL JDBC connector for both source and target.
- `GENERATED BY DEFAULT AS IDENTITY` cleanly produces dimension surrogate
  keys without sequences gymnastics.
- Strong support for `INSERT … ON CONFLICT … DO UPDATE` (idempotent upserts
  by `crime_id`).
- Native `BYTEA` for SCD hashes; `JSONB` if we want raw payload audit.

MySQL is acceptable but lacks `UPSERT` ergonomics; Aurora PostgreSQL is the
upgrade path if scale demands it later.

### 8.2 Schema Layout

Three logical schemas inside one RDS database:

| Schema | Purpose | Loaded from |
|---|---|---|
| `raw_stg` | Mirror of S3 raw, untyped except primary keys; one table per source | Glue job reading the S3 raw zone |
| `dw_staging` | Cleansed, type-cast, deduplicated; transient | Glue job over `raw_stg` |
| `dw` | The star schema (presentation area, Lecture 01 slide 14) | Glue job applies SCD merges |

This three-tier shape matches Lecture 01 slide 14 (Operational Source →
Staging → Presentation) and the medallion pattern from Lecture 13 (bronze /
silver / gold).

### 8.3 DDL Sketches

Condensed — full DDL belongs in `terraform/` or a `sql/dw_schema.sql` once
this design is approved.

```sql
-- 8.3.1  dim_date  (smart key, SCD0)
CREATE TABLE dw.dim_date (
  date_key       INTEGER     PRIMARY KEY,           -- YYYYMMDD smart key
  full_date      DATE        NOT NULL UNIQUE,
  day_of_week    SMALLINT    NOT NULL,
  day_name       TEXT        NOT NULL,
  is_weekend     BOOLEAN     NOT NULL,
  is_us_holiday  BOOLEAN     NOT NULL,
  month_num      SMALLINT    NOT NULL,
  month_name     TEXT        NOT NULL,
  quarter        SMALLINT    NOT NULL,
  year           SMALLINT    NOT NULL,
  iso_week       SMALLINT    NOT NULL
);
INSERT INTO dw.dim_date VALUES (0, '0001-01-01', ...);  -- Unknown row

-- 8.3.2  dim_time_of_day  (hourly, SCD0)
CREATE TABLE dw.dim_time_of_day (
  time_key       SMALLINT    PRIMARY KEY,           -- 0..23
  hour_24        SMALLINT    NOT NULL,
  hour_12        SMALLINT    NOT NULL,
  am_pm          CHAR(2)     NOT NULL,
  period_of_day  TEXT        NOT NULL               -- 'Late Night','Morning','Afternoon','Evening','Night'
);

-- 8.3.3  dim_location  (SCD2 with embedded socioeconomics)
CREATE TABLE dw.dim_location (
  location_key            BIGINT  GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  community_area          SMALLINT,                 -- natural key part 1
  district                TEXT,                     -- natural key part 2
  ward                    SMALLINT,
  beat                    TEXT,
  block                   TEXT,
  community_area_name     TEXT,                     -- SCD1 (overwrite)
  pct_housing_crowded     NUMERIC(5,2),             -- SCD2
  pct_below_poverty       NUMERIC(5,2),             -- SCD2
  pct_unemployed_16plus   NUMERIC(5,2),             -- SCD2
  pct_no_hs_25plus        NUMERIC(5,2),             -- SCD2
  pct_under18_or_over64   NUMERIC(5,2),             -- SCD2
  per_capita_income_usd   INTEGER,                  -- SCD2
  hardship_index          SMALLINT,                 -- SCD2
  scd_start_date          DATE        NOT NULL,
  scd_end_date            DATE        NOT NULL DEFAULT '9999-12-31',
  is_current              BOOLEAN     NOT NULL DEFAULT TRUE,
  scd_version             SMALLINT    NOT NULL DEFAULT 1,
  scd_hash                BYTEA       NOT NULL,
  UNIQUE (community_area, district, ward, beat, scd_start_date)
);

-- 8.3.4  dim_crime_type  (SCD2)
CREATE TABLE dw.dim_crime_type (
  crime_type_key       BIGINT  GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  iucr                 TEXT        NOT NULL,         -- natural key
  primary_type         TEXT,
  description          TEXT,
  fbi_code             TEXT,
  index_code           CHAR(1),                      -- 'I' or 'N'
  active               BOOLEAN     NOT NULL,
  scd_start_date       DATE        NOT NULL,
  scd_end_date         DATE        NOT NULL DEFAULT '9999-12-31',
  is_current           BOOLEAN     NOT NULL DEFAULT TRUE,
  scd_version          SMALLINT    NOT NULL DEFAULT 1,
  scd_hash             BYTEA       NOT NULL,
  UNIQUE (iucr, scd_start_date)
);

-- 8.3.5  dim_weather  (SCD0, hourly observation)
CREATE TABLE dw.dim_weather (
  weather_key          BIGINT  GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  obs_date_key         INTEGER     NOT NULL REFERENCES dw.dim_date,
  obs_hour             SMALLINT    NOT NULL REFERENCES dw.dim_time_of_day,
  weather_code_wmo     SMALLINT,
  weather_category     TEXT,                         -- 'Clear','Rain','Snow','Storm','Fog'
  temp_band            TEXT,                         -- 'Freezing','Cold','Mild','Warm','Hot'
  precip_band          TEXT,                         -- 'None','Light','Moderate','Heavy'
  UNIQUE (obs_date_key, obs_hour)
);

-- 8.3.6  dim_crime_flags  (junk, SCD1)
CREATE TABLE dw.dim_crime_flags (
  flags_key       SMALLINT    PRIMARY KEY,
  is_arrest       BOOLEAN     NOT NULL,
  is_domestic     BOOLEAN     NOT NULL,
  label           TEXT        NOT NULL               -- e.g., 'Arrest, Domestic'
);

-- 8.3.7  fact_crime  (transaction grain, atomic)
CREATE TABLE dw.fact_crime (
  crime_pk                 BIGINT  GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  crime_id                 BIGINT      NOT NULL UNIQUE,    -- source 'id'
  case_number              TEXT,                            -- degenerate
  occurrence_date_key      INTEGER     NOT NULL REFERENCES dw.dim_date,
  occurrence_time_key      SMALLINT    NOT NULL REFERENCES dw.dim_time_of_day,
  report_date_key          INTEGER     NOT NULL REFERENCES dw.dim_date,
  location_key             BIGINT      NOT NULL REFERENCES dw.dim_location,
  crime_type_key           BIGINT      NOT NULL REFERENCES dw.dim_crime_type,
  weather_key              BIGINT      NOT NULL REFERENCES dw.dim_weather,
  flags_key                SMALLINT    NOT NULL REFERENCES dw.dim_crime_flags,
  -- additive measures
  incident_count           SMALLINT    NOT NULL DEFAULT 1,
  is_arrest                SMALLINT    NOT NULL,            -- 0/1
  is_domestic              SMALLINT    NOT NULL,            -- 0/1
  hours_to_update          INTEGER,
  -- non-additive / for visualisation
  latitude                 NUMERIC(9,6),
  longitude                NUMERIC(9,6),
  temperature_celsius      NUMERIC(5,2),
  precipitation_mm         NUMERIC(6,2)
);
CREATE INDEX ix_fact_crime_date ON dw.fact_crime (occurrence_date_key);
CREATE INDEX ix_fact_crime_loc  ON dw.fact_crime (location_key);
CREATE INDEX ix_fact_crime_type ON dw.fact_crime (crime_type_key);

-- 8.3.8  fact_arrest  (optional)
CREATE TABLE dw.fact_arrest (
  arrest_pk            BIGINT  GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  cb_no                BIGINT      NOT NULL UNIQUE,
  case_number          TEXT,                                -- conforms with fact_crime
  arrest_date_key      INTEGER     NOT NULL REFERENCES dw.dim_date,
  arrest_time_key      SMALLINT    NOT NULL REFERENCES dw.dim_time_of_day,
  arrestee_key         BIGINT      REFERENCES dw.dim_arrestee,
  arrest_count         SMALLINT    NOT NULL DEFAULT 1,
  charge_count         SMALLINT    NOT NULL
);

-- 8.3.9  bridge_arrest_charge
CREATE TABLE dw.bridge_arrest_charge (
  arrest_pk        BIGINT      NOT NULL REFERENCES dw.fact_arrest,
  crime_type_key   BIGINT      NOT NULL REFERENCES dw.dim_crime_type,
  charge_position  SMALLINT    NOT NULL,
  charge_class     CHAR(2),
  charge_statute   TEXT,
  PRIMARY KEY (arrest_pk, charge_position)
);

-- 8.3.10  dim_arrestee  (SCD1)
CREATE TABLE dw.dim_arrestee (
  arrestee_key   BIGINT  GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  race           TEXT,
  -- placeholders for future enrichment if/when source adds them:
  age_band       TEXT,
  sex            TEXT
);
```

### 8.4 Surrogate Keys & Smart Keys

- All dims except `dim_date`, `dim_time_of_day`, `dim_crime_flags` use
  identity surrogate keys.
- `dim_date` uses a `YYYYMMDD` **smart key** (Lecture 02 slide 61) — lets us
  partition `fact_crime` by `occurrence_date_key / 10000` (year) without a
  date join.
- `dim_time_of_day` uses 0–23 directly (a tiny smart key).
- `dim_crime_flags` uses 0–4 — `0` = unknown, `1` = (false, false), `2` =
  (true, false), `3` = (false, true), `4` = (true, true).

### 8.5 Special "Unknown" Rows

Per Lecture 02 slide 67 and Lecture 03 slide 23, every dim has a
**reserved-key row** to absorb null FKs without dropping fact rows:

| Dim | Reserved row(s) |
|---|---|
| `dim_date` | `0` = "Unknown date" |
| `dim_time_of_day` | (no unknown — hour can always be derived) |
| `dim_location` | `0` = "Unknown community/district" (used when `community_area` is NULL — observed in our sample row 3) |
| `dim_crime_type` | `0` = "Unknown IUCR" |
| `dim_weather` | `-1` = "Weather observation not available" |
| `dim_crime_flags` | `0` = "Flags unknown" |

ETL must coalesce nulls to these surrogates rather than dropping rows.

---

## 9. ETL Flow: S3 raw → RDS staging → RDS curated

This is the "Glue ETL" architecture the rubric asks for. High-level only —
detailed Glue job design is out of scope for this document.

```
+-------------------+     +-----------------+     +-------------------+     +------------+
| S3 raw zone       |     | Glue: extract   |     | RDS schema        |     | Glue: load |
| s3://...../raw/   | --> | & cast types    | --> | raw_stg.*         | --> | & dedupe   |
| chicaho_crime/    |     | (PySpark)       |     | (typed mirror)    |     |            |
| (append-only,     |     +-----------------+     +-------------------+     +------------+
|  ingest_date=...) |                                                              |
+-------------------+                                                              v
                                                                          +---------------+
                          +-------------------+   +------------------+    | RDS schema    |
                          |   IUCR codes      |   |  Socioeconomics  |    | dw_staging.*  |
                          |   Weather JSON    |-> | + Weather staging|--> | (dedup, joined)|
                          |   Arrests CSV     |   |  (PySpark)       |    +-------+-------+
                          +-------------------+   +------------------+            |
                                                                                  v
                                                                    +-----------------------+
                                                                    | Glue: SCD merge       |
                                                                    | + surrogate assign    |
                                                                    | + null → unknown coal.|
                                                                    +-----------+-----------+
                                                                                |
                                                                                v
                                                                    +-----------------------+
                                                                    | RDS schema  dw.*      |
                                                                    | (star schema for QS)  |
                                                                    +-----------------------+
```

Key ETL responsibilities (mapped to lecture concepts):

1. **Extract** (Lecture 01 slide 15): Glue PySpark reads S3 raw partitioned
   by `ingest_date`. For Chicago Crimes, the same source `id` may appear in
   multiple ingest partitions — keep the row from the latest `updated_on`.
2. **Transform** (Lecture 01 slide 15): cleanse types, coerce nulls to
   "Unknown" surrogate keys, parse `date`/`updated_on` to `YYYYMMDD`
   smart keys + hour, look up `weather_key` by `(date, hour)`, look up
   `crime_type_key` by `(iucr, occurrence_date)` against the SCD2
   history.
3. **Load** with **SCD-aware merge**: for SCD2 dims, hash the SCD2-tracked
   columns; if hash differs from `is_current = TRUE` row, expire the
   current row (`is_current = FALSE`, `scd_end_date = today`) and insert a
   new current row.

The big-data justification (rubric § 3 — 4%) sits naturally on top of this
flow:

- **Volume** — 1.5M crime + ~700k arrest + ~365k weather rows = Spark on
  Glue (Lecture 11) is the right processing engine, not single-host
  Python.
- **Variety** — CSV (crimes, IUCR, arrests, socioeconomics) + JSON
  (weather) → S3 data lake as the universal landing zone (Lecture 07).
- This is exactly the "DL & DW used together" pattern from Lecture 01
  slide 25.

Workflow automation (rubric § 4 — 1%) is already partly implemented:
EventBridge Scheduler → Lambda for daily Chicago Crimes ingest. The Glue
ETL jobs can be chained via Glue Workflows or an Airflow DAG (Lecture 13)
once the design here is approved.

---

## 10. Deviations from `CLAUDE.md` and Open Questions

### 10.1 Deviations

`CLAUDE.md` proposes a single `dim_time` covering both calendar and hour
attributes. **This design splits it into `dim_date` and `dim_time_of_day`**,
following Lecture 02 slide 41 (~24× smaller table). All other table names
(`fact_crime`, `dim_location`, `dim_crime_type`, `dim_weather`,
`dim_arrestee`) are kept identical to `CLAUDE.md`.

`CLAUDE.md` mentions an "arrest bridge" — this document specifies it as
`bridge_arrest_charge` connecting `fact_arrest` to `dim_crime_type`, *not*
`dim_arrestee`. The arrestee is a single dim per arrest event; the multi-
valued attribute is the *charges*, not the arrestees.

### 10.2 Open Questions

1. **Is `fact_arrest` required for V1?** The rubric only requires ≥ 1 fact
   table. Including it strengthens the bus matrix but adds ETL work. If
   skipped, the bus matrix collapses to one row but conformance is still
   demonstrable inside `fact_crime` (e.g., `dim_date` role-playing).
2. **How many socioeconomic snapshots will we ingest?** The richer
   `dim_location` SCD2 history is, the more compelling the SCD argument
   becomes. Recommend at least 3 snapshots (2018, 2021, 2024) so we have
   visibly versioned rows.
3. **Time grain — hourly or sub-hourly?** Crime timestamps go to the
   second; weather is hourly. Joining at hour grain loses ~no information
   for analytical questions and matches weather. Confirm.
4. **Holidays for `is_us_holiday`** — use a static lookup or import from
   `python-holidays`? Decision affects ETL idempotency.
5. **Aurora PostgreSQL vs RDS PostgreSQL?** RDS is enough at our row
   counts; Aurora is the upgrade if QuickSight users hit slow scans.

### 10.3 Acceptance Checklist (maps back to §3.0 questions)

- [ ] `fact_crime` loaded at incident grain with all conformed FKs populated.
- [ ] `dim_date` smart-keyed and prepopulated for 2018-01-01 through today.
- [ ] `dim_location` shows ≥ 2 SCD2 versions for at least one community area.
- [ ] `dim_crime_type` shows ≥ 1 historical version (an IUCR row going inactive).
- [ ] All Q1–Q5 queries from §3.0 return non-empty, sensible answers from
      QuickSight.
- [ ] No fact row dropped due to NULL FK (all coalesced to "Unknown" rows).
- [ ] Re-running the daily ingest is idempotent (re-fetched dates produce no
      duplicate fact rows).
