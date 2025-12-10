
import json
import nbformat
import os
import glob

def fix_notebook():
    notebook_path = "Graph_Construction_Walkthrough/Switzerland_Construction_Story.ipynb"
    
    with open(notebook_path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)

    target_index = -1
    for i, cell in enumerate(nb.cells):
        if cell.cell_type == "code" and "dataset_selector" in cell.source and "widgets" in cell.source:
             target_index = i
             break
            
    if target_index != -1:
        print(f"Found target cell at index {target_index}")
        
        # New Source: The "Standard" Pattern (Explicit Output + Loose Observe + Strict Logic)
        new_source = """
import folium
import math
import pickle
import geopandas as gpd
import ipywidgets as widgets
from pathlib import Path
from IPython.display import display, clear_output

# ----------------- DATA PREP -----------------
# 1. Swisstopo Data
if 'net_segments' in locals():
    net_segments_wgs84 = net_segments.to_crs(4326)
else:
    net_segments_wgs84 = None
if 'net_nodes' in locals():
    net_nodes_wgs84 = net_nodes.to_crs(4326)
else:
    net_nodes_wgs84 = None

# 2. SBB Data (Load Pickle)
sbb_graph_path = Path("../datasets/switzerland/sbb_rail_network.gpickle")
G_sbb = None
if sbb_graph_path.exists():
    with open(sbb_graph_path, 'rb') as f:
        G_sbb = pickle.load(f)

# ----------------- MAP FUNCTIONS -----------------
def create_swisstopo_map():
    m = folium.Map(location=[46.8182, 8.2275], zoom_start=8, tiles='CartoDB Positron', prefer_canvas=True)
    if net_segments_wgs84 is not None:
        edges_layer = folium.FeatureGroup(name="Swisstopo Edges")
        lines = []
        for geom in net_segments_wgs84.geometry:
            if geom and not geom.is_empty:
                coord_list = []
                if geom.geom_type == 'LineString': coord_list.append(geom)
                elif geom.geom_type == 'MultiLineString': coord_list.extend(geom.geoms)
                for part in coord_list:
                    coords = [(y, x) for x, y in part.coords if not (math.isnan(x) or math.isnan(y))]
                    if coords: lines.append(coords)
        if lines:
             folium.PolyLine(lines, color='gray', weight=2, opacity=0.6).add_to(edges_layer)
        edges_layer.add_to(m)

    if net_nodes_wgs84 is not None:
        nodes_layer = folium.FeatureGroup(name="Swisstopo Nodes")
        for idx, row in net_nodes_wgs84.iterrows():
            if row.geometry and not row.geometry.is_empty:
                y, x = row.geometry.y, row.geometry.x
                if not (math.isnan(y) or math.isnan(x)):
                     folium.Circle([y,x], radius=15, color='#3388ff', fill=True, fill_opacity=0.8, weight=0, tooltip="Swisstopo Node").add_to(nodes_layer)
        nodes_layer.add_to(m)
    return m

def create_sbb_map():
    m = folium.Map(location=[46.8182, 8.2275], zoom_start=8, tiles='CartoDB Positron', prefer_canvas=True)
    if G_sbb:
        edges_layer = folium.FeatureGroup(name="SBB Edges")
        nodes_layer = folium.FeatureGroup(name="SBB Nodes")
        positions = {}
        for n, data in G_sbb.nodes(data=True):
            lat, lon = data.get('lat'), data.get('lon')
            if lat is not None and lon is not None: positions[n] = (lat, lon)
            
        lines = []
        for u, v in G_sbb.edges():
            if u in positions and v in positions: lines.append([positions[u], positions[v]])
        if lines:
            folium.PolyLine(lines, color='#6c757d', weight=2, opacity=0.5).add_to(edges_layer)
        edges_layer.add_to(m)
        
        for n, pos in positions.items():
             folium.Circle(pos, radius=15, color='#e6194b', fill=True, fill_opacity=0.8, weight=0, tooltip=str(n)).add_to(nodes_layer)
        nodes_layer.add_to(m)
    return m

# ----------------- UI LOGIC -----------------
selector = widgets.RadioButtons(
    options=['Swisstopo (Nationwide Graph)', 'SBB (Legacy Graph)'],
    value='Swisstopo (Nationwide Graph)',
    description='Dataset:',
    disabled=False
)

out = widgets.Output()

def on_change(change):
    # STRICT Filtering: Only proceed if the 'value' changed
    if change['name'] == 'value' and change['type'] == 'change':
        with out:
            clear_output() # Wipe perfectly
            if 'Swisstopo' in change['new']:
                display(create_swisstopo_map())
            else:
                display(create_sbb_map())

# Attach observer
selector.observe(on_change)

# Initial Display
display(selector)
display(out)
with out:
    clear_output()
    display(create_swisstopo_map())
"""
        nb.cells[target_index].source = new_source
        nb.cells[target_index].outputs = [] 
        
        with open(notebook_path, "w", encoding="utf-8") as f:
            nbformat.write(nb, f)
        print("Successfully updated Switzerland Map 1 to Proven Pattern.")
    else:
        print("Could not find Map 1 cell.")

    # Cleanup Old Scripts
    os.system("rm scripts/fix_switzerland_map1_broken.py 2>/dev/null") 

if __name__ == "__main__":
    fix_notebook()
