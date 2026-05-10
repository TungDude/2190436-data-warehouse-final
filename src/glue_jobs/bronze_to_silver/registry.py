"""Source -> handler dispatch for the bronze->silver Glue job.

Each handler module under :mod:`src.glue_jobs.bronze_to_silver.sources`
must export:

* ``SOURCE_NAME``           - matches ``--source`` argv (e.g. ``"chicago_crime"``).
* ``SILVER_TABLE_NAME``     - silver table folder name (silver fixes the
  bronze ``chicaho`` typo where applicable).
* ``SILVER_PARTITION_COLS`` - list of column names to partition silver by.
* ``transform(spark, bronze_root_uri) -> DataFrame`` - reads bronze inputs
  rooted at ``bronze_root_uri`` (e.g. ``"s3://bucket/raw"`` in production
  or a local path in tests).
"""

from __future__ import annotations

# Dual-import pattern (matches main.py and chicago_crime.py): when this
# module is loaded as a top-level module from inside the libs.zip on Glue,
# the package-relative form raises and we fall back to the absolute import
# against the zip-root namespace. Under pytest the package-relative form
# is the one that succeeds.
try:  # pragma: no cover
    from .sources import chicago_crime
except ImportError:  # pragma: no cover
    from sources import chicago_crime  # type: ignore[no-redef]


REGISTRY = {
    chicago_crime.SOURCE_NAME: chicago_crime,
}


def get(source: str):
    """Return the handler module for *source*.

    Raises ``ValueError`` with a helpful message listing the registered
    sources when *source* is unknown.
    """
    if source not in REGISTRY:
        known = ", ".join(sorted(REGISTRY))
        raise ValueError(
            f"Unknown source '{source}'. Known sources: [{known}]. "
            "Add a module under src/glue_jobs/bronze_to_silver/sources/ "
            "and register it in registry.REGISTRY."
        )
    return REGISTRY[source]
