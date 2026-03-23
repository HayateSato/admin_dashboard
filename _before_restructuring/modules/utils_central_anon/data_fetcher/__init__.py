"""
Data Fetcher Module

Contains modules for fetching data from various sources (InfluxDB, etc.)
"""

from .influx_fetcher import InfluxDataFetcher

__all__ = ['InfluxDataFetcher']
