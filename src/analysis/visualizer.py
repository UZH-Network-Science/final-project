import folium
import matplotlib.pyplot as plt
import pandas as pd
import json
import networkx as nx
import numpy as np
from ipyleaflet import Map, basemaps, GeoJSON, WidgetControl
from ipywidgets import FloatSlider, Dropdown, VBox, HBox, HTML, Checkbox, Layout, Button, jslink
from IPython.display import display

class NetworkVisualizer:
    def __init__(self):
        pass

    def plot_map(self, G, node_color='#1f77b4', edge_color='#6c757d', title="Network Map"):
        """
        Generates a static Folium map.
        """
        lats = [d['lat'] for n, d in G.nodes(data=True) if 'lat' in d]
        lons = [d['lon'] for n, d in G.nodes(data=True) if 'lon' in d]
        
        if not lats:
            return folium.Map()

        center = [sum(lats)/len(lats), sum(lons)/len(lons)]
        m = folium.Map(location=center, zoom_start=8, tiles='CartoDB Positron')
        
        # Edges
        edges_fg = folium.FeatureGroup(name="Edges")
        for u, v in G.edges():
            if 'lat' in G.nodes[u] and 'lat' in G.nodes[v]:
                p1 = (G.nodes[u]['lat'], G.nodes[u]['lon'])
                p2 = (G.nodes[v]['lat'], G.nodes[v]['lon'])
                folium.PolyLine([p1, p2], color=edge_color, weight=1, opacity=0.5).add_to(edges_fg)
        edges_fg.add_to(m)
        
        # Nodes 
        nodes_fg = folium.FeatureGroup(name="Nodes")
        for n, d in G.nodes(data=True):
             if 'lat' in d:
                folium.CircleMarker(
                    location=[d['lat'], d['lon']],
                    radius=2,
                    color=node_color,
                    fill=True,
                    popup=str(n)
                ).add_to(nodes_fg)
        nodes_fg.add_to(m)
        
        folium.LayerControl().add_to(m)
        return m

    def create_interactive_map_ui(self, G):
        """
        Creates an interactive ipyleaflet map with sliders for robustness analysis.
        """
        # Pre-process coordinates for speed
        geojson_pos = {}
        lats, lons = [], []
        for n, d in G.nodes(data=True):
            if 'lat' in d and 'lon' in d:
                # GeoJSON uses (Lon, Lat)
                geojson_pos[n] = (d['lon'], d['lat'])
                lats.append(d['lat'])
                lons.append(d['lon'])
        
        if not lats:
            print("No coordinates found in graph.")
            return None

        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)

        # Pre-calculate centralities
        print("Calculating centralities for interactive map...")
        # Note: For large graphs like Japan (20k), Betweenness is slow. 
        # We handle this by checking graph size or caching if possible.
        # For uniformity, we run it but warn.
        degree_cent = nx.degree_centrality(G)
        
        if len(G) > 5000:
            print("Graph is large (>5k nodes). Skipping calculate-on-the-fly Betweenness for interactivity speed.")
            # Fallback to degree for betweenness placeholder or just empty
            betweenness_cent = degree_cent 
        else:
            betweenness_cent = nx.betweenness_centrality(G)

        sorted_degree = sorted(degree_cent, key=degree_cent.get, reverse=True)
        sorted_betweenness = sorted(betweenness_cent, key=betweenness_cent.get, reverse=True)
        all_nodes = list(G.nodes())

        # 1. Initialize Map
        m = Map(center=(center_lat, center_lon), zoom=8, basemap=basemaps.CartoDB.Positron, scroll_wheel_zoom=True)
        m.layout.height = '600px'

        # 2. Layers
        style_core = {'color': 'blue', 'weight': 1, 'opacity': 0.6}
        style_iso = {'color': 'red', 'weight': 1, 'opacity': 0.6}
        style_node_core = {'radius': 3, 'color': 'blue', 'fillColor': 'blue', 'fillOpacity': 0.8}
        style_node_iso = {'radius': 3, 'color': 'red', 'fillColor': 'red', 'fillOpacity': 0.8}

        layer_edges_core = GeoJSON(data={'type': 'FeatureCollection', 'features': []}, style=style_core, name='Edges (Core)')
        layer_edges_iso = GeoJSON(data={'type': 'FeatureCollection', 'features': []}, style=style_iso, name='Edges (Isolated)')
        layer_nodes_core = GeoJSON(data={'type': 'FeatureCollection', 'features': []}, point_style=style_node_core, name='Nodes (Core)')
        layer_nodes_iso = GeoJSON(data={'type': 'FeatureCollection', 'features': []}, point_style=style_node_iso, name='Nodes (Isolated)')

        m.add_layer(layer_edges_core)
        m.add_layer(layer_edges_iso)
        m.add_layer(layer_nodes_core)
        m.add_layer(layer_nodes_iso)

        # 3. Legend Widget (simplified)
        html_legend = HTML('''
            <div style="background:white; padding:5px; border:1px solid #ccc; border-radius:5px;">
                <b>Legend</b><br>
                <i style="background:blue; width:10px; height:10px; display:inline-block; border-radius:50%;"></i> Core<br>
                <i style="background:red; width:10px; height:10px; display:inline-block; border-radius:50%;"></i> Isolated
            </div>
        ''')
        m.add_control(WidgetControl(widget=html_legend, position='topright'))

        # 4. Update Logic
        def update_layers(strategy, fraction):
            num_remove = int(len(G) * fraction)
            G_temp = G.copy()
            
            remove_nodes = []
            if strategy == "Random":
                np.random.seed(42)
                remove_nodes = np.random.choice(all_nodes, num_remove, replace=False)
            elif strategy == "Targeted (Degree)":
                remove_nodes = sorted_degree[:num_remove]
            elif strategy == "Targeted (Betweenness)":
                remove_nodes = sorted_betweenness[:num_remove]
            
            G_temp.remove_nodes_from(remove_nodes)
            
            if len(G_temp) > 0:
                largest_cc = max(nx.connected_components(G_temp), key=len)
                lcc_set = set(largest_cc)
            else:
                lcc_set = set()

            # GeoJSON construction
            # Optimization: Only plot a subset if graph is huge? 
            # For now, plot all but be aware of browser limit.
            
            core_features = []
            iso_features = []
            
            # Edges
            for u, v in G.edges(): # Use original edges, check if nodes exist in G_temp
                if u in G_temp and v in G_temp: # Both nodes survived
                    if u in geojson_pos and v in geojson_pos:
                        coords = [geojson_pos[u], geojson_pos[v]]
                        feat = {'type': 'Feature', 'geometry': {'type': 'MultiLineString', 'coordinates': [coords]}, 'properties': {}}
                        if u in lcc_set:
                            core_features.append(feat)
                        else:
                            iso_features.append(feat)
            
            layer_edges_core.data = {'type': 'FeatureCollection', 'features': core_features}
            layer_edges_iso.data = {'type': 'FeatureCollection', 'features': iso_features}
            
            # Nodes (Optional: Plotting all nodes can be heavy)
            # Let's skip nodes for performance on large graphs, or simplified
            
        # 5. Controls
        strat_dd = Dropdown(options=['Random', 'Targeted (Degree)', 'Targeted (Betweenness)'], value='Random', description='Strategy:')
        frac_sl = FloatSlider(min=0.0, max=0.5, step=0.05, value=0.0, description='Fraction:')
        
        def on_change(change):
            update_layers(strat_dd.value, frac_sl.value)
            
        strat_dd.observe(on_change, names='value')
        frac_sl.observe(on_change, names='value')
        
        # Initial draw
        update_layers('Random', 0.0)
        
        display(VBox([strat_dd, frac_sl]))
        display(m)

    def plot_efficiency_decay(self, results_dict, title="Network Efficiency Decay", ylabel="Global Efficiency"):
        """
        Plots multiple curves from a dictionary of results.
        results_dict: { 'Label': {'0.0': 1.0, '0.1': 0.8...} }
        """
        plt.figure(figsize=(10, 6))
        
        # Define some default styles if config is not passed
        markers = ['o', 's', '^', 'D', 'x']
        colors = ['green', 'red', 'orange', 'purple', 'blue']
        
        for i, (label, data) in enumerate(results_dict.items()):
            # Filter and sort
            sorted_items = []
            for k, v in data.items():
                try:
                    sorted_items.append((float(k), v))
                except ValueError:
                    continue
            sorted_items.sort()
            
            if not sorted_items:
                continue
                
            features, values = zip(*sorted_items)
            
            marker = markers[i % len(markers)]
            color = colors[i % len(colors)]
            
            plt.plot(features, values, marker=marker, linestyle='-', label=label, color=color, alpha=0.8)
            
        plt.title(title)
        plt.xlabel("Fraction of Nodes Removed")
        plt.ylabel(ylabel)
        plt.grid(True, linestyle='--', alpha=0.3)
        plt.show()

    def create_component_map(self, G):
        """
        Creates a map showing the Largest Connected Component (Blue) and Isolated Components (Red).
        No interactive attack simulation controls.
        """
        # Pre-process coordinates
        geojson_pos = {}
        lats, lons = [], []
        for n, d in G.nodes(data=True):
            if 'lat' in d and 'lon' in d:
                geojson_pos[n] = (d['lon'], d['lat'])
                lats.append(d['lat'])
                lons.append(d['lon'])
        
        if not lats:
            return None

        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)

        # 1. Initialize Map
        m = Map(center=(center_lat, center_lon), zoom=8, basemap=basemaps.CartoDB.Positron, scroll_wheel_zoom=True)
        m.layout.height = '600px'

        # 2. Styles
        style_core = {'color': 'blue', 'weight': 1, 'opacity': 0.6}
        style_iso = {'color': 'red', 'weight': 1, 'opacity': 0.6}
        style_node_core = {'radius': 6, 'color': 'blue', 'fillColor': 'blue', 'fillOpacity': 0.8}
        style_node_iso = {'radius': 6, 'color': 'red', 'fillColor': 'red', 'fillOpacity': 0.8}

        # 3. Calculate Components (Initial State)
        if len(G) > 0:
            largest_cc = max(nx.connected_components(G), key=len)
            lcc_set = set(largest_cc)
        else:
            lcc_set = set()

        # 4. Construct Features
        core_edges = []
        iso_edges = []
        core_nodes = []
        iso_nodes = []

        # Edges
        for u, v in G.edges():
            if u in geojson_pos and v in geojson_pos:
                coords = [geojson_pos[u], geojson_pos[v]]
                feat = {'type': 'Feature', 'geometry': {'type': 'MultiLineString', 'coordinates': [coords]}, 'properties': {}}
                if u in lcc_set and v in lcc_set:
                    core_edges.append(feat)
                else:
                    iso_edges.append(feat)
        
        # Nodes
        # For the construction story, visualization of nodes is important context
        for n in G.nodes():
            if n in geojson_pos:
                feat = {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': geojson_pos[n]}, 'properties': {}}
                if n in lcc_set:
                    core_nodes.append(feat)
                else:
                    iso_nodes.append(feat)

        # 5. Layers
        layer_edges_core = GeoJSON(data={'type': 'FeatureCollection', 'features': core_edges}, style=style_core, name='Edges (Core)')
        layer_edges_iso = GeoJSON(data={'type': 'FeatureCollection', 'features': iso_edges}, style=style_iso, name='Edges (Isolated)')
        
        # Note: Point styling in GeoJSON layer is done via point_style
        layer_nodes_core = GeoJSON(data={'type': 'FeatureCollection', 'features': core_nodes}, point_style=style_node_core, name='Nodes (Core)')
        layer_nodes_iso = GeoJSON(data={'type': 'FeatureCollection', 'features': iso_nodes}, point_style=style_node_iso, name='Nodes (Isolated)')

        m.add_layer(layer_edges_core)
        m.add_layer(layer_edges_iso)
        m.add_layer(layer_nodes_core)
        m.add_layer(layer_nodes_iso)

        # 6. Legend
        html_legend = HTML('''
            <div style="background:white; padding:5px; border:1px solid #ccc; border-radius:5px;">
                <b>Components</b><br>
                <i style="background:blue; width:10px; height:10px; display:inline-block; border-radius:50%;"></i> Largest<br>
                <i style="background:red; width:10px; height:10px; display:inline-block; border-radius:50%;"></i> Isolated
            </div>
        ''')
        m.add_control(WidgetControl(widget=html_legend, position='topright'))
        
        return m

