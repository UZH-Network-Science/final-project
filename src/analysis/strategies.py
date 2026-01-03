
from abc import ABC, abstractmethod
import networkx as nx
import numpy as np
from src.analysis.centrality_cache import get_cache

class AttackStrategy(ABC):
    @abstractmethod
    def select_nodes(self, G, num_to_remove):
        """Returns a list of nodes to remove."""
        pass

class RandomStrategy(AttackStrategy):
    def select_nodes(self, G, num_to_remove):
        nodes = list(G.nodes())
        if num_to_remove >= len(nodes):
            return nodes
        return np.random.choice(nodes, num_to_remove, replace=False).tolist()

class StaticTargetedStrategy(AttackStrategy):
    def __init__(self, ranked_nodes):
        """
        Base class for strategies that pre-calculate a removal order.
        """
        self.ranked_nodes = ranked_nodes
        
    def select_nodes(self, G, num_to_remove):
        return self.ranked_nodes[:num_to_remove]

class DegreeStrategy(StaticTargetedStrategy):
    def __init__(self, G, inverse=False, force_recompute=False):
        print(f"Loading Degree Centrality (Inverse={inverse})...")
        cache = get_cache()
        ranked_nodes = cache.get_sorted_node_ids(G, 'degree', inverse=inverse, 
                                                  force_recompute=force_recompute)
        super().__init__(ranked_nodes)

class BetweennessStrategy(StaticTargetedStrategy):
    def __init__(self, G, inverse=False, force_recompute=False):
        print(f"Loading Betweenness Centrality (Inverse={inverse})...")
        cache = get_cache()
        ranked_nodes = cache.get_sorted_node_ids(G, 'betweenness', inverse=inverse,
                                                  force_recompute=force_recompute)
        super().__init__(ranked_nodes)

class ArticulationPointStrategy(StaticTargetedStrategy):
    def __init__(self, G, force_recompute=False):
        print("Loading Articulation Points strategy...")
        cache = get_cache()
        ranked_nodes = cache.get_sorted_node_ids(G, 'articulation', inverse=False,
                                                  force_recompute=force_recompute)
        super().__init__(ranked_nodes)
