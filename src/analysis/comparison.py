
import matplotlib.pyplot as plt
import numpy as np
from IPython.display import display, clear_output
from ipywidgets import Output, Checkbox, VBox, HBox, HTML, Accordion, Layout

def get_metric_series(results_cache, country, key_suffix, sub_metric='efficiency'):
    """
    Extracts the specific metric series (e.g. Efficiency, LCC) from cached results.
    Handles legacy efficiency-only results dictionaries and new extended metrics.
    """
    if country not in results_cache:
        print(f"Warning: No data loaded for {country}")
        return {}
        
    full_data = results_cache[country]
    
    # Check if key exists directly
    if key_suffix not in full_data:
        # Fallback: if requesting LCC but passing old efficiency key, try swapping to extended
        # Or if passed a key like 'extended_metrics_random', it might just be there
        pass
    
    # Try to find the data
    data = full_data.get(key_suffix)
    if not data:
         print(f"Warning: {key_suffix} not found for {country}")
         return {}
    
    # Structure 1: Extended Results -> {'efficiency': {...}, 'lcc': {...}}
    if isinstance(data, dict) and sub_metric in data:
        return data[sub_metric]
        
    # Structure 2: Legacy Random -> {'efficiency': {...}} (and we asked for efficiency)
    if sub_metric == 'efficiency' and isinstance(data, dict) and 'efficiency' in data:
        return data['efficiency']

    # Structure 3: Legacy Targeted -> Directly the series {fraction: value}
    # Only assume this is efficiency if we asked for efficiency
    if sub_metric == 'efficiency' and isinstance(data, dict):
         # Verify it looks like a series (keys are numbers)
         if data:
             first_key = next(iter(data.keys()))
             # simple heuristic check if key is likely a float fraction
             try:
                 float(first_key)
                 return data
             except ValueError:
                 pass
             
    return {}

def plot_interactive_comparison(results_cache, viz, countries, metric_key, title, ylabel, sub_metric='efficiency'):
    """
    Plots a comparison of a specific metric across multiple countries.
    """
    # Construct data dict for visualizer: {'Switzerland': {0.1:0.9...}, 'Japan': ...}
    plot_data = {}
    for country in countries:
        series = get_metric_series(results_cache, country, metric_key, sub_metric=sub_metric)
        if series:
            plot_data[country.title()] = series
            
    if plot_data:
        viz.plot_metric_decay(plot_data, title=title, ylabel=ylabel, log_x=True)
    else:
        print(f"No data available for {title} (Metric: {sub_metric})")

def plot_metric_all_strategies(results_cache, viz, countries, metric_name, pretty_name):
    """
    Aggregates all strategies for all countries into a single plot for a given metric.
    """
    plot_data = {}
    
    # Strategies to look for
    strategies = {
        'Random': 'extended_metrics_random',
        'Targeted Degree': 'extended_metrics_degree',
        'Targeted Betweenness': 'extended_metrics_betweenness',
        'Inv. Degree': 'extended_metrics_inverse_degree',
        'Inv. Betweenness': 'extended_metrics_inverse_betweenness',
        'Articulation': 'extended_metrics_articulation'
    }
    
    for country in countries:
        for strat_label, strat_key in strategies.items():
            series = get_metric_series(results_cache, country, strat_key, sub_metric=metric_name)
            if series:
                # Combined label: "Switzerland - Random"
                label = f"{country.title()} - {strat_label}"
                plot_data[label] = series
            else:
                 # Try old keys if extended ones fail (backwards compatibility for Efficiency)
                 if metric_name == 'efficiency':
                     legacy_map = {
                         'Random': 'efficiency_decay_random',
                         'Targeted Degree': 'efficiency_decay_degree',
                         'Targeted Betweenness': 'efficiency_decay_betweenness'
                     }
                     if strat_label in legacy_map:
                         series = get_metric_series(results_cache, country, legacy_map[strat_label], sub_metric='efficiency')
                         if series:
                             label = f"{country.title()} - {strat_label}"
                             plot_data[label] = series

    if plot_data:
        return viz.plot_metric_decay(plot_data, title=f"Robustness: {pretty_name} Degradation", ylabel=pretty_name, log_x=True)
    else:
        print(f"No data available for {pretty_name}")
        return None

def plot_all_metrics_consolidated(results_cache, viz, countries):
    """
    Plots simplified consolidated plots for all available metrics.
    Returns a VBox containing all metric widgets.
    """
    metrics = [
        ('efficiency', 'Global Efficiency'),
        ('lcc', 'LCC Size'),
        ('average_degree', 'Average Degree'),
        ('clustering', 'Avg Clustering Coeff.'),
        ('diameter', 'Diameter'),
        ('avg_path_length', 'Avg Path Length')
    ]
    
    widgets = []
    for metric_id, metric_pretty in metrics:
        widget = plot_metric_all_strategies(results_cache, viz, countries, metric_id, metric_pretty)
        if widget:
            widgets.append(widget)
    
    return VBox(widgets) if widgets else None

def plot_lcc_comparison(*args, **kwargs):
    """
    Deprecated alias for backward compatibility. 
    Redirects to plot_metric_all_strategies if arguments align, or warns user.
    """
    print("Warning: 'plot_lcc_comparison' is deprecated. Please use 'plot_all_metrics_consolidated'.")
    # Redirect to the consolidated view if possible, or just pass
    if len(args) >= 3:
        # args[0] = results_cache, args[1] = viz, args[2] = countries
        plot_metric_all_strategies(args[0], args[1], args[2], 'lcc', 'Leading Component (LCC)')
    else:
        print("Could not auto-redirect. Please update your notebook cell.")
