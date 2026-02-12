import os
import shutil
import sys
import subprocess
from pathlib import Path

def print_banner(text):
    print("\n" + "=" * 60)
    print(f" {text}")
    print("=" * 60)

def prepare_whisper_models():
    print_banner("1. Preparing Whisper Models")
    base_dir = Path("faster_whisper_models")
    
    for model_name in ["tiny", "base"]:
        model_path = base_dir / model_name
        if not model_path.exists():
            print(f"Skipping {model_name} - not found.")
            continue
            
        # Find the snapshot directory
        snapshot_dirs = list(model_path.glob("**/snapshots/*"))
        if not snapshot_dirs:
            print(f"No snapshots found for {model_name}")
            continue
            
        latest_snapshot = snapshot_dirs[0]
        print(f"Flattening {model_name} from {latest_snapshot}")
        
        # Temporary move files to top level of model_path
        for f in latest_snapshot.iterdir():
            dest = model_path / f.name
            if dest.exists():
                if dest.is_dir(): shutil.rmtree(dest)
                else: dest.unlink()
            shutil.copy2(f, dest)
            
        # Cleanup subfolders
        for item in model_path.iterdir():
            if item.is_dir() and item.name not in ["tiny", "base"]:
                try: shutil.rmtree(item)
                except: pass
        print(f"Successfully flattened {model_name}")

def build_apps():
    print_banner("2. Running PyInstaller Build")
    
    # 1. Shorts Maker
    print("\nBuilding ShortsMaker...")
    try:
        subprocess.run(["pyinstaller", "--noconfirm", "--clean", "ssmaker.spec"], check=True)
        print("ShortsMaker build finished successfully.")
    except subprocess.CalledProcessError as e:
        print(f"ShortsMaker build failed: {e}")
        return False

    return True

def package_results():
    print_banner("3. Packaging")
    dist_path = Path("dist")
    
    # Bundle components into one ready-to-use directory structure if needed,
    # but Specs already use COLLECT (onedir) which creates separate folders.
    
    print(f"Build artifacts are available in {dist_path.absolute()}")
    print("- ShortsMaker/")

if __name__ == "__main__":
    prepare_whisper_models()
    if build_apps():
        package_results()
    else:
        sys.exit(1)
