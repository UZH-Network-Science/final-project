import networkx as nx
import numpy as np
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
from functools import partial

def _worker_random_attack_lcc(G, num_to_remove, num_simulations, n_lcc):
    sizes = []
    nodes = list(G.nodes())
    if num_to_remove >= len(nodes):
        return 0.0
        
    for _ in range(num_simulations):
        G_temp = G.copy()
        # np.random.choice on list of nodes
        remove_targets = np.random.choice(nodes, num_to_remove, replace=False)
        G_temp.remove_nodes_from(remove_targets)
        
        if G_temp.number_of_nodes() > 0:
            lcc_size = len(max(nx.connected_components(G_temp), key=len))
            sizes.append(lcc_size / n_lcc)
        else:
            sizes.append(0.0)
    return np.mean(sizes)

def _worker_random_attack_efficiency(G, num_to_remove, num_simulations):
    effs = []
    nodes = list(G.nodes())
    if num_to_remove >= len(nodes):
        return 0.0
        
    for _ in range(num_simulations):
        G_temp = G.copy()
        remove_targets = np.random.choice(nodes, num_to_remove, replace=False)
        G_temp.remove_nodes_from(remove_targets)
        effs.append(nx.global_efficiency(G_temp))
        
    return np.mean(effs)

def _worker_targeted_attack(G, nodes_to_remove):
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

    def simulate_random_attack(self, fractions, num_simulations):
        """
        Removes random fraction of nodes and measures size of LCC.
        Returns: {fraction: mean_relative_lcc_size}
        """
        start = time.time()
        print(f"Simulating random attacks (LCC Size) - {num_simulations} runs...")
        results = {}
        
        # Prepare tasks
        tasks = {} # future -> fraction
        
        with ProcessPoolExecutor() as executor:
            for f in fractions:
                if f == 0:
                    results[str(f)] = 1.0
                    continue
                    
                num_to_remove = int(self.n_lcc * f)
                # Submit task
                future = executor.submit(_worker_random_attack_lcc, self.G_lcc, num_to_remove, num_simulations, self.n_lcc)
                tasks[future] = f

            # Progress monitoring
            # We filter out f=0 from tasks, so total is len(fractions)-1 usually
            for future in tqdm(as_completed(tasks), total=len(tasks), desc="Random Attack (LCC)"):
                f = tasks[future]
                try:
                    res = future.result()
                    results[str(f)] = res
                except Exception as e:
                    print(f"Error for fraction {f}: {e}")
                    results[str(f)] = 0.0
            
        print(f"Random attacks (LCC Size) done in {time.time()-start:.2f}s")
        return results

    def simulate_random_attack_efficiency(self, fractions, num_simulations):
        """
        Removes random fraction of nodes and measures Global Efficiency.
        Returns: {fraction: mean_efficiency}
        """
        start = time.time()
        print(f"Simulating random attacks (Efficiency) - {num_simulations} runs...")
        results = {}
        
        # Base efficiency
        base_eff = nx.global_efficiency(self.G_lcc)
        
        tasks = {}
        
        with ProcessPoolExecutor() as executor:
            for f in fractions:
                if f == 0:
                    results[str(f)] = base_eff
                    continue
                
                num_to_remove = int(self.n_lcc * f)
                future = executor.submit(_worker_random_attack_efficiency, self.G_lcc, num_to_remove, num_simulations)
                tasks[future] = f
                
            for future in tqdm(as_completed(tasks), total=len(tasks), desc="Random Attack (Eff)"):
                f = tasks[future]
                try:
                    results[str(f)] = future.result()
                except Exception as e:
                    print(f"Error for fraction {f}: {e}")
                    results[str(f)] = 0.0
            
        print(f"Random attacks (Efficiency) done in {time.time()-start:.2f}s")
        return results

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
        with ProcessPoolExecutor() as executor:
            for f in fractions:
                if f == 0:
                    results[str(f)] = nx.global_efficiency(self.G_lcc)
                    continue
                    
                num_to_remove = int(self.n_lcc * f)
                targets = sorted_nodes[:num_to_remove]
                
                future = executor.submit(_worker_targeted_attack, self.G_lcc, targets)
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
