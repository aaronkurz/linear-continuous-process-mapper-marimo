import pandas as pd
from typing import List, Tuple, Union
import plotly.graph_objects as go
from core.data.data_processor import DataProcessor
from core.services.graph_service import GraphService
from core.domain.graph_analyzer import GraphAnalyzer
from core.visualization.sankey_visualizer import SankeyVisualizer
from core.constants import ACTIVITY_COL


class ProcessAnalyticsService:
    """Orchestrates the analytics pipeline"""

    def __init__(
        self,
        event_log: pd.DataFrame,
        data_processor: DataProcessor,
        graph_service: GraphService,
        graph_analyzer: GraphAnalyzer,
    ):
        self.raw_log = event_log
        self.data_processor = data_processor
        self.graph_service = graph_service
        self.graph_analyzer = graph_analyzer

        self.base_log = self.data_processor.prepare_base_log(self.raw_log)

    def get_all_activities(self) -> List[str]:
        return sorted(self.base_log[ACTIVITY_COL].unique())

    def generate_sankey_figure(
        self,
        selected_activities: List[str],
        builder_key: str,
        merge_threshold: int = None,
        allow_loops: bool = True,
        visualize_empty_cases: bool = True,
    ) -> Tuple[go.Figure, Union[dict, None]]:
        if not selected_activities:
            return go.Figure(), None

        filtered_log, removed_cases = self.data_processor.filter_by_activities(
            self.base_log, selected_activities
        )
        if filtered_log.empty:
            return go.Figure(), None
        
        case_log = self.data_processor.create_case_log_with_variants(
            filtered_log, selected_activities, removed_cases, visualize_empty_cases
        )
        if case_log.empty:
            return go.Figure(), None

        G = self.graph_service.build_graph(
            case_log, "seq_variant", builder_key, allow_loops=allow_loops
        )

        if merge_threshold is not None:
            G = self.graph_service.simplify_graph(G, merge_threshold)

        G = self.graph_analyzer.enrich_graph_with_metrics(G)

        # Create visualizer with selected activities for legend
        visualizer = SankeyVisualizer(all_activities=selected_activities)
        return visualizer.create_figure(G), {
            "nodes_leakage_gt_0": G.graph.get("leakage_gt_0_count", 0),
            "terminal_nodes": G.graph.get("terminal_count", 0),
            "total_nodes": G.number_of_nodes(),
            "empty_cases": len(removed_cases)
            }
    
    def generate_metadata_chart(self, metadata: Union[dict, None], visualize_empty_cases_enabled: bool) -> go.Figure:
        if metadata is None:
            return go.Figure()
        chart_metadata = {
            "leakage_gt_0_count_wo_term": metadata.get("nodes_leakage_gt_0", 0) - metadata.get("terminal_nodes", 0),
            "terminal_nodes": metadata.get("terminal_nodes", 0),
            "start_empty_case_nodes": 2 if visualize_empty_cases_enabled and metadata.get("empty_cases", 0) > 0 else 1,
            "other_nodes": metadata.get("total_nodes", 0) - metadata.get("nodes_leakage_gt_0", 0) - (2 if visualize_empty_cases_enabled and metadata.get("empty_cases", 0) > 0 else 1),
        }

        bar_labels = ["Leakage > 0 w/o Termin.", "Terminal Nodes", "START/EMPTY TRACE Nodes", "Other Nodes"]
        bar_values = [
            chart_metadata["leakage_gt_0_count_wo_term"],
            chart_metadata["terminal_nodes"],
            chart_metadata["start_empty_case_nodes"],
            chart_metadata["other_nodes"],
        ]
        bar_colors = ["grey", "black", "white", "lightblue"]

        fig = go.Figure(
            data=[
                go.Bar(
                    x=bar_labels,
                    y=bar_values,
                    marker=dict(
                        color=bar_colors,
                        line=dict(color="black", width=1),
                    ),
                )
            ],
            layout=go.Layout(
                title="Node Metrics Distribution",
                xaxis=dict(title="Category"),
                yaxis=dict(title="Count"),
                showlegend=False,
            ),
        )
        return fig

    @staticmethod
    def summarize_metadata(metadata: Union[dict, None]) -> Union[dict, None]:
        """Framework-agnostic metadata summary, shared by all frontends."""
        if metadata is None:
            return None
        return {
            "Total Nodes": metadata.get("total_nodes", 0),
            "Nodes with Leakage > 0": metadata.get("nodes_leakage_gt_0", 0),
            "Terminal Nodes": metadata.get("terminal_nodes", 0),
        }

    def generate_metadata_table(self, metadata: Union[dict, None]):
        # Dash is imported lazily so that the analytics core stays importable
        # in non-Dash frontends, such as the marimo notebook.
        from dash import html
        import dash_bootstrap_components as dbc

        table_metadata = self.summarize_metadata(metadata)
        if table_metadata is None:
            return None

        table_rows = [html.Tr([html.Th(k), html.Td(str(v))]) for k, v in table_metadata.items()]
        metadata_table = dbc.Table([html.Tbody(table_rows)], bordered=True, hover=True, size="sm")
        return metadata_table