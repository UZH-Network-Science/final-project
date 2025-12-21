
import pandas as pd
import geopandas as gpd
import networkx as nx
import pickle
from pathlib import Path
from shapely.geometry import Point, LineString

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

def classify_station(abbreviation, station_abbreviation_set, fallback_rows=None):
    abbr = (abbreviation or "").strip().upper()
    if abbr and abbr in station_abbreviation_set:
        return True
    fallback_rows = fallback_rows or []
    for row in fallback_rows:
        row_abbr = row.get('Station abbreviation')
        if isinstance(row_abbr, str) and row_abbr.strip().upper() in station_abbreviation_set:
            return True
    return False

def flatten_lines(geom):
    if geom is None or geom.is_empty:
        return []
    coords = []
    if geom.geom_type == 'LineString':
        coords.extend((pt[1], pt[0]) for pt in geom.coords)
    elif geom.geom_type == 'MultiLineString':
        for line in geom.geoms:
            coords.extend((pt[1], pt[0]) for pt in line.coords)
    return coords


def load_data(base_dir):
    """Loads raw dataframes/gdfs from source files."""
    base_dir = Path(base_dir)
    SBB_STATION_PATH = base_dir / "sbb-dienststellen-gemass-opentransportdataswiss.csv"
    SWISSTOPO_GDB_PATH = base_dir / "schienennetz_2056_de.gdb"
    
    # Load metadata
    station_metadata = pd.read_csv(SBB_STATION_PATH, sep=';')
    
    # Load Swisstopo data
    try:
        net_segments = gpd.read_file(SWISSTOPO_GDB_PATH, layer='Netzsegment')
        net_nodes = gpd.read_file(SWISSTOPO_GDB_PATH, layer='Netzknoten')
    except Exception as e:
        print(f"Error loading GDB file: {e}")
        return None, None, None

    return station_metadata, net_segments, net_nodes

def get_station_abbreviations(station_metadata):
    """Extracts valid station abbreviations from metadata."""
    station_metadata['abbreviation_clean'] = (
        station_metadata['abbreviation']
        .astype(str)
        .str.strip()
        .str.upper()
    )
    stop_point_mask = station_metadata['stopPoint'].astype(str).str.lower() == 'true'
    station_abbreviation_set = set(
        station_metadata.loc[stop_point_mask, 'abbreviation_clean'].dropna().tolist()
    )
    station_abbreviation_set.discard('NAN')
    return station_abbreviation_set

def build_graph(net_nodes, net_segments, station_abbreviation_set):
    """Constructs the NetworkX graph from nodes and segments."""
    G = nx.Graph()
    
    nodes_gdf = net_nodes.to_crs(4326)
    segments_wgs84 = net_segments.to_crs(4326)

    # Process Nodes
    for _, row in nodes_gdf.iterrows():
        node_id = row['xtf_id']
        abbr = row.get('Betriebspunkt_Abkuerzung')
        label = abbr or row.get('Betriebspunkt_Name') or node_id
        lat = row.geometry.y
        lon = row.geometry.x
        is_station = False
        if isinstance(abbr, str) and abbr.strip():
            is_station = abbr.strip().upper() in station_abbreviation_set
        
        node_attrs = {
            'label': label,
            'abbreviation': abbr,
            'lat': lat,
            'lon': lon,
            'is_station': is_station,
            'rows': [row.drop(labels='geometry').to_dict()],
            'source': 'swisstopo',
        }
        G.add_node(node_id, **node_attrs)
    
    print(f"Nodes loaded: {G.number_of_nodes()}")

    # Process Edges
    for _, row in segments_wgs84.iterrows():
        u = row['rAnfangsknoten']
        v = row['rEndknoten']
        
        if pd.isna(u) or pd.isna(v):
            continue
        if u not in G.nodes or v not in G.nodes:
            continue
            
        lines = [row['Name']] if isinstance(row.get('Name'), str) else []
        segment_meta = {
            'segment_id': row['xtf_id'],
            'line_name': row.get('Name'),
            'track_count': row.get('AnzahlStreckengleise'),
            'gauge': row.get('Spurweite'),
            'electrified': row.get('Elektrifizierung'),
            'coords_wgs84': flatten_lines(row.geometry),
        }
        
        if G.has_edge(u, v):
            combined = set(G[u][v]['lines'])
            combined.update(lines)
            G[u][v]['lines'] = sorted(combined)
            G[u][v]['segments'].append(segment_meta)
        else:
            G.add_edge(
                u,
                v,
                lines=sorted(lines),
                segments=[segment_meta],
                source='swisstopo',
            )
            
    return G

