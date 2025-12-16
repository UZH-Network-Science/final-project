import folium
import matplotlib.pyplot as plt
import pandas as pd
import json
import networkx as nx
import numpy as np
from ipyleaflet import Map, basemaps, GeoJSON, WidgetControl
from ipywidgets import FloatSlider, Dropdown, VBox, HBox, HTML, Checkbox, Layout, Button, jslink, Output, Accordion
from IPython.display import display, clear_output

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
        Includes Visual Layer Control (Checkboxes) and Finite-Step Slider.
        Updated to match Comparison_Analysis features (Ghost nodes, Stable Random, correct Z-order).
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
        degree_cent = nx.degree_centrality(G)
        articulation_points = set(nx.articulation_points(G))
        
        # Removed limit per user request - Always show nodes
        # Use degree as proxy for betweenness if too large, but still allow interaction
        if len(G) > 5000:
            print("Graph is large (>5k nodes). using degree as proxy for betweenness for initial load speed.")
            betweenness_cent = degree_cent 
        else:
            betweenness_cent = nx.betweenness_centrality(G)

        sorted_degree = sorted(degree_cent, key=degree_cent.get, reverse=True)
        sorted_betweenness = sorted(betweenness_cent, key=betweenness_cent.get, reverse=True)
        
        # Pre-sort for Articulation Strategy
        ap_list = sorted([n for n in articulation_points], key=degree_cent.get, reverse=True)
        others = sorted([n for n in degree_cent if n not in articulation_points], key=degree_cent.get, reverse=True)
        sorted_articulation = ap_list + others
        
        all_nodes = list(G.nodes())

        # 1. Initialize Map
        m = Map(center=(center_lat, center_lon), zoom=8, basemap=basemaps.CartoDB.Positron, scroll_wheel_zoom=True)
        m.layout.height = '700px'

        # 2. Layers
        style_blue_edge = {'color': 'blue', 'weight': 1, 'opacity': 0.6}
        style_red_edge = {'color': 'red', 'weight': 1, 'opacity': 0.6}
        style_blue_node = {'radius': 3, 'color': 'blue', 'fillColor': 'blue', 'fillOpacity': 0.8, 'weight': 1}
        style_red_node = {'radius': 3, 'color': 'red', 'fillColor': 'red', 'fillOpacity': 0.8, 'weight': 1}
        style_gray_node = {'radius': 2, 'color': '#999999', 'fillColor': '#999999', 'fillOpacity': 0.3, 'weight': 1}

        layer_nodes_removed = GeoJSON(data={'type': 'FeatureCollection', 'features': []}, point_style=style_gray_node, name='Nodes (Removed)')
        layer_edges_blue = GeoJSON(data={'type': 'FeatureCollection', 'features': []}, style=style_blue_edge, name='Edges (Core)')
        layer_edges_red = GeoJSON(data={'type': 'FeatureCollection', 'features': []}, style=style_red_edge, name='Edges (Isolated)')
        layer_nodes_blue = GeoJSON(data={'type': 'FeatureCollection', 'features': []}, point_style=style_blue_node, name='Nodes (Core)')
        layer_nodes_red = GeoJSON(data={'type': 'FeatureCollection', 'features': []}, point_style=style_red_node, name='Nodes (Isolated)')

        # Z-Order: Bottom -> Top
        m.add_layer(layer_nodes_removed)
        m.add_layer(layer_edges_blue)
        m.add_layer(layer_edges_red)
        m.add_layer(layer_nodes_red)
        m.add_layer(layer_nodes_blue)

        # 3. Consolidated Legend & Layer Control
        def legend_icon(color, shape='line'):
            if shape == 'line':
                return f'<i style="background: {color}; width: 25px; height: 3px; display: inline-block; vertical-align: middle; margin-right: 5px;"></i>'
            else:
                return f'<i style="background: {color}; width: 10px; height: 10px; display: inline-block; border-radius: 50%; vertical-align: middle; margin-right: 5px;"></i>'

        # Granular Controls (Restored & Enhanced)
        check_edges_blue = Checkbox(value=True, indent=False, layout=Layout(width='30px'))
        check_edges_red = Checkbox(value=True, indent=False, layout=Layout(width='30px'))
        check_nodes_blue = Checkbox(value=True, indent=False, layout=Layout(width='30px'))
        check_nodes_red = Checkbox(value=True, indent=False, layout=Layout(width='30px'))
        check_nodes_rem = Checkbox(value=True, indent=False, layout=Layout(width='30px')) # New

        label_edges_blue = HTML(f"{legend_icon('blue', 'line')} <b>Core Edges</b>")
        label_edges_red = HTML(f"{legend_icon('red', 'line')} <b>Isolated Edges</b>")
        label_nodes_blue = HTML(f"{legend_icon('blue', 'circle')} <b>Core Nodes</b>")
        label_nodes_red = HTML(f"{legend_icon('red', 'circle')} <b>Isolated Nodes</b>")
        label_nodes_rem = HTML(f"{legend_icon('#999999', 'circle')} <b>Removed Nodes</b>")

        # Native Visibility Linking (Faster/Smoother than Python updates)
        jslink((check_edges_blue, 'value'), (layer_edges_blue, 'visible'))
        jslink((check_edges_red, 'value'), (layer_edges_red, 'visible'))
        jslink((check_nodes_blue, 'value'), (layer_nodes_blue, 'visible'))
        jslink((check_nodes_red, 'value'), (layer_nodes_red, 'visible'))
        jslink((check_nodes_rem, 'value'), (layer_nodes_removed, 'visible'))

        row_1 = HBox([check_edges_blue, label_edges_blue], layout=Layout(align_items='center'))
        row_2 = HBox([check_edges_red, label_edges_red], layout=Layout(align_items='center'))
        row_3 = HBox([check_nodes_blue, label_nodes_blue], layout=Layout(align_items='center'))
        row_4 = HBox([check_nodes_red, label_nodes_red], layout=Layout(align_items='center'))
        row_5 = HBox([check_nodes_rem, label_nodes_rem], layout=Layout(align_items='center'))

        layer_control_box = VBox([
            HTML(value="<b>Network Legend</b>"),
            row_1, row_2, row_3, row_4, row_5
        ])
        
        layer_control_box.layout.padding = '5px'
        layer_control_box.layout.background_color = 'white'
        layer_control_box.layout.border = '2px solid #ccc'
        layer_control_box.layout.border_radius = '5px'

        m.add_control(WidgetControl(widget=layer_control_box, position='topright'))

        # 4. Controls (Strategy/Slider)
        strat_dd = Dropdown(options=['Random', 'Targeted (Degree)', 'Targeted (Betweenness)', 'Targeted (Articulation)', 'Targeted (Inverse Degree)', 'Targeted (Inverse Betweenness)'], value='Random', description='Strategy:')
        frac_sl = FloatSlider(min=0.0, max=0.9, step=0.01, value=0.0, description='Fraction:', layout=Layout(flex='3'))
        
        btn_minus = Button(description='-', layout=Layout(width='40px'))
        btn_plus = Button(description='+', layout=Layout(width='40px'))
        
        def on_minus(b):
            new_val = round(max(frac_sl.min, frac_sl.value - 0.01), 2)
            frac_sl.value = new_val
            
        def on_plus(b):
            new_val = round(min(frac_sl.max, frac_sl.value + 0.01), 2)
            frac_sl.value = new_val
            
        btn_minus.on_click(on_minus)
        btn_plus.on_click(on_plus)

        # 5. Update Logic
        def update_layers(change=None):
            # Arguments from widgets
            strategy = strat_dd.value
            fraction = frac_sl.value
            
            # Note: Visibility is handled by jslink on the client side now.
            # We always populate the data layers.

            num_remove = int(len(G) * fraction)
            G_temp = G.copy()
            
            remove_nodes = []
            if strategy == "Random":
                # Stable Random Sampling
                rng = np.random.RandomState(42)
                permuted_nodes = rng.permutation(all_nodes)
                remove_nodes = permuted_nodes[:num_remove]
            elif strategy == "Targeted (Degree)":
                remove_nodes = sorted_degree[:num_remove]
            elif strategy == "Targeted (Betweenness)":
                remove_nodes = sorted_betweenness[:num_remove]
            elif strategy == "Targeted (Inverse Degree)":
                remove_nodes = sorted_degree[-num_remove:] if num_remove > 0 else []
            elif strategy == "Targeted (Inverse Betweenness)":
                remove_nodes = sorted_betweenness[-num_remove:] if num_remove > 0 else []
            elif strategy == "Targeted (Articulation)":
                remove_nodes = sorted_articulation[:num_remove]
            
            remove_set = set(remove_nodes)
            G_temp.remove_nodes_from(remove_nodes)
            
            if len(G_temp) > 0:
                largest_cc = max(nx.connected_components(G_temp), key=len)
                lcc_set = set(largest_cc)
            else:
                lcc_set = set()

            # GeoJSON construction
            blue_lines, red_lines = [], []
            blue_pts, red_pts, gray_pts = [], [], []

            # 1. Edges
            for u, v in G.edges(): 
                if u in G_temp and v in G_temp: 
                    if u in geojson_pos and v in geojson_pos:
                        coords = [geojson_pos[u], geojson_pos[v]]
                        if u in lcc_set and v in lcc_set:
                            blue_lines.append(coords)
                        else:
                            red_lines.append(coords)
            
            # 2. Nodes (Active)
            for n in G_temp.nodes():
                if n in geojson_pos:
                    pt = geojson_pos[n]
                    if n in lcc_set:
                        blue_pts.append(pt)
                    else:
                        red_pts.append(pt)
            
            # 3. Nodes (Removed)
            for n in remove_set:
                if n in geojson_pos:
                    gray_pts.append(geojson_pos[n])

            # Update Layers
            layer_nodes_removed.data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiPoint', 'coordinates': gray_pts}, 'properties': {}}]} if gray_pts else {'type': 'FeatureCollection', 'features': []}
            
            layer_edges_blue.data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiLineString', 'coordinates': blue_lines}, 'properties': {}}]} if blue_lines else {'type': 'FeatureCollection', 'features': []}
            layer_edges_red.data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiLineString', 'coordinates': red_lines}, 'properties': {}}]} if red_lines else {'type': 'FeatureCollection', 'features': []}
            
            layer_nodes_red.data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiPoint', 'coordinates': red_pts}, 'properties': {}}]} if red_pts else {'type': 'FeatureCollection', 'features': []}
            layer_nodes_blue.data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiPoint', 'coordinates': blue_pts}, 'properties': {}}]} if blue_pts else {'type': 'FeatureCollection', 'features': []}
            
        strat_dd.observe(update_layers, names='value')
        frac_sl.observe(update_layers, names='value')
        
        # Initial draw
        update_layers()
        
        slider_row = HBox([frac_sl, btn_minus, btn_plus])
        display(VBox([strat_dd, slider_row]))
        display(m)

    def plot_metric_decay(self, results_dict, title="Metric Decay", ylabel="Value", log_x=True):
        """
        Plots multiple curves from a dictionary of results with interactive controls.
        results_dict: { 'Label': {'0.0': 1.0, '0.1': 0.8...} }
        """
        # Prepare data first
        plot_data = []
        plot_data = []
        # Extended palette for many lines (Tab20-like + others)
        colors = [
            '#1f77b4', '#aec7e8', '#ff7f0e', '#ffbb78', '#2ca02c', '#98df8a',
            '#d62728', '#ff9896', '#9467bd', '#c5b0d5', '#8c564b', '#c49c94',
            '#e377c2', '#f7b6d2', '#7f7f7f', '#c7c7c7', '#bcbd22', '#dbdb8d',
            '#17becf', '#9edae5', 'black', 'navy'
        ]
        markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h', 'H', '+', 'x', 'd', '|', '_']
        
        for i, (label, data) in enumerate(results_dict.items()):
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
            plot_data.append({
                'label': label,
                'x': features,
                'y': values,
                'marker': markers[i % len(markers)],
                'color': colors[i % len(colors)],
                'linestyle': '-' if 'Switzerland' in label else '--' if 'Japan' in label else ':'
            })
            
        # Create Widgets
        out = Output(layout=Layout(width='100%'))
        checkboxes = {}
        for item in plot_data:
            checkboxes[item['label']] = Checkbox(
                value=True,
                description=item['label'],
                indent=False,
                layout=Layout(width='auto', margin='0 10px 0 0')
            )
            
        def update_plot(change=None):
            with out:
                clear_output(wait=True)
                plt.figure(figsize=(15, 6))
                
                has_plot = False
                for item in plot_data:
                    if checkboxes[item['label']].value:
                        x = np.array(item['x'])
                        y = np.array(item['y'])
                        
                        # Split zero and non-zero
                        # Assuming sorted, 0.0 is at index 0 if present
                        if len(x) > 0 and x[0] <= 1e-9:
                            # Plot zero point separately (scatter, no line)
                            plt.plot(
                                [x[0]], [y[0]], 
                                marker=item['marker'], 
                                linestyle='None', 
                                label=item['label'], # Label only one to avoid dup in legend
                                color=item['color'], 
                                alpha=0.8,
                                clip_on=False  # Allow point on axis to be fully visible
                            )
                            # Plot rest as line
                            if len(x) > 1:
                                plt.plot(
                                    x[1:], y[1:], 
                                    marker=item['marker'], 
                                    linestyle=item['linestyle'], 
                                    label='_nolegend_', 
                                    color=item['color'], 
                                    alpha=0.8
                                )
                        else:
                            # Standard plot
                            plt.plot(
                                x, y, 
                                marker=item['marker'], 
                                linestyle='-', 
                                label=item['label'], 
                                color=item['color'], 
                                alpha=0.8
                            )
                        has_plot = True
                
                if has_plot:
                    # Create custom legend handle for the Start Point
                    from matplotlib.lines import Line2D
                    
                    # Get existing handles/labels
                    handles, labels = plt.gca().get_legend_handles_labels()
                    
                    # Add Initial State handle
                    start_handle = Line2D([], [], color='gray', marker='H', linestyle='None', 
                                          markersize=8, label='Initial State')
                    handles.append(start_handle)
                    labels.append('Initial State')
                    
                    plt.legend(handles=handles, labels=labels)
                    
                # Manual Grid Lines for every point (x-axis)
                all_fractions = set()
                first_nonzero = None
                
                for item in plot_data:
                    if checkboxes[item['label']].value:
                        x = np.array(item['x'])
                        y = np.array(item['y'])
                        
                        # Split zero and non-zero
                        if len(x) > 0 and x[0] <= 1e-9:
                            # Plot zero point separately (scatter, no line)
                            # User requested Hexagon for the start point
                            plt.plot(
                                [x[0]], [y[0]], 
                                marker='H',  # Force Hexagon
                                linestyle='None', 
                                label='_nolegend_', 
                                color=item['color'], 
                                alpha=0.8,
                                clip_on=False,
                                markersize=8
                            )
                            # Plot rest as line
                            if len(x) > 1:
                                plt.plot(
                                    x[1:], y[1:], 
                                    marker=item['marker'], 
                                    linestyle=item['linestyle'], 
                                    label=item['label'], 
                                    color=item['color'], 
                                    alpha=0.8
                                )
                        else:
                            # Standard plot
                            plt.plot(
                                x, y, 
                                marker=item['marker'], 
                                linestyle=item['linestyle'], 
                                label=item['label'], 
                                color=item['color'], 
                                alpha=0.8
                            )
                        has_plot = True
                if log_x:
                    plt.xlabel("Fraction of Nodes Removed (Log Scale)")
                    # Use symlog to handle 0.0 correctly
                    # linthresh=0.05 makes the 0-0.05 gap linear
                    # linscale=0.05 compresses this linear region even more
                    plt.xscale('symlog', linthresh=0.05, linscale=0.05)
                    # Start exactly at 0
                    plt.xlim(left=0.0)
                    
                    # Custom Ticks
                    ticks = [0, 0.1, 1.0]
                    labels = ['0', '$10^{-1}$', '$10^{0}$']
                    
                    # Add first non-zero point label if valid
                    if first_nonzero is not None and first_nonzero not in ticks:
                        ticks.append(first_nonzero)
                        # Format nicely (e.g., 0.05)
                        labels.append(f"{first_nonzero:.2g}")
                        
                        # Sort for display correctness (though matplotlib handles it)
                        combined = sorted(zip(ticks, labels))
                        ticks, labels = zip(*combined)

                    plt.xticks(ticks, labels)
                    plt.minorticks_off() # Turn off minor ticks to be clean
                else:
                    plt.xlabel("Fraction of Nodes Removed")
                    
                plt.ylabel(ylabel)
                # Only Y-axis grid from default, X is manual
                plt.grid(True, axis='y', linestyle='--', alpha=0.3)
                plt.tight_layout()
                plt.show()

        # Wire events
        for cb in checkboxes.values():
            cb.observe(update_plot, names='value')
            
        # Layout
        # Create a legend control box
        cb_list = list(checkboxes.values())
        # Arrange checkboxes in rows of 3 to avoid super long vertical lists if many lines
        rows = [HBox(cb_list[i:i+3]) for i in range(0, len(cb_list), 3)]
        controls_content = VBox([HTML(f"<b>{ylabel} - Show/Hide Lines:</b>")] + rows)
        
        # Wrap in Accordion to create a hidden menu
        menu = Accordion(children=[controls_content])
        menu.set_title(0, 'Plot Controls')
        menu.selected_index = None # Start collapsed
        
        display(menu, out)
        
        # Trigger initial plot
        update_plot()

    def plot_efficiency_decay(self, results_dict, title="Network Efficiency Decay", ylabel="Global Efficiency"):
        return self.plot_metric_decay(results_dict, title, ylabel)

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

    def plot_degree_distribution(self, G, bins=50, title="Degree Distribution"):
        """
        Plots the degree distribution of the network (Histogram and Log-Log).
        """
        degrees = [d for n, d in G.degree()]
        
        plt.figure(figsize=(12, 5))
        
        # 1. Linear Scale Histogram
        plt.subplot(1, 2, 1)
        plt.hist(degrees, bins=bins, color='skyblue', edgecolor='black')
        plt.title(f"{title} (Linear)")
        plt.xlabel("Degree")
        plt.ylabel("Count")
        
        # 2. Semi-Log Plot (Log Y)
        plt.subplot(1, 2, 2)
        
        # Use linear bins, same as left plot, but with log yScale
        plt.hist(degrees, bins=bins, color='salmon', edgecolor='black', log=True)
        plt.yscale('log')
        
        plt.title(f"{title} (Semi-Log)")
        plt.xlabel("Degree")
        plt.ylabel("Count (Log)")
        
        plt.grid(True, which="both", ls="--", alpha=0.3)
        plt.tight_layout()
        plt.show()

    def compare_interactive_maps(self, G1, G2, name1="Network 1", name2="Network 2"):
        """
        Creates a side-by-side interactive comparison of two networks under attack.
        Shared controls for Strategy and Fraction.
        """
        # --- Helper to Setup Data for a Graph ---
        def setup_graph_data(G):
            geojson_pos = {}
            lats, lons = [], []
            for n, d in G.nodes(data=True):
                if 'lat' in d and 'lon' in d:
                    geojson_pos[n] = (d['lon'], d['lat'])
                    lats.append(d['lat'])
                    lons.append(d['lon'])
            
            if not lats: return None, None, None, None, None, None

            center = (sum(lats)/len(lats), sum(lons)/len(lons))
            
            # Pre-calc strategies
            d_cent = nx.degree_centrality(G)
            
            # Fast approx for betweenness if large
            if len(G) > 5000:
                b_cent = d_cent # Fallback
            else:
                b_cent = nx.betweenness_centrality(G)
            
            # Pre-calc Articulation Points (used for Articulation Strategy)
            # Note: This can be slow for very massive graphs, but usually O(N+E)
            try:
                articulation_points = set(nx.articulation_points(G))
                # Sort articulation points by degree centrality (descending)
                ap_list = sorted([n for n in articulation_points], key=d_cent.get, reverse=True)
                # Add other nodes, also sorted by degree, after articulation points
                others = sorted([n for n in d_cent if n not in articulation_points], key=d_cent.get, reverse=True)
                sorted_articulation = ap_list + others
            except Exception: # Catch potential errors if graph is too simple or specific
                # Fallback to degree centrality if articulation points calculation fails
                sorted_articulation = sorted(d_cent, key=d_cent.get, reverse=True)


            sorted_deg = sorted(d_cent, key=d_cent.get, reverse=True)
            sorted_bet = sorted(b_cent, key=b_cent.get, reverse=True)
            
            all_nodes = list(G.nodes())
            
            return geojson_pos, center, sorted_deg, sorted_bet, sorted_articulation, all_nodes

        # Setup Data
        pos1, center1, deg1, bet1, art1, nodes1 = setup_graph_data(G1)
        pos2, center2, deg2, bet2, art2, nodes2 = setup_graph_data(G2)
        
        if not pos1 or not pos2:
            print("Error: Missing coordinates.")
            return None

        # --- Helper to Create Layers ---
        def create_layers(m, color_core, color_iso):
            l_edges_core = GeoJSON(data={'type': 'FeatureCollection', 'features': []}, 
                                  style={'color': color_core, 'weight': 1, 'opacity': 0.6}, name='Edges (Core)')
            l_edges_iso = GeoJSON(data={'type': 'FeatureCollection', 'features': []}, 
                                 style={'color': color_iso, 'weight': 1, 'opacity': 0.6}, name='Edges (Iso)')
            l_nodes_core = GeoJSON(data={'type': 'FeatureCollection', 'features': []}, 
                                  point_style={'radius': 3, 'color': color_core, 'fillColor': color_core, 'fillOpacity': 0.8}, name='Nodes (Core)')
            l_nodes_iso = GeoJSON(data={'type': 'FeatureCollection', 'features': []},
                                 point_style={'radius': 4, 'color': color_iso, 'fillColor': color_iso, 'fillOpacity': 0.8}, name='Nodes (Iso)')
            l_nodes_removed = GeoJSON(data={'type': 'FeatureCollection', 'features': []},
                                     point_style={'radius': 2, 'color': '#999999', 'fillColor': '#999999', 'fillOpacity': 0.3}, name='Nodes (Removed)')
            
            # Order: Edges first, then Removed nodes (background), then Active nodes (foreground)
            # Fix: Add layers from Bottom (Background) to Top (Foreground).
            # Last added/updated = Top.
            m.add_layer(l_nodes_removed) 
            m.add_layer(l_edges_core)
            m.add_layer(l_edges_iso)
            m.add_layer(l_nodes_iso)
            m.add_layer(l_nodes_core)
            
            return l_edges_core, l_edges_iso, l_nodes_core, l_nodes_iso, l_nodes_removed

        # Initialize Maps
        # Zoom Customization based on User Feedback: Japan needs to be zoomed out more.
        # Default zoom was 7. Request: "minus 2 times" -> Zoom 5.
        zoom1 = 7 # Switzerland likely fine
        zoom2 = 5 # Japan (Network 2) zoomed out
        
        m1 = Map(center=center1, zoom=zoom1, basemap=basemaps.CartoDB.Positron)
        m2 = Map(center=center2, zoom=zoom2, basemap=basemaps.CartoDB.Positron)
        
        m1.layout.height = '600px'
        m2.layout.height = '600px'
        m1.layout.width = '100%'
        m2.layout.width = '100%'

        # Create Layers
        layers1 = create_layers(m1, 'blue', 'red')
        layers2 = create_layers(m2, 'blue', 'red')

        # --- Update Logic ---
        def get_geo_updates(G, pos, strategy_type, fraction, sorted_degree, sorted_betweenness, sorted_articulation, all_nodes_list):
            num_remove = int(len(G) * fraction)
            remove_nodes = []
            
            if strategy_type == "Random":
                # Deterministic random for stability in UI
                rng = np.random.RandomState(42) 
                # Use permutation to ensure subset stability (if frac 0.1 -> 0.2, the 0.1 nodes are still removed)
                permuted_nodes = rng.permutation(all_nodes_list)
                remove_nodes = permuted_nodes[:num_remove]
            elif strategy_type == "Targeted (Degree)":
                remove_nodes = sorted_degree[:num_remove]
            elif strategy_type == "Targeted (Betweenness)":
                remove_nodes = sorted_betweenness[:num_remove]
            elif strategy_type == "Inverse Targeted (Degree)":
                 remove_nodes = sorted_degree[-num_remove:] if num_remove > 0 else []
            elif strategy_type == "Inverse Targeted (Betweenness)":
                 remove_nodes = sorted_betweenness[-num_remove:] if num_remove > 0 else []
            elif strategy_type == "Targeted (Articulation)":
                remove_nodes = sorted_articulation[:num_remove]
            
            remove_set = set(remove_nodes)
            G_temp = G.copy()
            G_temp.remove_nodes_from(remove_nodes)
            
            if len(G_temp) > 0:
                largest_cc = max(nx.connected_components(G_temp), key=len)
                lcc_set = set(largest_cc)
            else:
                lcc_set = set()
                
            # Build Features
            core_lines, iso_lines = [], []
            core_pts, iso_pts, removed_pts = [], [], []
            
            for u, v in G.edges():
                if u in G_temp and v in G_temp:
                    if u in pos and v in pos:
                        coords = [pos[u], pos[v]]
                        if u in lcc_set and v in lcc_set:
                            core_lines.append(coords)
                        else:
                            iso_lines.append(coords)
                            
            # Optimization: Skip nodes if too many (>5k) to keep slider smooth?
            # User wants visual, so let's try to keep them.
            # if len(G_temp) < 10000: # Removed limit per user request
            
            # Add Active Nodes
            for n in G_temp.nodes():
                if n in pos:
                    pt = pos[n]
                    if n in lcc_set:
                        core_pts.append(pt)
                    else:
                        iso_pts.append(pt)
            
            # Add Removed Nodes (Ghosts)
            for n in remove_set:
                if n in pos:
                    removed_pts.append(pos[n])
                            
            return core_lines, iso_lines, core_pts, iso_pts, removed_pts

        def update_both(change=None):
            strat = strat_dd.value
            frac = frac_sl.value
            show_removed = show_removed_chk.value
            show_nodes = show_nodes_chk.value
            
            # Map 1 Update
            c1, i1, cp1, ip1, rem1 = get_geo_updates(G1, pos1, strat, frac, deg1, bet1, art1, nodes1)
            
            # Critical: Update layers in Z-order (Bottom -> Top). Last updated = Top.
            # 1. Removed (Gray) - Bottom
            # User Request: If "Show Nodes" is unchecked, hide ALL nodes (including gray ones).
            rem1_data = rem1 if (show_removed and show_nodes) else []
            layers1[4].data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiPoint', 'coordinates': rem1_data}, 'properties': {}}]} if rem1_data else {'type': 'FeatureCollection', 'features': []}
            
            # 2. Edges
            layers1[0].data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiLineString', 'coordinates': c1}, 'properties': {}}]} if c1 else {'type': 'FeatureCollection', 'features': []}
            layers1[1].data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiLineString', 'coordinates': i1}, 'properties': {}}]} if i1 else {'type': 'FeatureCollection', 'features': []}
            
            # 3. Iso (Red) - Middle
            ip1_data = ip1 if show_nodes else []
            layers1[3].data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiPoint', 'coordinates': ip1_data}, 'properties': {}}]} if ip1_data else {'type': 'FeatureCollection', 'features': []}
            
            # 4. Core (Blue) - Top (Last Updated)
            cp1_data = cp1 if show_nodes else []
            layers1[2].data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiPoint', 'coordinates': cp1_data}, 'properties': {}}]} if cp1_data else {'type': 'FeatureCollection', 'features': []}
            
            # Map 2 Update
            c2, i2, cp2, ip2, rem2 = get_geo_updates(G2, pos2, strat, frac, deg2, bet2, art2, nodes2)
            
            # 1. Removed (Gray)
            rem2_data = rem2 if (show_removed and show_nodes) else []
            layers2[4].data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiPoint', 'coordinates': rem2_data}, 'properties': {}}]} if rem2_data else {'type': 'FeatureCollection', 'features': []}

            # 2. Edges
            layers2[0].data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiLineString', 'coordinates': c2}, 'properties': {}}]} if c2 else {'type': 'FeatureCollection', 'features': []}
            layers2[1].data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiLineString', 'coordinates': i2}, 'properties': {}}]} if i2 else {'type': 'FeatureCollection', 'features': []}
            
            # 3. Iso (Red)
            ip2_data = ip2 if show_nodes else []
            layers2[3].data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiPoint', 'coordinates': ip2_data}, 'properties': {}}]} if ip2_data else {'type': 'FeatureCollection', 'features': []}
            
            # 4. Core (Blue)
            cp2_data = cp2 if show_nodes else []
            layers2[2].data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiPoint', 'coordinates': cp2_data}, 'properties': {}}]} if cp2_data else {'type': 'FeatureCollection', 'features': []}

        # Controls
        # Full list of strategies
        strategies = [
            'Random', 
            'Targeted (Degree)', 
            'Targeted (Betweenness)', 
            'Inverse Targeted (Degree)', 
            'Inverse Targeted (Betweenness)', 
            'Targeted (Articulation)'
        ]
        
        strat_dd = Dropdown(
            options=strategies, 
            value='Random', 
            description='Attack Strategy:', 
            style={'description_width': 'initial'},
            layout=Layout(width='auto')
        )
        
        # Slider with 0.01 steps and full width (relative to container, we use 90% or flex)
        frac_sl = FloatSlider(
            min=0.0, max=0.9, step=0.01, value=0.0, 
            description='Fraction Removed:', 
            layout=Layout(width='85%'), # Wider for 2nd row
            style={'description_width': 'initial'},
            readout_format='.2f'
        )
        
        # Buttons
        btn_minus = Button(description='-', layout=Layout(width='40px'))
        btn_plus = Button(description='+', layout=Layout(width='40px'))
        
        # Checkboxes
        show_nodes_chk = Checkbox(
            value=True,
            description='Show Nodes',
            indent=False,
            layout=Layout(width='auto', margin='0px 10px 0px 0px')
        )
        
        show_removed_chk = Checkbox(
            value=True,
            description='Show Removed Nodes',
            indent=False,
            layout=Layout(width='auto')
        )
        
        def on_minus(b):
            # step=0.01 logic
            new_val = round(max(frac_sl.min, frac_sl.value - 0.01), 2)
            frac_sl.value = new_val
            
        def on_plus(b):
            new_val = round(min(frac_sl.max, frac_sl.value + 0.01), 2)
            frac_sl.value = new_val
            
        btn_minus.on_click(on_minus)
        btn_plus.on_click(on_plus)
        
        strat_dd.observe(update_both, names='value')
        frac_sl.observe(update_both, names='value')
        show_removed_chk.observe(update_both, names='value')
        show_nodes_chk.observe(update_both, names='value')
        
        # Initial call
        update_both()
        
        # Layout
        # Row 1: Strategy + Checkboxes
        # Group checkboxes
        chk_box = HBox([show_nodes_chk, show_removed_chk], layout=Layout(align_items='center'))
        
        row1 = HBox([strat_dd, chk_box], 
                   layout=Layout(justify_content='space-between', width='100%', padding='5px'))
        
        # Row 2: Slider + Buttons (Full width)
        row2 = HBox([frac_sl, btn_minus, btn_plus], 
                   layout=Layout(width='100%', padding='5px', align_items='center'))
        
        controls = VBox([row1, row2], layout=Layout(width='100%', padding='10px'))
        
        label1 = HTML(f"<div style='text-align:center; font-weight:bold; font-size:16px;'>{name1}</div>")
        label2 = HTML(f"<div style='text-align:center; font-weight:bold; font-size:16px;'>{name2}</div>")
        
        map_box = HBox([
            VBox([label1, m1], layout=Layout(width='50%', padding='5px')),
            VBox([label2, m2], layout=Layout(width='50%', padding='5px'))
        ])
        
        return VBox([controls, map_box])
