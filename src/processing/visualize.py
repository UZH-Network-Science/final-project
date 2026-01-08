import folium
import networkx as nx
import math
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np

def create_folium_map(G, title="Rail Network", color_by_component=False):
    """
    Creates an interactive Folium map for a NetworkX graph.
    Nodes are colored by type (Station=Blue, Infra=Orange, Isolated=Red).
    If color_by_component is True, nodes and edges are colored by their connected component.
    """
    if not color_by_component:
        return create_robustness_style_map(G, title)

    # Calculate center
    lats = [d['lat'] for _, d in G.nodes(data=True) if d.get('lat')]
    lons = [d['lon'] for _, d in G.nodes(data=True) if d.get('lon')]
    if not lats:
        return folium.Map()
        
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=9, tiles='CartoDB Positron')
    
    # Feature Groups
    edges_fg = folium.FeatureGroup(name='Edges', show=True)
    stations_fg = folium.FeatureGroup(name='Stations', show=True)
    infra_fg = folium.FeatureGroup(name='Infrastructure', show=False)
    
    # Component Analysis
    components = sorted(nx.connected_components(G), key=len, reverse=True)
    largest_cc = components[0] if components else set()
    node_to_comp_idx = {}
    for idx, comp in enumerate(components):
        for node in comp:
            node_to_comp_idx[node] = idx
            
    colors = ['#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4', '#46f0f0', '#f032e6', '#bcf60c', '#fabebe']
    
    # 1. Edges
    for u, v, data in G.edges(data=True):
        u_data = G.nodes[u]
        v_data = G.nodes[v]
        
        if 'lat' in u_data and 'lat' in v_data:
            
            if color_by_component:
                comp_idx = node_to_comp_idx.get(u, 0) # Assuming edges connect same component
                color = colors[comp_idx % len(colors)]
                opacity = 0.8
                weight = 2
            else:
                is_in_main_cc = u in largest_cc
                color = '#1f77b4' if is_in_main_cc else '#ff0000' # Blue vs Red
                opacity = 0.5 if is_in_main_cc else 0.8
                weight = 1.5 if is_in_main_cc else 2.5
                
            folium.PolyLine(
                [[u_data['lat'], u_data['lon']], [v_data['lat'], v_data['lon']]],
                color=color, weight=weight, opacity=opacity,
                tooltip=f"Line: {', '.join(data.get('lines', []))}"
            ).add_to(edges_fg)
            
    # 2. Nodes
    largest_cc = components[0] if components else set()

    for node, data in G.nodes(data=True):
        if 'lat' not in data: continue
        
        node_type = data.get('node_type', 'station' if data.get('is_station', False) else 'infrastructure')
        is_in_main_cc = node in largest_cc
        comp_idx = node_to_comp_idx.get(node, 0)
        
        if color_by_component:
            color = colors[comp_idx % len(colors)]
            radius = 4
            fill_opacity = 0.8
            layer = stations_fg
            tooltip_txt = f"{data.get('label', data.get('name', node))} (Comp {comp_idx+1})"
        else:
            if not is_in_main_cc:
                # Disconnected components -> RED
                color = '#ff0000' # Red
                radius = 5
                fill_opacity = 0.9
                layer = stations_fg 
                tooltip_txt = f"{data.get('label', data.get('name', node))} (Disconnected)"
            elif node_type == 'station' or data.get('is_station'):
                color = '#1f77b4' # Blue
                radius = 4
                fill_opacity = 0.7
                layer = stations_fg
                tooltip_txt = data.get('label', data.get('name', node))
            else:
                color = '#ff7f0e' # Orange
                radius = 3
                fill_opacity = 0.7
                layer = infra_fg
                tooltip_txt = f"{data.get('label', data.get('name', node))} (Infra)"
            
        popup_html = f"<b>{data.get('label', data.get('name', node))}</b><br>ID: {node}<br>Component: {comp_idx+1}"
        
        folium.CircleMarker(
            location=[data['lat'], data['lon']],
            radius=radius, color=color, fill=True, fill_color=color, fill_opacity=fill_opacity,
            popup=folium.Popup(popup_html, max_width=200),
            tooltip=tooltip_txt
        ).add_to(layer)

    edges_fg.add_to(m)
    stations_fg.add_to(m)
    infra_fg.add_to(m)
    folium.LayerControl().add_to(m)
    
    return m

