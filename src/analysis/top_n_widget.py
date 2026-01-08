"""
TopNDisplayController - Centralized widget for displaying top-N centrality rankings.

Provides both interactive (Jupyter/Voila) and static (CI) rendering modes with:
- Offset-aware display (respects current node removal count)
- Scrollable container for fixed height display
- "Load More" button to expand the displayed list
"""

from ipywidgets import VBox, HBox, Button, Layout
from ipywidgets import HTML as WidgetHTML
from IPython.display import display, HTML


class TopNDisplayController:
    """
    Controller for displaying top-N nodes by various centrality measures.
    
    Supports both single-network and comparison modes with offset tracking
    based on the current attack simulation state.
    """
    
    def __init__(self, G, name, sorted_degree, sorted_betweenness, sorted_articulation, page_size=10):
        """
        Initialize the controller.
        
        Args:
            G: NetworkX graph with node attributes (supports 'name', 'station_name', 'label')
            name: Display name for this network (e.g., "Switzerland", "Japan")
            sorted_degree: List of node IDs sorted by degree centrality (descending)
            sorted_betweenness: List of node IDs sorted by betweenness centrality (descending)
            sorted_articulation: List of node IDs sorted by articulation priority (descending)
            page_size: Number of items to show per page (default: 10)
        """
        self.G = G
        self.name = name
        self.sorted_lists = {
            'Degree Centrality': sorted_degree,
            'Betweenness Centrality': sorted_betweenness,
            'Articulation Priority': sorted_articulation
        }
        self.page_size = page_size
        self.displayed_count = page_size
        self.current_offset = 0
        self.current_strategy = 'Targeted (Degree)'
        
        # Widget references (initialized in build_interactive_widget)
        self._html_widget = None
        self._load_more_btn = None
    
    def get_node_name(self, node_id):
        """Get human-readable name for a node, falling back to node_id."""
        data = self.G.nodes.get(node_id, {})
        for attr in ['name', 'station_name', 'label', 'title']:
            if attr in data:
                return str(data[attr])
        return str(node_id)
    
    def _get_sorted_list_for_strategy(self, strategy):
        """Map strategy name to the appropriate sorted list."""
        strategy_map = {
            'Targeted (Degree)': 'Degree Centrality',
            'Targeted (Betweenness)': 'Betweenness Centrality',
            'Targeted (Articulation)': 'Articulation Priority',
            'Inverse Targeted (Degree)': 'Degree Centrality',
            'Inverse Targeted (Betweenness)': 'Betweenness Centrality',
        }
        
        key = strategy_map.get(strategy, 'Degree Centrality')
        sorted_list = self.sorted_lists.get(key, [])
        
        # Reverse for inverse strategies
        if 'Inverse' in strategy:
            return list(reversed(sorted_list))
        return sorted_list
    
    def _get_metric_name_for_strategy(self, strategy):
        """Get display name for the metric based on strategy."""
        if 'Degree' in strategy:
            return 'Degree Centrality'
        elif 'Betweenness' in strategy:
            return 'Betweenness Centrality'
        elif 'Articulation' in strategy:
            return 'Articulation Priority'
        return 'Centrality'
    
    def build_static_matrix_html(self):
        """
        Build a static HTML matrix showing top-N nodes across all centrality measures.
        Used for CI/static rendering where interactive widgets are not available.
        
        Returns:
            str: HTML table with Rank | Degree | Betweenness | Articulation columns
        """
        n = self.page_size
        
        rows = []
        for i in range(n):
            row_cells = [f"<td style='padding: 6px; border-bottom: 1px solid #ddd;'>{i+1}</td>"]
            
            for metric_name in ['Degree Centrality', 'Betweenness Centrality', 'Articulation Priority']:
                sorted_list = self.sorted_lists.get(metric_name, [])
                if i < len(sorted_list):
                    node_name = self.get_node_name(sorted_list[i])
                else:
                    node_name = '-'
                row_cells.append(
                    f"<td style='padding: 6px; border-bottom: 1px solid #ddd;'>{node_name}</td>"
                )
            
            rows.append(f"<tr>{''.join(row_cells)}</tr>")
        
        return f"""
        <div style='margin: 10px 0;'>
            <h4 style='margin-bottom: 8px;'>{self.name} - Top {n} Stations by Centrality</h4>
            <table style='width: 100%; border-collapse: collapse; font-size: 12px;'>
                <thead>
                    <tr style='background: #f5f5f5;'>
                        <th style='padding: 8px; text-align: left; width: 50px;'>Rank</th>
                        <th style='padding: 8px; text-align: left;'>Degree</th>
                        <th style='padding: 8px; text-align: left;'>Betweenness</th>
                        <th style='padding: 8px; text-align: left;'>Articulation</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        """
    
    def _render_table_html(self):
        """
        Render the current state as an HTML table.
        Respects current_offset and displayed_count.
        """
        if self.current_strategy == 'Random':
            return f"""
            <div style='margin: 5px; color: #666; font-style: italic;'>
                Random strategy - no centrality ranking applicable
            </div>
            """
        
        sorted_list = self._get_sorted_list_for_strategy(self.current_strategy)
        metric_name = self._get_metric_name_for_strategy(self.current_strategy)
        
        start_idx = self.current_offset
        end_idx = start_idx + self.displayed_count
        visible_nodes = sorted_list[start_idx:end_idx]
        
        if not visible_nodes:
            return f"""
            <div style='margin: 5px; color: #666;'>
                No more nodes to display.
            </div>
            """
        
        rows = []
        for i, node in enumerate(visible_nodes):
            rank = start_idx + i + 1
            name = self.get_node_name(node)
            rows.append(f"<tr><td style='padding: 4px; width: 40px;'>{rank}</td><td style='padding: 4px;'>{name}</td></tr>")
        
        # Conditional subheader for offset
        offset_indicator = ""
        if self.current_offset > 0:
            offset_indicator = f"<span style='color: #888; font-size: 11px;'>(top {self.current_offset} stations removed)</span>"
        
        return f"""
        <div>
            <div style='display: flex; align-items: center; gap: 8px;'><h4 style='margin: 8px 0'>{self.name} - Top by {metric_name}</h4> {offset_indicator}</div>
            <div style='max-height: 400px; overflow-y: auto; border: 1px solid #eee; border-radius: 4px;'>
                <table style='width: 100%; border-collapse: collapse; font-size: 12px;'>
                    <thead style='position: sticky; top: 0; background: #f5f5f5;'>
                        <tr>
                            <th style='padding: 6px; text-align: left; width: 40px;'>#</th>
                            <th style='padding: 6px; text-align: left;'>Station</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows)}
                    </tbody>
                </table>
            </div>
        </div>
        """
    
    def _on_load_more(self, btn):
        """Handle Load More button click."""
        sorted_list = self._get_sorted_list_for_strategy(self.current_strategy)
        max_count = len(sorted_list) - self.current_offset
        
        self.displayed_count = min(self.displayed_count + self.page_size, max_count)
        self._refresh_display()
    
    def _refresh_display(self):
        """Refresh the HTML widget with current state."""
        if self._html_widget:
            self._html_widget.value = self._render_table_html()
        
        # Update Load More button visibility
        if self._load_more_btn:
            sorted_list = self._get_sorted_list_for_strategy(self.current_strategy)
            has_more = (self.current_offset + self.displayed_count) < len(sorted_list)
            self._load_more_btn.layout.display = 'block' if has_more else 'none'
    
    def build_interactive_widget(self):
        """
        Build the interactive widget with scrollable table and Load More button.
        
        Returns:
            VBox: Widget containing HTML table and Load More button
        """
        self._html_widget = WidgetHTML(value=self._render_table_html())
        
        self._load_more_btn = Button(
            description='Load More',
            button_style='info',
            layout=Layout(width='auto', margin='5px')
        )
        self._load_more_btn.on_click(self._on_load_more)
        
        # Initial visibility check
        sorted_list = self._get_sorted_list_for_strategy(self.current_strategy)
        has_more = (self.current_offset + self.displayed_count) < len(sorted_list)
        self._load_more_btn.layout.display = 'block' if has_more else 'none'
        
        return VBox([
            self._html_widget,
            self._load_more_btn
        ], layout=Layout(
            padding='5px',
            border='1px solid #ddd',
            border_radius='5px',
            width='100%'
        ))
    
    def update(self, strategy, num_remove):
        """
        Update the display based on current attack state.
        
        Args:
            strategy: Current attack strategy name
            num_remove: Number of nodes removed (used as offset)
        """
        self.current_strategy = strategy
        self.current_offset = num_remove
        self.displayed_count = self.page_size  # Reset on state change
        self._refresh_display()


