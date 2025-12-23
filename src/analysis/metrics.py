import networkx as nx
import numpy as np
import time
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
from functools import partial

from abc import ABC, abstractmethod
from src.analysis.strategies import (
    AttackStrategy, RandomStrategy, StaticTargetedStrategy,
    DegreeStrategy, BetweennessStrategy, ArticulationPointStrategy
)

# Global variable to hold the shared graph in each worker process
SHARED_GRAPH = None

def _init_worker(G):
    global SHARED_GRAPH
    SHARED_GRAPH = G



def _worker_simulation(strategy, num_to_remove, num_simulations, n_lcc, metrics):
    """
    Unified worker that delegates node selection to the Strategy.
    """
    global SHARED_GRAPH
    G = SHARED_GRAPH
    
    results = {m: [] for m in metrics}
    # Safety check
    if num_to_remove >= G.number_of_nodes():
        for m in metrics:
            results[m] = [0.0] * num_simulations
        return results

    for _ in range(num_simulations):
        G_temp = G.copy()
        
        # Strategy decides WHICH nodes to remove
        remove_targets = strategy.select_nodes(G, num_to_remove)
        G_temp.remove_nodes_from(remove_targets)
        
        # Check if graph is empty once
        is_empty = G_temp.number_of_nodes() == 0
        
        if 'lcc' in metrics:
            if not is_empty:
                try:
                    largest_cc = max(nx.connected_components(G_temp), key=len)
                    lcc_size = len(largest_cc)
                    results['lcc'].append(lcc_size / n_lcc)
                except ValueError: # Empty sequence
                     results['lcc'].append(0.0)
            else:
                results['lcc'].append(0.0)
                
        if 'efficiency' in metrics:
            if not is_empty:
                results['efficiency'].append(nx.global_efficiency(G_temp))
            else:
                results['efficiency'].append(0.0)

        if 'average_degree' in metrics:
            # (2 * E) / N
            n = G_temp.number_of_nodes()
            if n > 0:
                avg_deg = (2 * G_temp.number_of_edges()) / n
                results['average_degree'].append(avg_deg)
            else:
                results['average_degree'].append(0.0)

        if 'clustering' in metrics:
            if not is_empty:
                results['clustering'].append(nx.average_clustering(G_temp))
            else:
                results['clustering'].append(0.0)

        # Metrics that require LCC
        if 'diameter' in metrics or 'avg_path_length' in metrics:
            if not is_empty:
                # We need the subgraph for these
                try:
                    largest_cc = max(nx.connected_components(G_temp), key=len)
                    # Create subgraph only if needed, it's expensive
                    G_temp_lcc = G_temp.subgraph(largest_cc)
                    
                    if 'diameter' in metrics:
                        # Diameter is very slow, might warn user in docstring
                        results['diameter'].append(nx.diameter(G_temp_lcc))
                        
                    if 'avg_path_length' in metrics:
                        results['avg_path_length'].append(nx.average_shortest_path_length(G_temp_lcc))
                except (ValueError, nx.NetworkXError):
                    if 'diameter' in metrics: results['diameter'].append(0.0)
                    if 'avg_path_length' in metrics: results['avg_path_length'].append(0.0)
            else:
                if 'diameter' in metrics: results['diameter'].append(0.0)
                if 'avg_path_length' in metrics: results['avg_path_length'].append(0.0)
                
    return results