def plot_connected_components(G, title="Connected Components"):
    """
    Plots the graph with nodes colored by their connected component.
    """
    components = sorted(nx.connected_components(G), key=len, reverse=True)
    
    # Valid nodes with coords
    valid_nodes = [n for n in G.nodes if 'lat' in G.nodes[n] and 'lon' in G.nodes[n]]
    if not valid_nodes:
        return
        
    # Map node -> component index
    node_color_map = {}
    for idx, comp in enumerate(components):
        for node in comp:
            node_color_map[node] = idx
            
    # Prepare coords and colors
    lons = [G.nodes[n]['lon'] for n in valid_nodes]
    lats = [G.nodes[n]['lat'] for n in valid_nodes]
    colors = [node_color_map[n] for n in valid_nodes]
    
    # Plot
    fig, ax = plt.subplots(figsize=(12, 10))
    cmap = cm.get_cmap('tab20')
    scatter = ax.scatter(lons, lats, c=colors, cmap=cmap, s=10, alpha=0.8)
    
    # Legend for top 5 components
    handles = []
    for i in range(min(5, len(components))):
        color = cmap(i / 20) if len(components) > 1 else cmap(0) # Logic simplification
        handles.append(plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=cmap(i%20), label=f"Comp {i+1}: {len(components[i])} nodes"))
    
    if len(components) > 5:
         handles.append(plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='gray', label=f"Other {len(components)-5} comps"))

    ax.legend(handles=handles)
    ax.set_title(f"{title}\n({len(components)} components, Largest: {len(components[0])/len(G)*100:.1f}%)")
    ax.axis('off')
    plt.show()
    plt.close()

def create_component_map(G):
    """
    Creates an interactive map where distinct connected components have different colors.
    Shows edges and nodes. Creates a separate layer for EVERY component.
    """
    # Calculate center
    lats = [d['lat'] for _, d in G.nodes(data=True) if d.get('lat')]
    lons = [d['lon'] for _, d in G.nodes(data=True) if d.get('lon')]
    if not lats: return folium.Map()
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=9, tiles='CartoDB Positron')
    
    components = sorted(nx.connected_components(G), key=len, reverse=True)
    colors = ['#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4', '#46f0f0', '#f032e6', '#bcf60c', '#fabebe'] # Distinct colors
    
    # Create layers
    # Strategy: Top 50 components get their own layer.
    # All others (potentially thousands) are grouped into one "Small Components" layer to prevent Folium/Browser crash.
    layers = {}
    limit_individual_layers = 50
    
    small_comps_layer = folium.FeatureGroup(name=f"Small Multitudes ({max(0, len(components)-limit_individual_layers)} comps)", show=True)
    
    for idx, comp in enumerate(components):
        if idx < limit_individual_layers:
            layer_name = f"Component {idx+1} ({len(comp)} nodes)"
            # Show ALL layers by default as requested
            show_layer = True 
            layers[idx] = folium.FeatureGroup(name=layer_name, show=show_layer)
        else:
            # Map index to the shared layer
            layers[idx] = small_comps_layer
            
    node_to_comp_idx = {}
    for idx, comp in enumerate(components):
        for node in comp:
            node_to_comp_idx[node] = idx
            
    # Draw Edges first
    for u, v, data in G.edges(data=True):
        u_data = G.nodes[u]
        v_data = G.nodes[v]
        if 'lat' in u_data and 'lat' in v_data:
            # Check for NaN
            if math.isnan(u_data['lat']) or math.isnan(u_data['lon']) or math.isnan(v_data['lat']) or math.isnan(v_data['lon']):
                continue
                
            comp_idx = node_to_comp_idx.get(u, 0)
            color = colors[comp_idx % len(colors)]
            target_layer = layers.get(comp_idx)
            
            if target_layer:
                folium.PolyLine(
                    [[u_data['lat'], u_data['lon']], [v_data['lat'], v_data['lon']]],
                    color=color, weight=2, opacity=0.7,
                    tooltip=f"Line: {', '.join(data.get('lines', []))}"
                ).add_to(target_layer)

    # Draw Nodes
    for idx, comp in enumerate(components):
        color = colors[idx % len(colors)]
        target_layer = layers.get(idx)
        
        if target_layer:
            for node in comp:
                data = G.nodes[node]
                if 'lat' not in data: continue
                # Check for NaN
                if math.isnan(data['lat']) or math.isnan(data['lon']):
                    continue
                
                folium.CircleMarker(
                    location=[data['lat'], data['lon']],
                    radius=4, color=color, fill=True, fill_color=color, fill_opacity=0.8,
                    popup=f"Comp {idx+1}: {node}",
                    tooltip=f"Comp {idx+1}"
                ).add_to(target_layer)
            
    # Add individual layers sorted
    for idx in sorted([k for k in layers.keys() if isinstance(k, int) and k < limit_individual_layers]):
        layers[idx].add_to(m)
    
    # Add the catch-all layer if used
    if len(components) > limit_individual_layers:
        small_comps_layer.add_to(m)
        
    folium.LayerControl().add_to(m)
    return m

