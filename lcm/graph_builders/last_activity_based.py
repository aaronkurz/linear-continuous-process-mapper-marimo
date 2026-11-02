import networkx as nx
from collections import defaultdict
from typing import List

from .abstract_graph_builder import AbstractGraphBuilder


class LastActivityBasedGraphBuilder(AbstractGraphBuilder):
    @property
    def name(self) -> str:
        return "Last-Activity-Based Graph"

    def build(
        self, variants: List[List[str]], allow_loops: bool = True
    ) -> nx.MultiDiGraph:
        """
        Build a graph where each node is the last activity executed in the prefix.
        Edges represent direct transitions between last activities.
        """
        transition_counts = defaultdict(int)
        node_weights = defaultdict(int)  # Total times each activity appears as last
        START_NODE = "START"

        total_cases = len(variants)

        for activities in variants:
            prev_activity = START_NODE

            for activity in activities:
                transition_key = (prev_activity, activity)
                if prev_activity != activity or allow_loops:
                    transition_counts[transition_key] += 1
                    node_weights[activity] += 1

                prev_activity = activity

        G = nx.MultiDiGraph()

        # START node weight = total number of cases
        G.add_node(
            START_NODE,
            weight=total_cases,
            label="START",
            last_activity=None,
        )

        # Add activity nodes
        for activity, weight in node_weights.items():
            G.add_node(
                activity,
                weight=weight,
                label=activity,
                last_activity=activity,
            )

        # Add edges
        for (from_activity, to_activity), count in transition_counts.items():
            G.add_edge(
                from_activity,
                to_activity,
                weight=count,
                activity=to_activity,
            )

        return G
