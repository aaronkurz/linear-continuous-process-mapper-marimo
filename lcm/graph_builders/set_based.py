import networkx as nx
from collections import defaultdict
from typing import List

from .abstract_graph_builder import AbstractGraphBuilder


class SetBasedPrefixGraphBuilder(AbstractGraphBuilder):
    @property
    def name(self) -> str:
        return "Set-Based Prefix Graph"

    def build(
        self, variants: List[List[str]], allow_loops: bool = True
    ) -> nx.MultiDiGraph:
        """
        Build a prefix graph from a case log
        """
        state_counts = defaultdict(int)
        transitions = []  # store each transition as (from_state, to_state, activity)

        for activities in variants:
            current_state = frozenset()
            state_counts[current_state] += 1

            for i, activity in enumerate(activities):
                new_state = frozenset(activities[: i + 1])
                if current_state != new_state or allow_loops:
                    transitions.append((current_state, new_state, activity))
                    state_counts[new_state] += 1
                current_state = new_state

        G = nx.MultiDiGraph()
        # add nodes
        for state, count in state_counts.items():
            state_label = "START" if not state else "{" + ", ".join(sorted(state)) + "}"
            G.add_node(
                state, weight=count, label=state_label, activities_completed=len(state)
            )

        # group transitions by (from_state, to_state, activity) to count occurrences per activity
        transition_groups = defaultdict(int)
        for from_state, to_state, activity in transitions:
            key = (from_state, to_state, activity)
            transition_groups[key] += 1

        # add each unique (from, to, activity) as a separate edge
        for (from_state, to_state, activity), count in transition_groups.items():
            G.add_edge(
                from_state,
                to_state,
                weight=count,
                activity=activity,
            )

        return G
