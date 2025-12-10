
import argparse
from src.processing.switzerland import process_switzerland
from src.processing.japan import process_japan

def main():
    parser = argparse.ArgumentParser(description="Run data processing pipelines.")
    parser.add_argument('targets', nargs='*', default=['all'], help="Pipelines to run: 'switzerland', 'japan', or 'all' (default)")
    
    args = parser.parse_args()
    targets = [t.lower() for t in args.targets]
    
    run_all = 'all' in targets
    
    if run_all or 'switzerland' in targets:
        process_switzerland()
        
    if run_all or 'japan' in targets:
        process_japan()

if __name__ == "__main__":
    main()
