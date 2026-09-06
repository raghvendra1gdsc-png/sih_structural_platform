"""ingestion/sources — Information source adapters."""
from ingestion.sources.base import InformationSource, SourceHealth
from ingestion.sources.reddit import RedditSource
from ingestion.sources.gdelt import GDELTSource

__all__ = ["InformationSource", "SourceHealth", "RedditSource", "GDELTSource"]
