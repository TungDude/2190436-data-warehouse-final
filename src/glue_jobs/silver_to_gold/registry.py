"""Target -> handler-list dispatch for the silver->gold Glue job.

Two top-level targets:

* ``"dims"`` runs every dim loader module in order. Dim loaders that lack a
  feeder source today are no-op stubs (they log and return zero counts).
* ``"facts"`` runs every fact loader module. ``fact_crime`` resolves FKs
  against the dim tables produced by the dims target, so the workflow
  schedules dims to complete before facts via a CONDITIONAL trigger.

Excluded from the registry on purpose:

* ``dim_date``       — seeded once by ``sql/dw_seed.sql`` (SCD0 calendar).
* ``dim_time_of_day`` — same (SCD0, 24 rows).
* ``dim_crime_flags`` — same (junk dim, 5 rows).

Each dim loader exposes ``DIM_NAME``, ``NATURAL_KEY``, ``TRACKED_COLS``,
``SCD_TYPE`` and ``load(spark, jdbc_props, silver_database)``.
Each fact loader exposes ``FACT_NAME``, ``NATURAL_KEY`` and the same
``load`` signature.
"""

from __future__ import annotations

# Dual-import pattern (see bronze_to_silver/registry.py for rationale).
try:  # pragma: no cover
    from dimensions import dim_arrestee, dim_crime_type, dim_location, dim_weather
    from facts import chicago_crime
except ImportError:  # pragma: no cover
    from .dimensions import dim_arrestee, dim_crime_type, dim_location, dim_weather
    from .facts import chicago_crime


TARGETS = {
    "dims": [
        dim_location,
        dim_crime_type,
        dim_weather,
        dim_arrestee,
    ],
    "facts": [
        chicago_crime,
    ],
}


def get(target: str):
    """Return the list of loader modules for *target*.

    Raises ``ValueError`` with a helpful message when *target* is unknown.
    """
    if target not in TARGETS:
        known = ", ".join(sorted(TARGETS))
        raise ValueError(
            f"Unknown target '{target}'. Known targets: [{known}]."
        )
    return TARGETS[target]