def create_robustness_style_map(G, title="Rail Network (Core vs Isolated)"):
    """
    Creates a Folium map matching the 'Robustness' visualization style.
    - Main Connected Component (Core): BLUE
    - Isolated Components: RED
    Matches style parameters from src.analysis.visualizer.NetworkVisualizer.
    """
    # 1. Calculate Center
    lats = [d['lat'] for _, d in G.nodes(data=True) if d.get('lat')]
    lons = [d['lon'] for _, d in G.nodes(data=True) if d.get('lon')]
    if not lats: return folium.Map()
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=8, tiles='CartoDB Positron')
    
    # 2. Identify Core (Largest Connected Component)
    components = list(nx.connected_components(G))
    if not components:
        return m
        
    largest_cc = max(components, key=len)
    lcc_set = set(largest_cc)
    
    # 3. Create Feature Groups for Layer Control
    # Using FeatureGroups allows toggling 'Core' vs 'Isolated'
    fg_edges_core = folium.FeatureGroup(name='Edges (Core)', show=True)
    fg_edges_iso = folium.FeatureGroup(name='Edges (Isolated)', show=True)
    fg_nodes_core = folium.FeatureGroup(name='Nodes (Core)', show=True)
    fg_nodes_iso = folium.FeatureGroup(name='Nodes (Isolated)', show=True)

    # Styles from NetworkVisualizer (approximated for Folium)
    # style_core = {'color': 'blue', 'weight': 1, 'opacity': 0.6}
    # style_iso = {'color': 'red', 'weight': 1, 'opacity': 0.6}
    
    # 4. Plot Edges
    for u, v, data in G.edges(data=True):
        u_data = G.nodes[u]
        v_data = G.nodes[v]
        
        if 'lat' in u_data and 'lat' in v_data:
            # If BOTH nodes are in LCC, it's a Core edge
            is_core = (u in lcc_set) and (v in lcc_set)
            
            color = 'blue' if is_core else 'red'
            target_fg = fg_edges_core if is_core else fg_edges_iso
            
            # Note: robustness viz uses weight=1, opacity=0.6
            folium.PolyLine(
                [[u_data['lat'], u_data['lon']], [v_data['lat'], v_data['lon']]],
                color=color, weight=1.5, opacity=0.6,
                tooltip=f"Line: {', '.join(data.get('lines', []))}"
            ).add_to(target_fg)

    # 5. Plot Nodes
    # style_node_core = {'radius': 3, 'color': 'blue', 'fillColor': 'blue', 'fillOpacity': 0.8}
    for node, data in G.nodes(data=True):
        if 'lat' not in data: continue
        
        is_core = node in lcc_set
        color = 'blue' if is_core else 'red'
        target_fg = fg_nodes_core if is_core else fg_nodes_iso
        
        popup_html = f"<b>{data.get('label', data.get('name', node))}</b><br>ID: {node}<br>{'Core' if is_core else 'Isolated'}"
        
        folium.CircleMarker(
            location=[data['lat'], data['lon']],
            radius=6, # Larger size
            color=color, weight=1, # Match stroke to fill for 'chunkier' look
            fill=True, fill_color=color, fill_opacity=0.8,
            popup=folium.Popup(popup_html, max_width=200),
            tooltip=data.get('label', str(node))
        ).add_to(target_fg)

    # Add Layers
    fg_edges_core.add_to(m)
    fg_edges_iso.add_to(m)
    fg_nodes_core.add_to(m)
    fg_nodes_iso.add_to(m)
    
    folium.LayerControl().add_to(m)
    return m

def plot_static_map(G, title="Static Network Map", node_color='#1f77b4', edge_color='#6c757d'):
    """
    Creates a static Matplotlib map for CI/GitHub rendering.
    Uses 'lon'/'lat' node attributes for positioning.
    """
    plt.figure(figsize=(10, 10))
    
    # Extract positions
    pos = {n: (d['lon'], d['lat']) for n, d in G.nodes(data=True) if 'lon' in d and 'lat' in d}
    if not pos:
        print("No geographic data found for static map.")
        return

    # Draw Edges
    nx.draw_networkx_edges(G, pos, width=0.5, edge_color=edge_color, alpha=0.5)
    
    # Draw Nodes
    nx.draw_networkx_nodes(G, pos, node_size=10, node_color=node_color, alpha=0.8)
    
    plt.title(title)
    plt.axis('off')
    plt.gca().set_aspect('equal')
    plt.show()
    plt.close()
