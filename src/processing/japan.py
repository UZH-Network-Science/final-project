
import geopandas as gpd
import networkx as nx
import pickle
import numpy as np
from pathlib import Path
from shapely.geometry import Point, LineString
from shapely.ops import unary_union
from collections import defaultdict, Counter
from scipy.spatial import cKDTree


def load_data(base_dir):
    """Loads raw GeoJSON files."""
    base_dir = Path(base_dir)
    station_path = base_dir / 'N02-24_GML/UTF-8/N02-24_Station.geojson'
    railroad_path = base_dir / 'N02-24_GML/UTF-8/N02-24_RailroadSection.geojson'
    
    print(f"Processing Japan dataset from: {base_dir}")
    print("Loading stations...")
    try:
        gdf_stations = gpd.read_file(station_path)
        print(f"Loaded {len(gdf_stations)} stations.")
        print("Loading railroad sections...")
        gdf_railroads = gpd.read_file(railroad_path)
        print(f"Loaded {len(gdf_railroads)} railroad sections.")
    except Exception as e:
        print(f"Error loading GeoJSON files: {e}")
        return None, None
    return gdf_stations, gdf_railroads

def group_stations(gdf_stations):
    """Groups station platforms by Group Code."""
    print("Step 1: Grouping station platforms...")
    group_code_groups = defaultdict(list)
    for idx, station in gdf_stations.iterrows():
        group_code = station['N02_005g']
        group_code_groups[group_code].append({
            'idx': idx,
            'geometry': station.geometry,
            'name': station['N02_005'],
            'operator': station.get('N02_004'),
            'station_code': station.get('N02_005c'),
        })
    print(f"Found {len(group_code_groups)} unique group codes")
    return group_code_groups

def create_initial_nodes(group_code_groups):
    """Creates initial station nodes from platform groups."""
    print("Step 2: Creating station nodes...")
    station_groups = {}
    
    for group_code, platforms in group_code_groups.items():
        station_id = group_code
        all_platform_geoms = [p['geometry'] for p in platforms]
        combined_platforms = unary_union(all_platform_geoms)
        centroid = combined_platforms.centroid
        
        names = list(set(p['name'] for p in platforms if p['name']))
        operators = list(set(p['operator'] for p in platforms if p['operator']))
        coords = list(set([coord for p in platforms for coord in p['geometry'].coords]))
        
        name_counts = Counter(p['name'] for p in platforms if p['name'])
        display_name = max(name_counts, key=name_counts.get) if name_counts else f"Station_{group_code}"
        
        station_groups[station_id] = {
            'centroid': centroid,
            'coords': coords,
            'geometry': combined_platforms,
            'lat': centroid.y,
            'lon': centroid.x,
            'name': display_name,
            'all_names': names,
            'operators': operators,
            'platform_count': len(platforms),
            'group_code': group_code,
        }
    return station_groups

def merge_interchange_stations(station_groups):
    """Merges station groups that share physical coordinates."""
    # (Simplified for modular reuse, full logic preserved below)
    print("Step 3: Merging interchange stations...")
    coord_to_groups = defaultdict(set)
    coord_to_station = {}
    
    for group_code, data in station_groups.items():
        for coord in data['coords']:
            coord_to_groups[coord].add(group_code)

    shared_coords = {coord: groups for coord, groups in coord_to_groups.items() if len(groups) > 1}

    if shared_coords:
        interchange_pairs = defaultdict(set)
        for coord, groups in shared_coords.items():
            groups_list = list(groups)
            for i in range(len(groups_list)):
                for j in range(i + 1, len(groups_list)):
                    interchange_pairs[groups_list[i]].add(groups_list[j])
                    interchange_pairs[groups_list[j]].add(groups_list[i])
        
        parent = {code: code for code in station_groups}
        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py
        
        for group_code, partners in interchange_pairs.items():
            for partner in partners:
                union(group_code, partner)
        
        root_to_members = defaultdict(set)
        for code in station_groups:
            root_to_members[find(code)].add(code)
            
        merged_count = 0
        for root, member_codes in root_to_members.items():
            if len(member_codes) > 1:
                merged_count += 1
                representative = min(member_codes, key=lambda c: len(station_groups[c]['name']))
                
                all_coords = list(set(coord for code in member_codes for coord in station_groups[code]['coords']))
                all_names = list(set(name for code in member_codes for name in station_groups[code]['all_names']))
                all_operators = list(set(op for code in member_codes for op in station_groups[code]['operators']))
                total_platforms = sum(station_groups[code]['platform_count'] for code in member_codes)
                
                station_groups[representative]['all_names'] = all_names
                station_groups[representative]['operators'] = all_operators
                station_groups[representative]['platform_count'] = total_platforms
                station_groups[representative]['coords'] = all_coords
                station_groups[representative]['merged_from'] = list(member_codes)
                
                for code in member_codes:
                    if code != representative:
                        del station_groups[code]
        print(f"Merged {merged_count} interchange groups")
        
    # Rebuild coordinate map
    for station_id, station in station_groups.items():
        for coord in station['coords']:
            coord_to_station[coord] = station_id
            
    return station_groups, coord_to_station

