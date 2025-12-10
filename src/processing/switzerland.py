
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

    # 3. Build
    G = build_graph(net_nodes, net_segments, station_abbreviation_set)

    # 4. Export
    print(f"Edges loaded: {G.number_of_edges()}")
    print(f"Connected components: {nx.number_connected_components(G)}")
    
    print(f"Exporting graph to {GRAPH_OUTPUT_PATH}...")
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(GRAPH_OUTPUT_PATH, 'wb') as f:
        pickle.dump(G, f)
    print("Export successful.")


if __name__ == "__main__":
    process_switzerland()
