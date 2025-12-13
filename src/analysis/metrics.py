import networkx as nx
import numpy as np
import time
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
from functools import partial


# Global variable to hold the shared graph in each worker process
SHARED_GRAPH = None

def _init_worker(G):
    global SHARED_GRAPH
    SHARED_GRAPH = G

def _worker_random_attack_batch(num_to_remove, num_simulations, n_lcc, metrics):
    """
    Unified worker that can compute multiple metrics on the same perturbed graphs.
    """
    global SHARED_GRAPH
    G = SHARED_GRAPH
    
    results = {m: [] for m in metrics}
    nodes = list(G.nodes())
    
    if num_to_remove >= len(nodes):
        for m in metrics:
            results[m] = [0.0] * num_simulations
        return results

    for _ in range(num_simulations):
        G_temp = G.copy()
        remove_targets = np.random.choice(nodes, num_to_remove, replace=False)
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

def _worker_targeted_attack(nodes_to_remove):
    global SHARED_GRAPH
    G = SHARED_GRAPH
    
    G_temp = G.copy()
    G_temp.remove_nodes_from(nodes_to_remove)
    return nx.global_efficiency(G_temp)

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
            "average_path_length_topo": nx.average_shortest_path_length(self.G_lcc),
            "average_clustering_coefficient": nx.average_clustering(self.G_lcc),
            "global_efficiency": nx.global_efficiency(self.G_lcc),
            "local_efficiency": nx.local_efficiency(self.G_lcc),
        }
        
        # Weighted path length if weights exist
        if nx.get_edge_attributes(self.G_lcc, 'weight'):
             metrics["average_path_length_weighted"] = nx.average_shortest_path_length(self.G_lcc, weight='weight')
        
        print(f"Global metrics done in {time.time()-start:.2f}s")
        return metrics

    def _run_random_simulations_generic(self, fractions, num_simulations, metric_name):
        """
        Generic driver for parallel random simulations.
        """
        start = time.time()
        print(f"Simulating random attacks ({metric_name}) - {num_simulations} runs...")
        results = {}
        
        # Calculate optimal batch size
        # We want at least 4x CPU count tasks to ensure good load balancing
        cpu_count = os.cpu_count() or 4
        total_tasks_target = cpu_count * 4
        
        # Very rough heuristic: splits per fraction
        # If we have 10 fractions and want 40 tasks, we need 4 splits per fraction
        # But ensure min batch size so overhead isn't too high
        tasks_per_fraction = max(1, total_tasks_target // len(fractions))
        batch_size = max(1, num_simulations // tasks_per_fraction)
        
        # Ensure exact coverage
        # Actually simpler: just generate chunks
        chunks = []
        remaining = num_simulations
        while remaining > 0:
            take = min(batch_size, remaining)
            chunks.append(take)
            remaining -= take
            
        print(f"  -> Parallel Strategy: {len(chunks)} chunks/fraction (batch size ~{batch_size})")

        # Prepare base value for f=0 outside loop
        if metric_name == 'lcc':
            base_val = 1.0
        else:
            base_val = nx.global_efficiency(self.G_lcc)

        futures_map = {} # future -> fraction

        with ProcessPoolExecutor(initializer=_init_worker, initargs=(self.G_lcc,)) as executor:
            for f in fractions:
                if f == 0:
                    results[str(f)] = base_val
                    continue
                
                num_to_remove = int(self.n_lcc * f)
                
                for chunk_size in chunks:
                    future = executor.submit(
                        _worker_random_attack_batch, 
                        num_to_remove, 
                        chunk_size, 
                        self.n_lcc, 
                        [metric_name]
                    )
                    futures_map[future] = f

            # Aggregator for chunks
            temp_results = {str(f): [] for f in fractions}
            
            for future in tqdm(as_completed(futures_map), total=len(futures_map), desc=f"Random ({metric_name})"):
                f = futures_map[future]
                try:
                    res_dict = future.result()
                    # res_dict is {'metric': [values...]}
                    temp_results[str(f)].extend(res_dict[metric_name])
                except Exception as e:
                    print(f"Error for fraction {f}: {e}")

        # Final average
        for f, values in temp_results.items():
            if f == str(0): continue # already set
            if values:
                results[f] = np.mean(values)
            else:
                results[f] = 0.0
                
        print(f"Random attacks ({metric_name}) done in {time.time()-start:.2f}s")
        return results

    def simulate_random_attack(self, fractions, num_simulations):
        return self._run_random_simulations_generic(fractions, num_simulations, 'lcc')

    def simulate_random_attack_efficiency(self, fractions, num_simulations):
        return self._run_random_simulations_generic(fractions, num_simulations, 'efficiency')

    def simulate_targeted_attack(self, fractions, strategy='degree'):
        """
        Removes nodes based on centrality strategy.
        Returns: {fraction: efficiency}
        """
        start = time.time()
        print(f"Simulating targeted attack ({strategy})...")
        
        if strategy == 'degree':
            centrality = nx.degree_centrality(self.G_lcc)
            reverse = True
        elif strategy == 'inverse_degree':
            centrality = nx.degree_centrality(self.G_lcc)
            reverse = False
        elif strategy == 'betweenness':
             print("Calculating Betweenness (this may take a while)...")
             centrality = nx.betweenness_centrality(self.G_lcc)
             reverse = True
        elif strategy == 'inverse_betweenness':
             print("Calculating Betweenness (this may take a while)...")
             centrality = nx.betweenness_centrality(self.G_lcc)
             reverse = False
        elif strategy == 'articulation':
             # Hybrid Strategy: Articulation Points first (sorted by degree), then High Degree
             print("identifying Articulation Points...")
             articulation_points = set(nx.articulation_points(self.G_lcc))
             degree_cent = nx.degree_centrality(self.G_lcc)
             
             # Sort Articulation Points by Degree
             ap_list = sorted([n for n in articulation_points], key=degree_cent.get, reverse=True)
             
             # Sort Non-Articulation Points by Degree
             others = sorted([n for n in degree_cent if n not in articulation_points], key=degree_cent.get, reverse=True)
             
             # Combined list
             sorted_nodes = ap_list + others
             centrality = None # Not needed for sorting anymore
             reverse = None    # Already sorted
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
            
        if strategy != 'articulation':
            sorted_nodes = sorted(centrality, key=centrality.get, reverse=reverse)
        
        results = {}
        tasks = {}
        with ProcessPoolExecutor(initializer=_init_worker, initargs=(self.G_lcc,)) as executor:
            for f in fractions:
                if f == 0:
                    results[str(f)] = nx.global_efficiency(self.G_lcc)
                    continue
                    
                num_to_remove = int(self.n_lcc * f)
                targets = sorted_nodes[:num_to_remove]
                
                future = executor.submit(_worker_targeted_attack, targets)
                tasks[future] = f
            
            for future in tqdm(as_completed(tasks), total=len(tasks), desc=f"Targeted ({strategy})"):
                f = tasks[future]
                try:
                    results[str(f)] = future.result()
                except Exception as e:
                    print(f"Error for fraction {f}: {e}")
                    results[str(f)] = 0.0
            
        print(f"Targeted attack ({strategy}) done in {time.time()-start:.2f}s")
        return results
