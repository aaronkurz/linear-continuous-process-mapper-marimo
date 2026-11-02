import networkx as nx
from typing import Dict, List
from lcm.constants import MapType
from lcm.graph_builders import AbstractGraphBuilder


class GraphService:
    """Handles graph construction."""

    def __init__(self, graph_builders: Dict[MapType, AbstractGraphBuilder]):
        self.graph_builders = graph_builders

    def build_graph(
        self,
        variants: List[List[str]],
        map_type: MapType,
        allow_loops: bool = True,
    ) -> nx.MultiDiGraph:
        return self.graph_builders[map_type].build(variants, allow_loops=allow_loops)
