-- ============================================================================
-- Chicago Crime Data Warehouse — seed rows (gold tier)
--
-- Source of truth:
--   docs/dimensional-design.md §8.4 (smart keys), §8.5 (reserved "Unknown" rows).
--
-- Idempotent: every INSERT uses ON CONFLICT DO NOTHING so re-running on an
-- already-bootstrapped database is a no-op. Runs in its own transaction after
-- dw_schema.sql succeeds (the DDL bootstrap Lambda enforces this separation).
--
-- Sections:
--   1. Reserved "Unknown" / "Not applicable" surrogate rows.
--   2. dim_date — 2018-01-01 .. 2030-12-31 with computed federal holidays.
--   3. dim_time_of_day — 24 rows, hours 0..23.
--   4. dim_crime_flags — 5 rows (0=unknown plus the 4 boolean combinations).
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Reserved "Unknown" rows per dimensional-design.md §8.5 (root dims only)
--
-- These rows absorb null FKs so fact loads never drop rows on missing
-- dimension members (Lecture 02 slide 67). The gold loader coalesces null
-- FKs to these surrogate keys.
--
-- Only the FK-free reserved rows go here; dim_weather(-1) references
-- dim_time_of_day(0) and is seeded in Section 4 after dim_time_of_day is
-- populated.
-- ----------------------------------------------------------------------------

-- dim_date(0) — "Unknown date"
INSERT INTO dw.dim_date (
    date_key, full_date, day_of_week, day_name, is_weekend, is_us_holiday,
    month_num, month_name, quarter, year, iso_week
)
VALUES (
    0, DATE '0001-01-01', 0, 'Unknown', FALSE, FALSE,
    0, 'Unknown', 0, 0, 0
)
ON CONFLICT (date_key) DO NOTHING;

-- dim_location(0) — "Unknown location"
INSERT INTO dw.dim_location (
    location_key, community_area, district, ward, beat, block,
    community_area_name, scd_start_date, scd_end_date, is_current,
    scd_version, scd_hash
)
VALUES (
    0, NULL, NULL, NULL, NULL, NULL,
    'Unknown', DATE '0001-01-01', DATE '9999-12-31', TRUE,
    1, '\x00'::bytea
)
ON CONFLICT (location_key) DO NOTHING;

-- dim_crime_type(0) — "Unknown IUCR"
INSERT INTO dw.dim_crime_type (
    crime_type_key, iucr, primary_type, description, fbi_code,
    index_code, active, scd_start_date, scd_end_date, is_current,
    scd_version, scd_hash
)
VALUES (
    0, 'UNKN', 'Unknown', 'Unknown', NULL,
    NULL, FALSE, DATE '0001-01-01', DATE '9999-12-31', TRUE,
    1, '\x00'::bytea
)
ON CONFLICT (crime_type_key) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 2. dim_date — 2018-01-01 .. 2030-12-31
--
-- Smart key YYYYMMDD per Lecture 02 slide 61. Federal holiday detection done
-- in pure SQL via two CTEs:
--   - fixed_holidays: month/day matches (New Year, Independence, Christmas,
--     Veterans Day, Juneteenth from 2021)
--   - floating_holidays: Nth-weekday-of-month rules computed with DOW + a
--     day-of-month range that uniquely identifies the Nth occurrence.
--
-- E.g., MLK Day = 3rd Monday of January = a date in January where DOW=1
-- (Monday) and day-of-month is 15..21 (only one such date per year).
--
-- Veterans Day uses the actual statute date (Nov 11), not the federal
-- observance shift; analytical queries on weekday distribution stay correct.
-- ----------------------------------------------------------------------------

