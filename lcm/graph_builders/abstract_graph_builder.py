import networkx as nx
from abc import ABC, abstractmethod
from typing import List


class AbstractGraphBuilder(ABC):
    """Abstract base class for all graph builder"""

    @abstractmethod
    def build(
        self, variants: List[List[str]], allow_loops: bool = True
    ) -> nx.MultiDiGraph:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """User friendly name for the builder strategy"""
