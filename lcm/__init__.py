"""Linear continuous process maps as Plotly Sankey figures.

    lcm_service = lcm.get_service(lcm.load_event_log("logs/log.csv"))
    figure, metadata = lcm_service.generate(map_type="sequence_based")
"""

import pandas as pd

from lcm.constants import MapType
from lcm.data.data_loader import LOG_SUFFIXES, load_event_log
from lcm.data.data_processor import DataProcessor
from lcm.domain.graph_analyzer import GraphAnalyzer
from lcm.graph_builders import (
    LastActivityBasedGraphBuilder,
    SequenceBasedPrefixTreeBuilder,
    SetBasedPrefixGraphBuilder,
)
from lcm.services.graph_service import GraphService
from lcm.services.process_analytics_service import ProcessAnalyticsService

__all__ = [
    "LOG_SUFFIXES",
    "MapType",
    "ProcessAnalyticsService",
    "get_service",
    "load_event_log",
]


def get_service(event_log: pd.DataFrame) -> ProcessAnalyticsService:
    """Create a service for `event_log`; `generate` then draws maps from it."""
    graph_service = GraphService(
        {
            MapType.SET_BASED: SetBasedPrefixGraphBuilder(),
            MapType.SEQUENCE_BASED: SequenceBasedPrefixTreeBuilder(),
            MapType.LAST_ACTIVITY_BASED: LastActivityBasedGraphBuilder(),
        }
    )
    return ProcessAnalyticsService(
        event_log=event_log,
        data_processor=DataProcessor(),
        graph_service=graph_service,
        graph_analyzer=GraphAnalyzer(),
    )