class NetworkAnalyzer:
    def __init__(self, G):
        self.G = G
        # Pre-calculate LCC once as many metrics depend on it
        if nx.is_directed(G):
             self.G_undirected = G.to_undirected()
             components = list(nx.connected_components(self.G_undirected))
        else:
             components = list(nx.connected_components(G))
             
        largest_cc_nodes = max(components, key=len)
        self.G_lcc = G.subgraph(largest_cc_nodes).copy()
        
        self.n_original = G.number_of_nodes()
        self.n_lcc = self.G_lcc.number_of_nodes()

    def calculate_global_metrics(self):
        """Calculates scalar metrics for the graph."""
        start = time.time()
        print("Calculating global metrics...")
        
        metrics = {
            "num_nodes": self.G.number_of_nodes(),
            "num_edges": self.G.number_of_edges(),
            "lcc_nodes": self.n_lcc,
            "lcc_edges": self.G_lcc.number_of_edges(),
            # Note nx raises error if G has multiple components for avg shortest path length
            "average_path_length_topo": nx.average_shortest_path_length(self.G_lcc),
            "average_clustering_coefficient": nx.average_clustering(self.G),
            "global_efficiency": nx.global_efficiency(self.G),
            "local_efficiency": nx.local_efficiency(self.G),
            "average_degree": (2 * self.G.number_of_edges()) / self.G.number_of_nodes() if self.G.number_of_nodes() > 0 else 0,
            "diameter": nx.diameter(self.G_lcc),
        }
        
        # Weighted path length if weights exist
        if nx.get_edge_attributes(self.G, 'weight'):
            # Note nx raises error if G has multiple components for avg shortest path length
            metrics["average_path_length_weighted"] = nx.average_shortest_path_length(self.G_lcc, weight='weight')
        
        print(f"Global metrics done in {time.time()-start:.2f}s")
        return metrics

    def simulate_attack(self, strategy, fractions, num_simulations=1, metrics=None):
        """
        Unified entry point for any attack strategy.
        metrics: List of metrics to compute ['lcc', 'efficiency', 'average_degree', 'clustering', 'diameter', 'avg_path_length']
        Returns: {metric: {fraction: value}}
        """
        if metrics is None:
            metrics = ['lcc', 'efficiency']
        metric_names = metrics
        # Determine label for progress bar
        if isinstance(strategy, RandomStrategy):
            desc = "Random Attack"
        elif isinstance(strategy, StaticTargetedStrategy):
            desc = "Targeted Attack"
        else:
            desc = "Attack Simulation"
            
        start = time.time()
        print(f"Simulating {desc} (Unified) - {num_simulations} runs...")
        
        final_results = {m: {} for m in metric_names}
        
        # Calculate optimal batch size for parallelism
        cpu_count = os.cpu_count() or 4
        # Heuristic: split heavily if few fractions
        total_tasks_target = cpu_count * 4
        tasks_per_fraction = max(1, total_tasks_target // len(fractions))
        batch_size = max(1, num_simulations // tasks_per_fraction)
        
        chunks = []
        remaining = num_simulations
        while remaining > 0:
            take = min(batch_size, remaining)
            chunks.append(take)
            remaining -= take
            
        # Base values (f=0)
        # Note: We should probably compute these dynamically for consistency if not passed
        # But for efficiency, we assume the user knows the initial state or we could calc them here.
        # Simple fix: metrics at f=0 are just global metrics
        base_values = {}
        if 'lcc' in metric_names: base_values['lcc'] = 1.0 # Normalized
        if 'efficiency' in metric_names: base_values['efficiency'] = nx.global_efficiency(self.G)
        if 'average_degree' in metric_names: base_values['average_degree'] = (2 * self.G.number_of_edges()) / self.n_original
        if 'clustering' in metric_names: base_values['clustering'] = nx.average_clustering(self.G)
        if 'diameter' in metric_names: base_values['diameter'] = nx.diameter(self.G_lcc)
        if 'avg_path_length' in metric_names: base_values['avg_path_length'] = nx.average_shortest_path_length(self.G_lcc)

        futures_map = {} # future -> fraction

        with ProcessPoolExecutor(initializer=_init_worker, initargs=(self.G,)) as executor:
            for f in fractions:
                if f == 0:
                    for m in metric_names:
                        final_results[m][str(f)] = base_values[m]
                    continue
                
                num_to_remove = int(self.n_original * f)
                
                for chunk_size in chunks:
                    future = executor.submit(
                        _worker_simulation, 
                        strategy, # Passes the Strategy object (must be picklable)
                        num_to_remove, 
                        chunk_size, 
                        self.n_original, 
                        metric_names
                    )
                    futures_map[future] = f

            # Aggregator
            temp_results = {str(f): {m: [] for m in metric_names} for f in fractions}
            
            # Disable tqdm in CI to prevent nbclient display_id errors
            is_ci = os.environ.get('CI', 'false').lower() == 'true'
            is_gha = os.environ.get('GITHUB_ACTIONS', 'false').lower() == 'true'
            print(f"DEBUG [simulate_attack]: CI={is_ci}, GITHUB_ACTIONS={is_gha}, env_CI={os.environ.get('CI')}, env_GHA={os.environ.get('GITHUB_ACTIONS')}", flush=True)
            disable_tqdm = is_ci or is_gha
            
            for future in tqdm(as_completed(futures_map), total=len(futures_map), desc=desc, disable=disable_tqdm):
                f = futures_map[future]
                try:
                    res_dict = future.result()
                    for m in metric_names:
                        temp_results[str(f)][m].extend(res_dict[m])
                except Exception as e:
                    print(f"Error for fraction {f}: {e}")

        # Final average
        for f, metric_data in temp_results.items():
            if float(f) == 0: continue
            for m in metric_names:
                values = metric_data[m]
                if values:
                    final_results[m][f] = np.mean(values)
                else:
                    final_results[m][f] = 0.0
                
        print(f"{desc} done in {time.time()-start:.2f}s")
        return final_results

    # --- Convenience Wrappers for API Compatibility ---

    def simulate_random_attacks(self, fractions, num_simulations, metrics=None):
        if metrics is None:
            metrics = ['lcc', 'efficiency']
        return self.simulate_attack(RandomStrategy(), fractions, num_simulations, metrics=metrics)

    def simulate_targeted_attack(self, fractions, strategy_name='degree', metrics=None):
        """
        Wrapper to create the appropriate strategy object and run simulations.
        """
        # Factory logic
        if strategy_name == 'degree':
            strategy = DegreeStrategy(self.G, inverse=False)
        elif strategy_name == 'inverse_degree':
            strategy = DegreeStrategy(self.G, inverse=True)
        elif strategy_name == 'betweenness':
            strategy = BetweennessStrategy(self.G, inverse=False)
        elif strategy_name == 'inverse_betweenness':
            strategy = BetweennessStrategy(self.G, inverse=True)
        elif strategy_name == 'articulation':
            strategy = ArticulationPointStrategy(self.G)
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")
            
        # Delegate to unified runner
        if metrics is None:
            # Default behavior for compatibility: return just efficiency dict
            results_all = self.simulate_attack(strategy, fractions, num_simulations=1, metrics=['efficiency'])
            return results_all['efficiency']
        else:
            # Extended behavior: return all requested metrics
            return self.simulate_attack(strategy, fractions, num_simulations=1, metrics=metrics)