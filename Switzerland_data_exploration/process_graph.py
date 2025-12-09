
import pickle
import networkx as nx
from pathlib import Path
from geopy.distance import geodesic
import pandas as pd
import numpy as np

# ---------------- CONFIGURATION ----------------
# Paths (Relative to Switzerland/ folder)
RAW_GRAPH_PATH = "../datasets/switzerland/swiss_rail_network_swisstopo.gpickle"
OUTPUT_GRAPH_PATH = "../datasets/switzerland/swiss_rail_network_unified.gpickle"

MERGE_RADIUS = 150  # Collapse nodes closer than this
LINK_RADIUS = 500   # Add edges between nodes closer than this

# Manual Fix Configurations
FIX_BUCHS_IDS = [
    'ch14uvag00240305', # Buchs SG RB
    'ch14uvag00088895'  # Buchs SG
]
FIX_MONTHEY_CENTER_ID = 'ch14uvag00089584' # Monthey
FIX_MONTHEY_NAME = 'Monthey'
FIX_HOFSTETTEN_COORDS = (47.485, 8.515) # Approx Oberglatt/Hofstetten based on visual
FIX_HOFSTETTEN_RADIUS = 1000

# ---------------- HELPERS ----------------
def parse_geopos(value):
    if isinstance(value, str) and ',' in value:
        lat_str, lon_str = value.split(',', 1)
        try:
            return float(lat_str.strip()), float(lon_str.strip())
        except ValueError:
            return None
    return None

def get_node_coords(G):
    coords = []
    for n, d in G.nodes(data=True):
        lat = d.get('lat')
        lon = d.get('lon')
        if lat is None or lon is None:
            for row in d.get('rows', []):
                val = parse_geopos(row.get('Geopos')) or parse_geopos(row.get('Geopos_didok'))
                if val:
                    lat, lon = val
                    break
        if lat is not None and lon is not None:
            coords.append({'id': n, 'lat': lat, 'lon': lon})
    return coords

def main():
    print(f"Loading raw graph from {RAW_GRAPH_PATH}...")
    with open(RAW_GRAPH_PATH, 'rb') as f:
        G = pickle.load(f)
    print(f"Loaded {len(G)} nodes.")

    # 1. EXTRACT COORDINATES
    node_coords = get_node_coords(G)
    coord_map = {item['id']: (item['lat'], item['lon']) for item in node_coords}

    # 2. MERGE PASS (150m)
    print(f"Merging nodes < {MERGE_RADIUS}m...")
    bucket_size = MERGE_RADIUS / 111000.0
    grid = {}
    for item in node_coords:
        k = (int(item['lat']/bucket_size), int(item['lon']/bucket_size))
        if k not in grid: grid[k] = []
        grid[k].append(item)

    merge_graph = nx.Graph()
    merge_graph.add_nodes_from(G.nodes())
    
    for item in node_coords:
        base_lat = int(item['lat']/bucket_size)
        base_lon = int(item['lon']/bucket_size)
        for dlat in [-1,0,1]:
            for dlon in [-1,0,1]:
                cand_key = (base_lat+dlat, base_lon+dlon)
                for cand in grid.get(cand_key, []):
                    if item['id'] < cand['id']:
                        dist = geodesic((item['lat'], item['lon']), (cand['lat'], cand['lon'])).meters
                        if dist < MERGE_RADIUS:
                            merge_graph.add_edge(item['id'], cand['id'])
    
    mapping = {}
    for comp in nx.connected_components(merge_graph):
        if len(comp) > 1:
            rep = sorted(list(comp))[0]
            for node in comp:
                mapping[node] = rep
    
    G = nx.relabel_nodes(G, mapping, copy=True)
    G.remove_edges_from(nx.selfloop_edges(G))
    print(f"Merge complete. Nodes: {len(G)}")

    # 3. LINK PASS (500m)
    print(f"Linking nodes < {LINK_RADIUS}m...")
    # Refresh coords
    node_coords = get_node_coords(G)
    coord_map = {item['id']: (item['lat'], item['lon']) for item in node_coords}
    bucket_size = LINK_RADIUS / 111000.0
    grid = {}
    for item in node_coords:
        k = (int(item['lat']/bucket_size), int(item['lon']/bucket_size))
        if k not in grid: grid[k] = []
        grid[k].append(item)
    
    added_links = 0
    for item in node_coords:
        base_lat = int(item['lat']/bucket_size)
        base_lon = int(item['lon']/bucket_size)
        for dlat in [-1,0,1]:
            for dlon in [-1,0,1]:
                cand_key = (base_lat+dlat, base_lon+dlon)
                for cand in grid.get(cand_key, []):
                    if item['id'] < cand['id']:
                        if not G.has_edge(item['id'], cand['id']):
                            dist = geodesic((item['lat'], item['lon']), (cand['lat'], cand['lon'])).meters
                            if dist < LINK_RADIUS:
                                G.add_edge(item['id'], cand['id'], weight=dist, type='synthetic_link')
                                added_links += 1
    print(f"Added {added_links} global synthetic links.")

    # 4. MANUAL PATCHES
    print("Applying Manual Patches...")

    # Patch A: Buchs SG
    u, v = FIX_BUCHS_IDS
    # Check if they exist (might have been merged)
    u = mapping.get(u, u)
    v = mapping.get(v, v)
    if G.has_node(u) and G.has_node(v) and u != v:
        if not G.has_edge(u, v):
            dist = geodesic(coord_map[u], coord_map[v]).meters
            G.add_edge(u, v, weight=dist, type='manual_patch')
            print(f"Fixed Buchs SG ({u}-{v})")

    # Patch B: Monthey
    # Find center
    center = mapping.get(FIX_MONTHEY_CENTER_ID, FIX_MONTHEY_CENTER_ID)
    if G.has_node(center):
        center_pos = coord_map[center]
        # Find all nodes with "Monthey" in name
        targets = []
        for n, d in G.nodes(data=True):
            name = str(d.get('name', '')).lower()
            if 'monthey' in name and n != center:
                targets.append(n)
        
        for t in targets:
            if t in coord_map:
                dist = geodesic(center_pos, coord_map[t]).meters
                if dist < 1500: # Generous 1.5km for Monthey cluster
                    G.add_edge(center, t, weight=dist, type='manual_patch')
                    print(f"Linked Monthey node {t} to Center")

    # Patch C: Hofstetten / Oberglatt
    # Find nodes near coords
    near_nodes = []
    for n, pos in coord_map.items():
        if geodesic(pos, FIX_HOFSTETTEN_COORDS).meters < FIX_HOFSTETTEN_RADIUS:
            near_nodes.append(n)
    
    if len(near_nodes) > 1:
        # Fully connect them (clique) or just line?
        # Let's connect all to the one closest to center
        near_nodes.sort(key=lambda n: geodesic(coord_map[n], FIX_HOFSTETTEN_COORDS).meters)
        hub = near_nodes[0]
        for other in near_nodes[1:]:
             if not G.has_edge(hub, other):
                dist = geodesic(coord_map[hub], coord_map[other]).meters
                G.add_edge(hub, other, weight=dist, type='manual_manual')
                print(f"Fixed Hofstetten/Oberglatt: Linked {other} to {hub}")

    # 5. SAVE
    print(f"Saving unified graph to {OUTPUT_GRAPH_PATH}...")
    with open(OUTPUT_GRAPH_PATH, 'wb') as f:
        pickle.dump(G, f)
    print("Done.")

if __name__ == "__main__":
    main()