def process_switzerland(base_dir="datasets/switzerland", output_dir="datasets/switzerland"):
    base_dir = Path(base_dir)
    output_dir = Path(output_dir)
    GRAPH_OUTPUT_PATH = output_dir / "swiss_rail_network_swisstopo.gpickle"
    
    print(f"Processing Switzerland dataset from: {base_dir}")
    
    # 1. Load
    station_metadata, net_segments, net_nodes = load_data(base_dir)
    if net_segments is None:
        return

    # 2. Prepare
    station_abbreviation_set = get_station_abbreviations(station_metadata)

    # 3. Build Raw Graph
    G = build_graph(net_nodes, net_segments, station_abbreviation_set)
    print(f"Raw Build complete. Nodes: {len(G)}, Edges: {len(G.edges())}")

    # 4. UNIFICATION (Merge + Link + Patch)
    # Copied from legacy process_graph.py to ensure continuity
    from geopy.distance import geodesic

    MERGE_RADIUS = 150  # Collapse nodes closer than this
    LINK_RADIUS = 500   # Add edges between nodes closer than this
    
    # helper for unification
    def get_node_coords(G):
        coords = []
        for n, d in G.nodes(data=True):
            lat = d.get('lat')
            lon = d.get('lon')
            # Fallback to rows if top-level missing (should be there from build_graph but safe)
            if lat is None or lon is None:
                 pass 
            if lat is not None and lon is not None:
                coords.append({'id': n, 'lat': lat, 'lon': lon})
        return coords

    # --- 4a. MERGE PASS ---
    print(f"Merging nodes < {MERGE_RADIUS}m...")
    node_coords = get_node_coords(G)
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

    # --- 4b. LINK PASS ---
    print(f"Linking nodes < {LINK_RADIUS}m...")
    node_coords = get_node_coords(G) # Refresh coords
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

    # --- 4c. MANUAL PATCHES ---
    print("Applying Manual Patches...")
    FIX_BUCHS_IDS = ['ch14uvag00240305', 'ch14uvag00088895']
    FIX_MONTHEY_CENTER_ID = 'ch14uvag00089584'
    FIX_HOFSTETTEN_COORDS = (47.485, 8.515)
    FIX_HOFSTETTEN_RADIUS = 1000

    # Patch A: Buchs SG
    u, v = FIX_BUCHS_IDS
    u = mapping.get(u, u)
    v = mapping.get(v, v)
    if G.has_node(u) and G.has_node(v) and u != v:
        if not G.has_edge(u, v):
            dist = geodesic(coord_map[u], coord_map[v]).meters
            G.add_edge(u, v, weight=dist, type='manual_patch')
            print(f"Fixed Buchs SG ({u}-{v})")

    # Patch B: Monthey
    try:
        center = mapping.get(FIX_MONTHEY_CENTER_ID, FIX_MONTHEY_CENTER_ID)
        if G.has_node(center):
            center_pos = coord_map[center]
            targets = []
            for n, d in G.nodes(data=True):
                name = str(d.get('label', '')).lower() # Use label instead of raw name
                if 'monthey' in name and n != center:
                    targets.append(n)
            
            for t in targets:
                if t in coord_map:
                    dist = geodesic(center_pos, coord_map[t]).meters
                    if dist < 1500:
                        G.add_edge(center, t, weight=dist, type='manual_patch')
                        print(f"Linked Monthey node {t} to Center")
    except Exception as e:
        print(f"Warning: Monthey patch failed: {e}")

    # Patch C: Hofstetten / Oberglatt
    try:
        near_nodes = []
        for n, pos in coord_map.items():
            if geodesic(pos, FIX_HOFSTETTEN_COORDS).meters < FIX_HOFSTETTEN_RADIUS:
                near_nodes.append(n)
        
        if len(near_nodes) > 1:
            near_nodes.sort(key=lambda n: geodesic(coord_map[n], FIX_HOFSTETTEN_COORDS).meters)
            hub = near_nodes[0]
            for other in near_nodes[1:]:
                 if not G.has_edge(hub, other):
                    dist = geodesic(coord_map[hub], coord_map[other]).meters
                    G.add_edge(hub, other, weight=dist, type='manual_manual')
                    print(f"Fixed Hofstetten/Oberglatt: Linked {other} to {hub}")
    except Exception as e:
         print(f"Warning: Hofstetten patch failed: {e}")

    # 5. Export
    # We export to 'swiss_rail_network_unified.gpickle' to match the legacy output name
    UNIFIED_OUTPUT_PATH = output_dir / "swiss_rail_network_unified.gpickle"

    print(f"Final Graph: Nodes: {len(G)}, Edges: {len(G.edges())}")
    print(f"Connected components: {nx.number_connected_components(G)}")
    
    print(f"Exporting unified graph to {UNIFIED_OUTPUT_PATH}...")
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(UNIFIED_OUTPUT_PATH, 'wb') as f:
        pickle.dump(G, f)
    print("Export successful.")


if __name__ == "__main__":
    process_switzerland()
