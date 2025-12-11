import sys
import os
import sysconfig

def patch_networkx():
    """
    Patches networkx 3.x to work with Python 3.14 (preview).
    Issue: dataclasses.dataclass(slots=True) causes failure in Python 3.14 dev builds.
    Fix: Change slots=True to slots=False in networkx/utils/configs.py.
    """
    # Only run on Python 3.14+
    if sys.version_info < (3, 14):
        print(f"Python {sys.version_info.major}.{sys.version_info.minor}: No patching needed.")
        return

    # Find site-packages
    paths = sysconfig.get_paths()
    site_packages = paths.get('purelib')
    
    if not site_packages:
        print("Error: Could not determine site-packages location.")
        return

    config_file = os.path.join(site_packages, 'networkx', 'utils', 'configs.py')

    if not os.path.exists(config_file):
        print(f"Warning: networkx config file not found at {config_file}")
        return

    # Read and patch
    try:
        with open(config_file, 'r') as f:
            content = f.read()
        
        target_str = "slots=True"
        replacement_str = "slots=False"

        if target_str in content:
            print(f"Applying patch to {config_file}...")
            new_content = content.replace(target_str, replacement_str)
            with open(config_file, 'w') as f:
                f.write(new_content)
            print("Successfully patched networkx for Python 3.14 compatibility.")
        elif replacement_str in content:
            print("networkx is already patched.")
        else:
            print("Warning: Could not find target string to patch in networkx.")
            
    except Exception as e:
        print(f"Error patching networkx: {e}")

if __name__ == "__main__":
    patch_networkx()
