
import pickle
import networkx as nx
from pathlib import Path
from geopy.distance import geodesic
import time

BASE_DIR = Path("../datasets/switzerland")
SWISSTOPO_PICKLE_PATH = BASE_DIR / "swiss_rail_network_swisstopo.gpickle"

def parse_geopos(value):
    if isinstance(value, str) and ',' in value:
        lat_str, lon_str = value.split(',', 1)
        try:
            lat = float(lat_str.strip())
            lon = float(lon_str.strip())
        except ValueError:
            return None
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    return None

print("Loading Graph...")
with open(SWISSTOPO_PICKLE_PATH, 'rb') as f:
    G_raw = pickle.load(f)

# Extract valid coords
node_coords = []
for n, d in G_raw.nodes(data=True):
    lat = d.get('lat')
    lon = d.get('lon')
    if lat is None or lon is None:
        for row in d.get('rows', []):
            coords = parse_geopos(row.get('Geopos')) or parse_geopos(row.get('Geopos_didok'))
            if coords: 
                lat, lon = coords
                break
    if lat is not None and lon is not None:
        node_coords.append({'id': n, 'lat': lat, 'lon': lon})

print(f"Total Nodes with Coords: {len(node_coords)} / {len(G_raw)}")

def get_merge_mapping(radius_m):
    bucket_size_deg = (radius_m / 111000.0)
    spatial_grid = {}
    for item in node_coords:
        key = (int(item['lat'] / bucket_size_deg), int(item['lon'] / bucket_size_deg))
        if key not in spatial_grid: spatial_grid[key] = []
        spatial_grid[key].append(item)
        
    merge_graph = nx.Graph()
    merge_graph.add_nodes_from([i['id'] for i in node_coords])
    checked = set()
    
    for item in node_coords:
        base_lat_k = int(item['lat'] / bucket_size_deg)
        base_lon_k = int(item['lon'] / bucket_size_deg)
        for dlat in [-1, 0, 1]:
            for dlon in [-1, 0, 1]:
                key = (base_lat_k + dlat, base_lon_k + dlon)
                candidates = spatial_grid.get(key, [])
                for cand in candidates:
                    if item['id'] >= cand['id']: continue
                    dist = geodesic((item['lat'], item['lon']), (cand['lat'], cand['lon'])).meters
                    if dist < radius_m:
                        merge_graph.add_edge(item['id'], cand['id'])
                        
    mapping = {}
    for comp in nx.connected_components(merge_graph):
        if len(comp) > 1:
            rep = sorted(list(comp))[0]
            for node in comp:
                mapping[node] = rep
    return mapping

# 1. FIXED MERGE at 150m
MERGE_RADIUS = 150
print(f"\n--- Step 1: Spatial Merge (< {MERGE_RADIUS}m) ---")
mapping = get_merge_mapping(MERGE_RADIUS)
G_merged = nx.relabel_nodes(G_raw, mapping, copy=True)
G_merged.remove_edges_from(nx.selfloop_edges(G_merged))

# Re-extract unified coords
unified_coords = []
for n, d in G_merged.nodes(data=True):
    lat = d.get('lat')
    lon = d.get('lon')
    if lat is None or lon is None:
         for row in d.get('rows', []):
            coords = parse_geopos(row.get('Geopos')) or parse_geopos(row.get('Geopos_didok'))
            if coords: 
                lat, lon = coords
                break
    if lat is not None and lon is not None:
        unified_coords.append({'id': n, 'lat': lat, 'lon': lon})

def test_link_radius(link_radius_m):
    G_temp = G_merged.copy()
    
    if link_radius_m <= MERGE_RADIUS:
        # No extra linking
        pass
    else:
        bucket_size_deg = (link_radius_m / 111000.0)
        link_grid = {}
        for item in unified_coords:
            k = (int(item['lat']/bucket_size_deg), int(item['lon']/bucket_size_deg))
            if k not in link_grid: link_grid[k] = []
            link_grid[k].append(item)
            
        added_links = 0
        checked = set()
        
        for item in unified_coords:
            base_lat_k = int(item['lat'] / bucket_size_deg)
            base_lon_k = int(item['lon'] / bucket_size_deg)
            
            for dlat in [-1, 0, 1]:
                for dlon in [-1, 0, 1]:
                    key = (base_lat_k + dlat, base_lon_k + dlon)
                    candidates = link_grid.get(key, [])
                    for cand in candidates:
                        if item['id'] >= cand['id']: continue
                        if G_temp.has_edge(item['id'], cand['id']): continue
                        
                        dist = geodesic((item['lat'], item['lon']), (cand['lat'], cand['lon'])).meters
                        if dist < link_radius_m:
                            G_temp.add_edge(item['id'], cand['id'])
                            added_links += 1
                            
    components = list(nx.connected_components(G_temp))
    if not components: return 0, 0
    lcc = max(components, key=len)
    return len(G_temp) - len(lcc), len(components)

print(f"\n--- Step 2: Hybrid Linking Sweep (Merge=150m + Link=X) ---")
print(f"{'Link Radius (m)':<20} | {'Isolated Nodes':<15} | {'Components':<15}")
print("-" * 60)

for r in [150, 200, 300, 400, 500, 600, 700, 800]:
    iso, comps = test_link_radius(r)
    print(f"{r:<20} | {iso:<15} | {comps:<15}")
