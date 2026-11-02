import networkx as nx
from collections import defaultdict
from typing import List

from .abstract_graph_builder import AbstractGraphBuilder


class SequenceBasedPrefixTreeBuilder(AbstractGraphBuilder):
    @property
    def name(self) -> str:
        return "Sequence-Based Prefix Tree"

    def build(
        self, variants: List[List[str]], allow_loops: bool = True
    ) -> nx.MultiDiGraph:
        """
        Build a prefix tree where each node is a unique sequence (tuple) of activities.
        No merging: A->B->C is different from B->A->C.
        """
        state_counts = defaultdict(int)
        transition_info = defaultdict(lambda: {"count": 0, "activity": None})

        for activities in variants:
            current_state = tuple()  # empty prefix
            state_counts[current_state] += 1

            for i, activity in enumerate(activities):
                # Build prefix up to current position
                new_state = tuple(activities[: i + 1])

                # Always add edge (even if same state, if loops allowed)
                if current_state != new_state or allow_loops:
                    transition_key = (current_state, new_state)
                    transition_info[transition_key]["count"] += 1
                    transition_info[transition_key]["activity"] = activity

                current_state = new_state
                state_counts[current_state] += 1

        G = nx.MultiDiGraph()

        for state, count in state_counts.items():
            # Label: START for empty, otherwise "A → B → C"
            state_label = "START" if len(state) == 0 else " → ".join(state)
            G.add_node(
                state,
                weight=count,
                label=state_label,
                sequence_length=len(state),
                activities=list(state),
            )

        for (from_state, to_state), info in transition_info.items():
            if info["count"] > 0 and from_state in G.nodes and to_state in G.nodes:
                G.add_edge(
                    from_state,
                    to_state,
                    weight=info["count"],
                    activity=info["activity"],
                )

        return G
