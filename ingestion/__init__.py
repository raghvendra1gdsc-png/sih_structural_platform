"""
ingestion/
==========
Data ingestion layer for the Disaster Structural Intelligence Platform.

Phase 0:
    schemas                    — Pydantic canonical data models
    synthetic_report_generator — Demo data generator

Phase 1 additions:
    usgs_ingester              — USGS earthquake event fetch + geographic classification
    normaliser                 — RawReport → NormalizedReport pipeline
"""
from ingestion.usgs_ingester import DataSourceUnavailableError  # re-export

__all__ = ["DataSourceUnavailableError"]