def build_comparison_static_matrix(controllers, page_size=10):
    """
    Build a static comparison matrix for CI rendering.
    Shows centrality rankings side-by-side for multiple networks.
    
    Args:
        controllers: List of TopNDisplayController instances
        page_size: Number of ranks to display
    
    Returns:
        str: HTML table with comparison matrix
    """
    if not controllers:
        return ""
    
    metrics = ['Degree Centrality', 'Betweenness Centrality', 'Articulation Priority']
    metric_short = {'Degree Centrality': 'Degree', 'Betweenness Centrality': 'Betweenness', 'Articulation Priority': 'Articulation'}
    
    # Build header
    header_cells = ["<th style='padding: 8px; text-align: left; width: 50px;'>Rank</th>"]
    for metric in metrics:
        for ctrl in controllers:
            header_cells.append(
                f"<th style='padding: 8px; text-align: left;'>{ctrl.name}<br><small>{metric_short[metric]}</small></th>"
            )
    
    # Build rows
    rows = []
    for i in range(page_size):
        row_cells = [f"<td style='padding: 6px; border-bottom: 1px solid #ddd;'>{i+1}</td>"]
        
        for metric in metrics:
            for ctrl in controllers:
                sorted_list = ctrl.sorted_lists.get(metric, [])
                if i < len(sorted_list):
                    node_name = ctrl.get_node_name(sorted_list[i])
                else:
                    node_name = '-'
                row_cells.append(
                    f"<td style='padding: 6px; border-bottom: 1px solid #ddd; font-size: 11px;'>{node_name}</td>"
                )
        
        rows.append(f"<tr>{''.join(row_cells)}</tr>")
    
    return f"""
    <div style='margin: 10px 0; overflow-x: auto;'>
        <h4 style='margin-bottom: 8px;'>Top {page_size} Stations by Centrality - Comparison</h4>
        <table style='width: 100%; border-collapse: collapse; font-size: 12px;'>
            <thead>
                <tr style='background: #f5f5f5;'>
                    {''.join(header_cells)}
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </div>
    """
