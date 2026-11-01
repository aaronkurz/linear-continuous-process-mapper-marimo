import pandas as pd
from typing import Dict, List, Optional, Tuple
import plotly.graph_objects as go
from lcm.constants import MapType
from lcm.data.data_processor import DataProcessor
from lcm.services.graph_service import GraphService
from lcm.domain.graph_analyzer import GraphAnalyzer
from lcm.visualization.sankey_visualizer import SankeyVisualizer


class ProcessAnalyticsService:
    """Orchestrates the analytics pipeline"""

    def __init__(
        self,
        event_log: pd.DataFrame,
        data_processor: DataProcessor,
        graph_service: GraphService,
        graph_analyzer: GraphAnalyzer,
    ):
        self.data_processor = data_processor
        self.graph_service = graph_service
        self.graph_analyzer = graph_analyzer

        self.traces = self.data_processor.prepare_traces(event_log)

    def get_all_activities(self) -> List[str]:
        return sorted({act for trace in self.traces for act in trace})

    def generate(
        self,
        *,
        activities: Optional[List[str]] = None,
        map_type: str = MapType.SET_BASED,
        allow_loops: bool = True,
        visualize_empty_cases: bool = True,
        folds: Optional[Dict[str, List[str]]] = None,
    ) -> Tuple[go.Figure, dict]:
        """Draw a process map of the log.

        Every call starts from the full log, so maps do not affect each other.

        Args:
            activities: Activities to keep, named as they appear after folding.
                All of them if None.
            map_type: A `MapType`, or its value such as "set_based".
            allow_loops: Draw an activity that leaves the node unchanged as a
                self-loop. Has no effect on sequence-based maps, whose nodes
                never repeat.
            visualize_empty_cases: Draw the cases that have none of the selected
                activities as an "EMPTY TRACE" node.
            folds: Fold name mapped to the activities it replaces, for example
                {"Rejections": ["Rejected by A", "Rejected by B"]}.

        Returns:
            The Plotly Sankey figure, and a dict of counts describing the map.

        Raises:
            ValueError: If `map_type`, `activities` or `folds` are invalid.
        """
        map_type = MapType(map_type)
        folds = folds or {}
        selected_activities = self._resolve_activities(activities, folds)

        traces = self.data_processor.apply_folds(self.traces, folds)
        variants, empty_cases = self.data_processor.create_variants(
            traces, selected_activities, visualize_empty_cases
        )

        G = self.graph_service.build_graph(variants, map_type, allow_loops=allow_loops)
        G = self.graph_analyzer.enrich_graph_with_metrics(G)

        # Create visualizer with selected activities for legend
        visualizer = SankeyVisualizer(all_activities=selected_activities)
        return visualizer.create_figure(G), {
            "nodes_leakage_gt_0": G.graph.get("leakage_gt_0_count", 0),
            "terminal_nodes": G.graph.get("terminal_count", 0),
            "total_nodes": G.number_of_nodes(),
            "empty_cases": empty_cases,
        }

    def _resolve_activities(
        self, activities: Optional[List[str]], folds: Dict[str, List[str]]
    ) -> List[str]:
        """Check the choices against the log; return the activities to draw."""
        known = set(self.get_all_activities())
        folded = set()
        for name, members in folds.items():
            if not name.strip():
                raise ValueError("Every fold needs a name.")
            if not members:
                raise ValueError(f"Fold '{name}' has no activities.")
            self._reject(set(members) - known, f"Fold '{name}' has unknown activities")
            self._reject(set(members) & folded, f"Fold '{name}' reuses folded activities")
            folded |= set(members)
            if name in known - set(members):
                raise ValueError(f"Fold '{name}' has the name of another activity.")

        available = (known - folded) | set(folds)
        if activities is None:
            return sorted(available)
        if not activities:
            raise ValueError("Select at least one activity.")
        self._reject(
            set(activities) - available, "Unknown activities (folded ones go by fold name)"
        )
        return list(activities)

    @staticmethod
    def _reject(names: set, problem: str) -> None:
        if names:
            raise ValueError(f"{problem}: {', '.join(sorted(names))}.")

    @staticmethod
    def summarize_metadata(metadata: dict) -> dict:
        """Summary of graph metadata for display."""
        return {
            "Total Nodes": metadata["total_nodes"],
            "Nodes with Leakage > 0": metadata["nodes_leakage_gt_0"],
            "Terminal Nodes": metadata["terminal_nodes"],
            "Empty Cases": metadata["empty_cases"],
        }
