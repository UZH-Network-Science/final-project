import networkx as nx
import numpy as np
import time
import os
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
                lcc_size = len(max(nx.connected_components(G_temp), key=len))
                results['lcc'].append(lcc_size / n_lcc)
            else:
                results['lcc'].append(0.0)
                
        if 'efficiency' in metrics:
            if not is_empty:
                results['efficiency'].append(nx.global_efficiency(G_temp))
            else:
                results['efficiency'].append(0.0)
                
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
        }
        
        # Weighted path length if weights exist
        if nx.get_edge_attributes(self.G, 'weight'):
            # Note nx raises error if G has multiple components for avg shortest path length
            metrics["average_path_length_weighted"] = nx.average_shortest_path_length(self.G_lcc, weight='weight')
        
        print(f"Global metrics done in {time.time()-start:.2f}s")
        return metrics

    def simulate_attack(self, strategy, fractions, num_simulations=1):
        """
        Unified entry point for any attack strategy.
        Returns: {'lcc': {}, 'efficiency': {}}
        """
        metric_names = ['lcc', 'efficiency']
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
        base_values = {
            'lcc': 1.0,
            'efficiency': nx.global_efficiency(self.G)
        }

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
            
            for future in tqdm(as_completed(futures_map), total=len(futures_map), desc=desc):
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

    def simulate_random_attacks(self, fractions, num_simulations):
        return self.simulate_attack(RandomStrategy(), fractions, num_simulations)

    def simulate_targeted_attack(self, fractions, strategy_name='degree'):
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
        results_all = self.simulate_attack(strategy, fractions, num_simulations=1)
        return results_all['efficiency']