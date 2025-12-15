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
        
        if len(G) > 5000:
            print("Graph is large (>5k nodes). Skipping calculate-on-the-fly Betweenness for interactivity speed.")
            betweenness_cent = degree_cent 
            # Performance Guard:
            skip_nodes = True
        else:
            betweenness_cent = nx.betweenness_centrality(G)
            skip_nodes = False

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

        layer_edges_blue = GeoJSON(data={'type': 'FeatureCollection', 'features': []}, style=style_blue_edge, name='Edges (Core)')
        layer_edges_red = GeoJSON(data={'type': 'FeatureCollection', 'features': []}, style=style_red_edge, name='Edges (Isolated)')
        
        layer_nodes_blue = GeoJSON(data={'type': 'FeatureCollection', 'features': []}, point_style=style_blue_node, name='Nodes (Core)')
        layer_nodes_red = GeoJSON(data={'type': 'FeatureCollection', 'features': []}, point_style=style_red_node, name='Nodes (Isolated)')

        m.add_layer(layer_edges_blue)
        m.add_layer(layer_edges_red)
        m.add_layer(layer_nodes_blue)
        m.add_layer(layer_nodes_red)

        # 3. Consolidated Legend & Layer Control
        def legend_icon(color, shape='line'):
            if shape == 'line':
                return f'<i style="background: {color}; width: 25px; height: 3px; display: inline-block; vertical-align: middle; margin-right: 5px;"></i>'
            else:
                return f'<i style="background: {color}; width: 10px; height: 10px; display: inline-block; border-radius: 50%; vertical-align: middle; margin-right: 5px;"></i>'

        label_edges_blue = HTML(f"{legend_icon('blue', 'line')} <b>Core Edges (Connected)</b>")
        label_edges_red = HTML(f"{legend_icon('red', 'line')} <b>Isolated Edges</b>")
        label_nodes_blue = HTML(f"{legend_icon('blue', 'circle')} <b>Core Nodes (Connected)</b>")
        label_nodes_red = HTML(f"{legend_icon('red', 'circle')} <b>Isolated Nodes</b>")
        
        check_edges_blue = Checkbox(value=True, indent=False, layout=Layout(width='30px'))
        check_edges_red = Checkbox(value=True, indent=False, layout=Layout(width='30px'))
        check_nodes_blue = Checkbox(value=True, indent=False, layout=Layout(width='30px'))
        check_nodes_red = Checkbox(value=True, indent=False, layout=Layout(width='30px'))
        
        jslink((check_edges_blue, 'value'), (layer_edges_blue, 'visible'))
        jslink((check_edges_red, 'value'), (layer_edges_red, 'visible'))
        jslink((check_nodes_blue, 'value'), (layer_nodes_blue, 'visible'))
        jslink((check_nodes_red, 'value'), (layer_nodes_red, 'visible'))
        
        row_1 = HBox([check_edges_blue, label_edges_blue], layout=Layout(align_items='center'))
        row_2 = HBox([check_edges_red, label_edges_red], layout=Layout(align_items='center'))
        row_3 = HBox([check_nodes_blue, label_nodes_blue], layout=Layout(align_items='center'))
        row_4 = HBox([check_nodes_red, label_nodes_red], layout=Layout(align_items='center'))
        
        layer_control_box = VBox([
            HTML(value="<b>Network Layers & Legend</b>"),
            row_1, row_2, row_3, row_4
        ])
        
        if len(G) > 5000:
            layer_control_box.children += (HTML(value="<br><i><small>Performance Guard: Node layers disabled (>5k nodes)</small></i>"),)

        layer_control_box.layout.padding = '5px'
        layer_control_box.layout.background_color = 'white'
        layer_control_box.layout.border = '2px solid #ccc'
        layer_control_box.layout.border_radius = '5px'

        m.add_control(WidgetControl(widget=layer_control_box, position='topright'))

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
            elif strategy == "Targeted (Inverse Degree)":
                remove_nodes = sorted_degree[-num_remove:] if num_remove > 0 else []
            elif strategy == "Targeted (Inverse Betweenness)":
                remove_nodes = sorted_betweenness[-num_remove:] if num_remove > 0 else []
            elif strategy == "Targeted (Articulation)":
                remove_nodes = sorted_articulation[:num_remove]
            
            G_temp.remove_nodes_from(remove_nodes)
            
            if len(G_temp) > 0:
                largest_cc = max(nx.connected_components(G_temp), key=len)
                lcc_set = set(largest_cc)
            else:
                lcc_set = set()

            # GeoJSON construction
            blue_lines = []
            red_lines = []
            
            # Edges
            for u, v in G.edges(): 
                if u in G_temp and v in G_temp: 
                    if u in geojson_pos and v in geojson_pos:
                        coords = [geojson_pos[u], geojson_pos[v]]
                        if u in lcc_set and v in lcc_set: # Strict definition: Edge is core if BOTH nodes are in LCC? Or if u in lcc (since comp connect)
                             # If edge exists in G_temp, u and v are connected. If u is in lcc, v must be in lcc.
                             # So check u in lcc_set is enough
                            blue_lines.append(coords)
                        else:
                            red_lines.append(coords)
            
            layer_edges_blue.data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiLineString', 'coordinates': blue_lines}, 'properties': {}}]} if blue_lines else {'type': 'FeatureCollection', 'features': []}
            layer_edges_red.data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiLineString', 'coordinates': red_lines}, 'properties': {}}]} if red_lines else {'type': 'FeatureCollection', 'features': []}
            
            # Nodes
            blue_pts = []
            red_pts = []
            
            if not skip_nodes:
                for n in G_temp.nodes():
                    if n in geojson_pos:
                        pt = geojson_pos[n]
                        if n in lcc_set:
                            blue_pts.append(pt)
                        else:
                            red_pts.append(pt)
                        
            layer_nodes_blue.data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiPoint', 'coordinates': blue_pts}, 'properties': {}}]} if blue_pts else {'type': 'FeatureCollection', 'features': []}
            layer_nodes_red.data = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'MultiPoint', 'coordinates': red_pts}, 'properties': {}}]} if red_pts else {'type': 'FeatureCollection', 'features': []}

        # 5. Controls
        strat_dd = Dropdown(options=['Random', 'Targeted (Degree)', 'Targeted (Betweenness)', 'Targeted (Articulation)', 'Targeted (Inverse Degree)', 'Targeted (Inverse Betweenness)'], value='Random', description='Strategy:')
        frac_sl = FloatSlider(min=0.0, max=0.5, step=0.01, value=0.0, description='Fraction:', layout=Layout(flex='3'))
        
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

        def on_change(change):
            update_layers(strat_dd.value, frac_sl.value)
            
        strat_dd.observe(on_change, names='value')
        frac_sl.observe(on_change, names='value')
        
        # Initial draw
        update_layers('Random', 0.0)
        
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
        markers = ['o', 's', '^', 'D', 'x', 'v', '<', '>']
        colors = ['green', 'red', 'orange', 'purple', 'blue', 'brown', 'cyan', 'magenta']
        
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
                'color': colors[i % len(colors)]
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
                                    linestyle='-', 
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
                                    linestyle='-', 
                                    label=item['label'], 
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

