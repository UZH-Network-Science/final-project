"""
Centrality caching module for expensive NetworkX computations.

This module provides disk-based caching for graph centrality metrics
to avoid recomputation during Voila notebook execution and attack simulations.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Set, List, Optional, Any, Tuple
import networkx as nx

# Compute project root from module location (src/analysis/centrality_cache.py -> project root)
_MODULE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _MODULE_DIR.parent.parent
_DEFAULT_CACHE_DIR = _PROJECT_ROOT / "metrics" / "centrality_cache"


class CentralityCache:
    """
    Caches expensive centrality computations to disk.
    
    The cache key is derived from a stable hash of the graph structure
    (node count, edge count, and sorted edge list hash).
    """
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _graph_hash(self, G: nx.Graph) -> str:
        """Generate a stable hash for the graph structure."""
        n_nodes = G.number_of_nodes()
        n_edges = G.number_of_edges()
        
        # Sort edges for deterministic hash
        edges_str = str(sorted(G.edges()))
        edges_hash = hashlib.md5(edges_str.encode()).hexdigest()[:8]
        
        return f"{n_nodes}n_{n_edges}e_{edges_hash}"
    
    def _cache_path(self, graph_hash: str, metric_name: str) -> Path:
        """Get the cache file path for a metric."""
        return self.cache_dir / f"{graph_hash}_{metric_name}.json"
    
    def _load(self, path: Path) -> Optional[Any]:
        """Load cached data from disk."""
        if path.exists():
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None
        return None
    
    def _save(self, path: Path, data: Any) -> None:
        """Save data to cache."""
        with open(path, 'w') as f:
            json.dump(data, f)
    
    def get_degree_centrality(self, G: nx.Graph, force_recompute: bool = False) -> Dict[Any, float]:
        """Get degree centrality, using cache if available."""
        graph_hash = self._graph_hash(G)
        cache_path = self._cache_path(graph_hash, "degree")
        
        if not force_recompute:
            cached = self._load(cache_path)
            if cached is not None:
                print(f"[CentralityCache] Using cached degree centrality")
                return cached
        
        print(f"[CentralityCache] Computing degree centrality...")
        result = nx.degree_centrality(G)
        result_serializable = {str(k): v for k, v in result.items()}
        self._save(cache_path, result_serializable)
        return result
    
    def get_betweenness_centrality(self, G: nx.Graph, force_recompute: bool = False) -> Dict[Any, float]:
        """Get betweenness centrality, using cache if available."""
        graph_hash = self._graph_hash(G)
        cache_path = self._cache_path(graph_hash, "betweenness")
        
        if not force_recompute:
            cached = self._load(cache_path)
            if cached is not None:
                print(f"[CentralityCache] Using cached betweenness centrality")
                return cached
        
        print(f"[CentralityCache] Computing betweenness centrality (this may take a while)...")
        result = nx.betweenness_centrality(G)
        result_serializable = {str(k): v for k, v in result.items()}
        self._save(cache_path, result_serializable)
        return result
    
    def get_articulation_points(self, G: nx.Graph, force_recompute: bool = False) -> Set[Any]:
        """Get articulation points, using cache if available."""
        graph_hash = self._graph_hash(G)
        cache_path = self._cache_path(graph_hash, "articulation")
        
        if not force_recompute:
            cached = self._load(cache_path)
            if cached is not None:
                print(f"[CentralityCache] Using cached articulation points")
                return set(cached)
        
        print(f"[CentralityCache] Computing articulation points...")
        result = set(nx.articulation_points(G))
        result_serializable = [str(n) for n in result]
        self._save(cache_path, result_serializable)
        return result
    
    def get_sorted_nodes(self, G: nx.Graph, metric: str, inverse: bool = False, 
                         force_recompute: bool = False) -> List[Tuple[Any, float]]:
        """
        Get nodes sorted by centrality metric.
        
        Args:
            G: NetworkX graph
            metric: 'degree', 'betweenness', or 'articulation'
            inverse: If True, sort ascending (target low centrality nodes)
            force_recompute: Force recalculation of centralities
            
        Returns:
            List of (node, centrality_value) tuples, sorted by centrality
        """
        if metric == 'degree':
            centrality = self.get_degree_centrality(G, force_recompute)
        elif metric == 'betweenness':
            centrality = self.get_betweenness_centrality(G, force_recompute)
        elif metric == 'articulation':
            # For articulation, use degree centrality but prioritize articulation points
            degree_cent = self.get_degree_centrality(G, force_recompute)
            articulation_pts = self.get_articulation_points(G, force_recompute)
            
            # Articulation points first (sorted by degree), then others
            ap_list = sorted([(n, degree_cent.get(str(n), degree_cent.get(n, 0))) 
                             for n in articulation_pts], 
                            key=lambda x: x[1], reverse=not inverse)
            others = sorted([(n, degree_cent.get(str(n), degree_cent.get(n, 0))) 
                            for n in G.nodes() if n not in articulation_pts],
                           key=lambda x: x[1], reverse=not inverse)
            return ap_list + others
        else:
            raise ValueError(f"Unknown metric: {metric}")
        
        # Sort by centrality value
        sorted_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=not inverse)
        return sorted_nodes
    
    def get_sorted_node_ids(self, G: nx.Graph, metric: str, inverse: bool = False,
                            force_recompute: bool = False) -> List[Any]:
        """
        Get just the node IDs sorted by centrality (for attack strategies).
        
        Returns:
            List of node IDs
        """
        sorted_with_values = self.get_sorted_nodes(G, metric, inverse, force_recompute)
        return [node for node, _ in sorted_with_values]


# Global instance for convenience
_cache_instance: Optional[CentralityCache] = None


def get_cache(cache_dir: Optional[Path] = None) -> CentralityCache:
    """Get or create the global cache instance.
    
    If cache_dir is not specified, uses the default location:
    {project_root}/metrics/centrality_cache/
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CentralityCache(cache_dir)
    return _cache_instance
