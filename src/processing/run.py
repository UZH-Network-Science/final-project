import argparse
import multiprocessing
from src.processing import process_switzerland, process_japan

def main():
    parser = argparse.ArgumentParser(description="Run data processing pipelines.")
    parser.add_argument('targets', nargs='*', default=['all'], help="Pipelines to run: 'switzerland', 'japan', or 'all' (default)")
    
    args = parser.parse_args()
    targets = [t.lower() for t in args.targets]
    
    run_all = 'all' in targets
    
    tasks = []
    if run_all or 'switzerland' in targets:
        tasks.append(process_switzerland)
        
    if run_all or 'japan' in targets:
        tasks.append(process_japan)

    if not tasks:
        print("No valid targets specified.")
        return

    # If running multiple tasks, use multiprocessing
    if len(tasks) > 1:
        print(f"Running {len(tasks)} pipelines in parallel...")
        processes = []
        for task in tasks:
            p = multiprocessing.Process(target=task)
            p.start()
            processes.append(p)
        
        for p in processes:
            p.join()
    else:
        # Run single task directly
        tasks[0]()

if __name__ == "__main__":
    main()
