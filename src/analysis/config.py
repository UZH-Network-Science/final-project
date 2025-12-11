import yaml
from pathlib import Path

# RE-WRITE to load at module level to keep API compatible with notebooks:
class AnalysisConfig:
    _config_path = Path(__file__).parent / "config.yaml"
    with open(_config_path, "r") as f:
        _data = yaml.safe_load(f)

    # Simulations
    NUM_RANDOM_SIMULATIONS = _data['simulations']['num_random_simulations']
    FRACTIONS = _data['simulations']['fractions']
    
    # Colors
    COLORS = _data['colors']

    @staticmethod
    def get_graph_path(country):
        paths = AnalysisConfig._data['paths']
        if country.lower() == 'switzerland':
            p = Path(paths['switzerland']['unified'])
            if not p.exists() and Path(paths['switzerland']['raw']).exists():
                 return str(paths['switzerland']['raw'])
            return str(p)
        elif country.lower() == 'japan':
            return paths['japan']['unified']
        return None