WITH calendar AS (
    SELECT d::date AS full_date
      FROM generate_series(DATE '2018-01-01', DATE '2030-12-31', INTERVAL '1 day') AS d
),
fixed_holidays AS (
    SELECT d::date AS holiday_date
      FROM generate_series(DATE '2018-01-01', DATE '2030-12-31', INTERVAL '1 day') AS d
     WHERE (EXTRACT(MONTH FROM d) = 1  AND EXTRACT(DAY FROM d) = 1)
        OR (EXTRACT(MONTH FROM d) = 7  AND EXTRACT(DAY FROM d) = 4)
        OR (EXTRACT(MONTH FROM d) = 11 AND EXTRACT(DAY FROM d) = 11)
        OR (EXTRACT(MONTH FROM d) = 12 AND EXTRACT(DAY FROM d) = 25)
        OR (EXTRACT(YEAR FROM d) >= 2021
            AND EXTRACT(MONTH FROM d) = 6
            AND EXTRACT(DAY FROM d) = 19)
),
floating_holidays AS (
    -- MLK Day: 3rd Monday of January
    SELECT d::date AS holiday_date
      FROM generate_series(DATE '2018-01-01', DATE '2030-12-31', INTERVAL '1 day') AS d
     WHERE EXTRACT(MONTH FROM d) = 1
       AND EXTRACT(DOW   FROM d) = 1
       AND EXTRACT(DAY   FROM d) BETWEEN 15 AND 21
    UNION ALL
    -- Presidents Day: 3rd Monday of February
    SELECT d::date
      FROM generate_series(DATE '2018-01-01', DATE '2030-12-31', INTERVAL '1 day') AS d
     WHERE EXTRACT(MONTH FROM d) = 2
       AND EXTRACT(DOW   FROM d) = 1
       AND EXTRACT(DAY   FROM d) BETWEEN 15 AND 21
    UNION ALL
    -- Memorial Day: last Monday of May
    SELECT d::date
      FROM generate_series(DATE '2018-01-01', DATE '2030-12-31', INTERVAL '1 day') AS d
     WHERE EXTRACT(MONTH FROM d) = 5
       AND EXTRACT(DOW   FROM d) = 1
       AND EXTRACT(DAY   FROM d) BETWEEN 25 AND 31
    UNION ALL
    -- Labor Day: 1st Monday of September
    SELECT d::date
      FROM generate_series(DATE '2018-01-01', DATE '2030-12-31', INTERVAL '1 day') AS d
     WHERE EXTRACT(MONTH FROM d) = 9
       AND EXTRACT(DOW   FROM d) = 1
       AND EXTRACT(DAY   FROM d) BETWEEN 1 AND 7
    UNION ALL
    -- Columbus Day: 2nd Monday of October
    SELECT d::date
      FROM generate_series(DATE '2018-01-01', DATE '2030-12-31', INTERVAL '1 day') AS d
     WHERE EXTRACT(MONTH FROM d) = 10
       AND EXTRACT(DOW   FROM d) = 1
       AND EXTRACT(DAY   FROM d) BETWEEN 8 AND 14
    UNION ALL
    -- Thanksgiving: 4th Thursday of November
    SELECT d::date
      FROM generate_series(DATE '2018-01-01', DATE '2030-12-31', INTERVAL '1 day') AS d
     WHERE EXTRACT(MONTH FROM d) = 11
       AND EXTRACT(DOW   FROM d) = 4
       AND EXTRACT(DAY   FROM d) BETWEEN 22 AND 28
),
all_holidays AS (
    SELECT holiday_date FROM fixed_holidays
    UNION
    SELECT holiday_date FROM floating_holidays
)
INSERT INTO dw.dim_date (
    date_key, full_date, day_of_week, day_name, is_weekend, is_us_holiday,
    month_num, month_name, quarter, year, iso_week
)
SELECT
    to_char(c.full_date, 'YYYYMMDD')::integer       AS date_key,
    c.full_date,
    EXTRACT(DOW FROM c.full_date)::smallint         AS day_of_week,
    trim(to_char(c.full_date, 'Day'))               AS day_name,
    EXTRACT(DOW FROM c.full_date) IN (0, 6)         AS is_weekend,
    h.holiday_date IS NOT NULL                      AS is_us_holiday,
    EXTRACT(MONTH FROM c.full_date)::smallint       AS month_num,
    trim(to_char(c.full_date, 'Month'))             AS month_name,
    EXTRACT(QUARTER FROM c.full_date)::smallint     AS quarter,
    EXTRACT(YEAR FROM c.full_date)::smallint        AS year,
    EXTRACT(WEEK FROM c.full_date)::smallint        AS iso_week
  FROM calendar c
  LEFT JOIN all_holidays h ON h.holiday_date = c.full_date
ON CONFLICT (date_key) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 3. dim_time_of_day — 24 hourly buckets
--
-- period_of_day buckets follow common social conventions:
--   00-04 Late Night, 05-08 Early Morning, 09-11 Morning,
--   12-16 Afternoon, 17-20 Evening, 21-23 Night.
-- ----------------------------------------------------------------------------

INSERT INTO dw.dim_time_of_day (time_key, hour_24, hour_12, am_pm, period_of_day)
SELECT
    h::smallint                                          AS time_key,
    h::smallint                                          AS hour_24,
    CASE
        WHEN h = 0       THEN 12
        WHEN h BETWEEN 1 AND 12 THEN h
        ELSE h - 12
    END::smallint                                        AS hour_12,
    CASE WHEN h < 12 THEN 'AM' ELSE 'PM' END             AS am_pm,
    CASE
        WHEN h BETWEEN 0  AND 4  THEN 'Late Night'
        WHEN h BETWEEN 5  AND 8  THEN 'Early Morning'
        WHEN h BETWEEN 9  AND 11 THEN 'Morning'
        WHEN h BETWEEN 12 AND 16 THEN 'Afternoon'
        WHEN h BETWEEN 17 AND 20 THEN 'Evening'
        ELSE                           'Night'
    END                                                  AS period_of_day
  FROM generate_series(0, 23) AS h
ON CONFLICT (time_key) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 4. dim_weather(-1) — "Weather observation not available"
--
-- Seeded after dim_time_of_day and dim_date so the FK constraints resolve.
-- Per dimensional-design.md §8.5, surrogate key -1 marks "not applicable".
-- ----------------------------------------------------------------------------

INSERT INTO dw.dim_weather (
    weather_key, obs_date_key, obs_hour, weather_code_wmo,
    weather_category, temp_band, precip_band
)
VALUES (
    -1, 0, 0, NULL,
    'Unavailable', 'Unavailable', 'Unavailable'
)
ON CONFLICT (weather_key) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 5. dim_crime_flags — junk dimension
--
-- Five rows per dimensional-design.md §8.4: surrogate 0 = unknown, then the
-- four (is_arrest, is_domestic) boolean combinations.
-- ----------------------------------------------------------------------------

INSERT INTO dw.dim_crime_flags (flags_key, is_arrest, is_domestic, label)
VALUES
    (0, NULL,  NULL,  'Unknown'),
    (1, FALSE, FALSE, 'No Arrest, Non-Domestic'),
    (2, TRUE,  FALSE, 'Arrest, Non-Domestic'),
    (3, FALSE, TRUE,  'No Arrest, Domestic'),
    (4, TRUE,  TRUE,  'Arrest, Domestic')
ON CONFLICT (flags_key) DO NOTHING;
