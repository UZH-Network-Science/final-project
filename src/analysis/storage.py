import json
import os
from pathlib import Path
import hashlib

class ResultsManager:
    def __init__(self, metrics_dir="metrics"):
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_path(self, country_name):
        return self.metrics_dir / country_name / f"{country_name}_metrics_unified.json"

    def load_results(self, country_name):
        path = self._get_path(country_name)
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)
        return {}

    def save_results(self, country_name, results):
        path = self._get_path(country_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(results, f, indent=4, sort_keys=True)
        print(f"Saved metrics to {path}")

    def get_cached_or_run(self, country_name, key, run_func, current_params=None, override=False):
        """
        Smart caching logic:
        - If key not in results -> Run
        - If 'num_simulations' in current_params and cached version has fewer runs -> Run (and overwrite)
        - If override is True -> Run (and overwrite)
        - Else -> Return cached
        """
        results = self.load_results(country_name)
        cached_data = results.get(key)

        should_run = False
        
        if override:
            should_run = True
            print(f"[{key}] Override enabled. Re-running...")
        elif cached_data is None:
            should_run = True
            print(f"[{key}] No cached data found. Running...")
        else:
            # Check for parameter upgrades (e.g. more simulations)
            if current_params and 'num_simulations' in current_params:
                cached_params = cached_data.get('params', {})
                cached_sims = cached_params.get('num_simulations', 0)
                requested_sims = current_params['num_simulations']
                
                if requested_sims > cached_sims:
                    print(f"[{key}] Requested more simulations ({requested_sims} > {cached_sims}). Re-running...")
                    should_run = True
                else:
                    print(f"[{key}] Cached data sufficient ({cached_sims} runs >= {requested_sims}). Using cache.")
            else:
                print(f"[{key}] Using cached results.")

        if should_run:
            data = run_func()
            # Attach params to the data for future checking
            if current_params:
                data['params'] = current_params
            
            results[key] = data
            self.save_results(country_name, results)
            return data
        
        return cached_data
