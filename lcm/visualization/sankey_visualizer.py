import networkx as nx
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any

from lcm.constants import EMPTY_TRACE


class SankeyVisualizer:
    """Converts an enriched graph into a Plotly Sankey figure."""

    def __init__(self, all_activities=None):
        self.all_activities = all_activities or []

    def create_figure(self, G: nx.MultiDiGraph) -> go.Figure:
        if not G.nodes:
            return go.Figure()

        data = self._prepare_sankey_data(G)
        return self._build_figure(data)

    def _prepare_sankey_data(self, G: nx.MultiDiGraph) -> Dict[str, Any]:
        node_to_idx = {}
        nodes_info = []
        node_custom_data = []

        # Use all activities for consistent coloring, fall back to graph activities if not provided
        if self.all_activities:
            activities_for_coloring = sorted(self.all_activities)
        else:
            activities_for_coloring = sorted(
                {data.get("activity", "Unknown") for _, _, data in G.edges(data=True)}
            )

        activity_colors = px.colors.qualitative.Plotly
        activity_color_map = {
            act: activity_colors[i % len(activity_colors)]
            for i, act in enumerate(activities_for_coloring)
        }
        activity_color_map[EMPTY_TRACE] = "lightgrey"

        # Process nodes
        for node, data in G.nodes(data=True):
            weight = data.get("weight", 0)
            if weight <= 0:
                continue

            node_idx = len(nodes_info)
            node_to_idx[node] = node_idx

            metrics = data.get("metrics", {})
            incoming = metrics.get("incoming_flow", 0)
            outgoing = metrics.get("outgoing_flow", 0)
            leakage = metrics.get("leakage", 0)

            # Determine color based on semantic state
            if data["label"] == "START":
                node_color = "white"
            elif data["label"] in [EMPTY_TRACE, f"{{{EMPTY_TRACE}}}"]:
                node_color = "white"
            elif metrics.get("is_terminal", False):
                node_color = "black"
            elif metrics.get("is_balanced", False):
                node_color = "lightgrey"
            else:
                node_color = "dimgrey"

            nodes_info.append({"label": data["label"], "color": node_color})
            node_custom_data.append(
                {
                    "node_label": data["label"],
                    "incoming_flow": incoming,
                    "outgoing_flow": outgoing,
                    "leakage": leakage,
                }
            )

        # Process edges
        sources, targets, values, link_labels, link_colors = [], [], [], [], []
        for src, tgt, key, data in G.edges(data=True, keys=True):
            src_idx = node_to_idx.get(src)
            tgt_idx = node_to_idx.get(tgt)
            if src_idx is None or tgt_idx is None:
                continue

            activity = data.get("activity", "Unknown")
            weight = data["weight"]

            sources.append(src_idx)
            targets.append(tgt_idx)
            values.append(weight)
            link_labels.append(f"{activity} ({weight})")
            link_colors.append(activity_color_map[activity])

        return {
            "nodes_info": nodes_info,
            "node_custom_data": node_custom_data,
            "sources": sources,
            "targets": targets,
            "values": values,
            "link_labels": link_labels,
            "link_colors": link_colors,
            "activity_color_map": activity_color_map,
        }

    def _build_figure(self, data: Dict[str, Any]) -> go.Figure:
        node_labels = [n["label"] for n in data["nodes_info"]]
        node_colors = [n["color"] for n in data["nodes_info"]]

        fig = go.Figure(
            data=[
                go.Sankey(
                    textfont=dict(color="rgba(0,0,0,0)", size=1),
                    node=dict(
                        pad=15,
                        thickness=20,
                        line=dict(color="black", width=0.5),
                        label=node_labels,
                        color=node_colors,
                        customdata=data["node_custom_data"],
                        hovertemplate=(
                            "<b>%{customdata.node_label}</b><br>"
                            "Incoming Flow: %{customdata.incoming_flow}<br>"
                            "Outgoing Flow: %{customdata.outgoing_flow}<br>"
                            "Leakage: %{customdata.leakage}<br>"
                        ),
                    ),
                    link=dict(
                        source=data["sources"],
                        target=data["targets"],
                        value=data["values"],
                        label=data["link_labels"],
                        color=data["link_colors"],
                        hovertemplate="%{label}<br>Cases: %{value}<extra></extra>",
                    ),
                )
            ]
        )

        fig.update_layout(
            font_size=12,
            height=700,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            legend=dict(
                title="Activities",
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.05,
                bgcolor="rgba(255, 255, 255, 0.8)",
                bordercolor="gray",
                borderwidth=1,
            ),
        )

        # Add dummy traces for legend
        for activity, color in data["activity_color_map"].items():
            fig.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode="markers",
                    marker=dict(size=10, color=color),
                    legendgroup=activity,
                    showlegend=True,
                    name=activity,
                )
            )

        fig.update_xaxes(showgrid=False, zeroline=False, showticklabels=False)
        fig.update_yaxes(showgrid=False, zeroline=False, showticklabels=False)

        return fig
