
from abc import ABC, abstractmethod
import networkx as nx
import numpy as np

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
    def __init__(self, G, inverse=False):
        print(f"Calculating Degree Centrality (Inverse={inverse})...")
        centrality = nx.degree_centrality(G)
        ranked_nodes = sorted(centrality, key=centrality.get, reverse=not inverse)
        super().__init__(ranked_nodes)

class BetweennessStrategy(StaticTargetedStrategy):
    def __init__(self, G, inverse=False):
        print(f"Calculating Betweenness Centrality (Inverse={inverse})...")
        centrality = nx.betweenness_centrality(G)
        ranked_nodes = sorted(centrality, key=centrality.get, reverse=not inverse)
        super().__init__(ranked_nodes)

class ArticulationPointStrategy(StaticTargetedStrategy):
    def __init__(self, G):
        print("Identifying Articulation Points strategy...")
        # Hybrid Strategy: Articulation Points first (sorted by degree), then High Degree
        articulation_points = set(nx.articulation_points(G))
        degree_cent = nx.degree_centrality(G)
        
        # Sort Articulation Points by Degree
        ap_list = sorted([n for n in articulation_points], key=degree_cent.get, reverse=True)
        
        # Sort Non-Articulation Points by Degree
        others = sorted([n for n in degree_cent if n not in articulation_points], key=degree_cent.get, reverse=True)
        
        super().__init__(ap_list + others)
