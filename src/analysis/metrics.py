import networkx as nx
import numpy as np
import time

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
        
        for f in fractions:
            if f == 0:
                results[str(f)] = 1.0
                continue
                
            num_to_remove = int(self.n_lcc * f)
            sizes = []
            
            for _ in range(num_simulations):
                G_temp = self.G_lcc.copy()
                nodes = list(G_temp.nodes())
                if num_to_remove >= len(nodes):
                     sizes.append(0.0)
                     continue
                     
                remove_targets = np.random.choice(nodes, num_to_remove, replace=False)
                G_temp.remove_nodes_from(remove_targets)
                
                if G_temp.number_of_nodes() > 0:
                    lcc_size = len(max(nx.connected_components(G_temp), key=len))
                    sizes.append(lcc_size / self.n_lcc)
                else:
                    sizes.append(0.0)
            
            results[str(f)] = np.mean(sizes)
            
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
        
        for f in fractions:
            if f == 0:
                results[str(f)] = base_eff
                continue
            
            num_to_remove = int(self.n_lcc * f)
            effs = []
            
            for _ in range(num_simulations):
                G_temp = self.G_lcc.copy()
                nodes = list(G_temp.nodes())
                if num_to_remove >= len(nodes):
                    effs.append(0.0)
                    continue
                
                # Faster removal than copy?
                remove_targets = np.random.choice(nodes, num_to_remove, replace=False)
                G_temp.remove_nodes_from(remove_targets)
                
                effs.append(nx.global_efficiency(G_temp))
                
            results[str(f)] = np.mean(effs)
            
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
        for f in fractions:
            if f == 0:
                results[str(f)] = nx.global_efficiency(self.G_lcc)
                continue
                
            num_to_remove = int(self.n_lcc * f)
            targets = sorted_nodes[:num_to_remove]
            
            G_temp = self.G_lcc.copy()
            G_temp.remove_nodes_from(targets)
            
            results[str(f)] = nx.global_efficiency(G_temp)
            
        print(f"Targeted attack ({strategy}) done in {time.time()-start:.2f}s")
        return results