def build_graph(station_groups, coord_to_station, gdf_railroads):
    """Builds the final graph linking stations and railroads."""
    print("Step 4: Building NetworkX graph...")
    G = nx.Graph()
    for station_id, data in station_groups.items():
        G.add_node(
            station_id,
            node_type='station',
            lat=data['lat'],
            lon=data['lon'],
            name=data['name'],
            operators=data.get('operators', []),
        )

    # KD-Tree for spatial snapping
    all_station_coords = []
    coord_to_station_list = []
    for station_id, data in station_groups.items():
        for coord in data['coords']:
            all_station_coords.append(coord)
            coord_to_station_list.append(station_id)

    station_tree = cKDTree(np.array(all_station_coords))
    SNAP_THRESHOLD_DEG = 2e-6  # ~20cm

    infra_node_counter = 0
    infra_nodes = {}
    infra_coords_list = []
    infra_tree = None

    def get_or_create_infra_node(coord):
        nonlocal infra_node_counter, infra_tree
        if infra_coords_list:
            if infra_tree is None or len(infra_coords_list) > len(infra_tree.data):
                infra_tree = cKDTree(np.array(infra_coords_list))
            dist, idx = infra_tree.query(coord)
            if dist <= SNAP_THRESHOLD_DEG:
                return list(infra_nodes.values())[idx]
        
        infra_node_id = f"INFRA_{infra_node_counter}"
        infra_node_counter += 1
        infra_nodes[coord] = infra_node_id
        infra_coords_list.append(coord)
        G.add_node(infra_node_id, node_type='infrastructure', lat=coord[1], lon=coord[0])
        return infra_node_id

    for idx, rail in gdf_railroads.iterrows():
        if rail.geometry.geom_type != 'LineString':
            continue
        
        coords = list(rail.geometry.coords)
        start_coord = coords[0]
        end_coord = coords[-1]
        
        def resolve_endpoint(coord):
            if coord in coord_to_station:
                return coord_to_station[coord]
            dist, idx = station_tree.query(coord)
            if dist <= SNAP_THRESHOLD_DEG:
                return coord_to_station_list[idx]
            return get_or_create_infra_node(coord)
        
        start_node = resolve_endpoint(start_coord)
        end_node = resolve_endpoint(end_coord)
        
        if start_node == end_node:
            continue
        
        line_name = rail.get('N02_003')
        operator = rail.get('N02_004')
        
        if G.has_edge(start_node, end_node):
            if line_name and line_name not in G[start_node][end_node]['lines']:
                G[start_node][end_node]['lines'].append(line_name)
        else:
            G.add_edge(start_node, end_node, lines=[line_name] if line_name else [], operator=operator)
            
    return G

def process_japan(base_dir="datasets/japan", output_dir="datasets/japan"):
    base_dir = Path(base_dir)
    output_dir = Path(output_dir)
    output_path = output_dir / 'japan_rail_network.gpickle'

    # 1. Load
    gdf_stations, gdf_railroads = load_data(base_dir)
    if gdf_stations is None:
        return

    # 2. Group
    group_code_groups = group_stations(gdf_stations)

    # 3. Create Nodes
    station_groups = create_initial_nodes(group_code_groups)

    # 4. Merge
    station_groups, coord_to_station = merge_interchange_stations(station_groups)

    # 5. Build Graph
    G = build_graph(station_groups, coord_to_station, gdf_railroads)

    # 6. Export
    print(f"Graph stats: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    
    print(f"Exporting graph to {output_path}...")
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'wb') as f:
        pickle.dump(G, f)
    print("Export successful.")


if __name__ == "__main__":
    process_japan()
