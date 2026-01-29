import os
import sys
import shutil
from win32com.client import Dispatch


def deploy():
    # Paths
    project_dir = os.getcwd()
    dist_dir = os.path.join(project_dir, "dist", "ssmaker")

    # Get Desktop path properly
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")

    dest_dir = os.path.join(desktop, "ShoppingShortsMaker")
    # Use English name to avoid COM encoding issues
    shortcut_path = os.path.join(desktop, "ShoppingShortsMaker.lnk")

    print(f"Deploying to Desktop: {dest_dir}")

    # 1. Clean destination
    if os.path.exists(dest_dir):
        try:
            shutil.rmtree(dest_dir)
            print("Cleaned existing directory")
        except Exception as e:
            print(
                f"Error cleaning directory: {str(e).encode('utf-8', 'ignore').decode('utf-8')}"
            )
            # Try to continue? If cleaning failed, copytree will fail.
            # But maybe the user deleted it manually.

    # 2. Copy build
    if not os.path.exists(dist_dir):
        print(f"Build directory not found: {dist_dir}")
        print("Please run build.py first!")
        return

    try:
        if not os.path.exists(dest_dir):
            shutil.copytree(dist_dir, dest_dir)
            print("Copied build files")
        else:
            print("Destination exists (cleanup failed?), skipping copy")
    except Exception as e:
        print(
            f"Error copying files: {str(e).encode('utf-8', 'ignore').decode('utf-8')}"
        )
        return

    # 3. Create Shortcut
    try:
        target_exe = os.path.join(dest_dir, "ssmaker.exe")
        icon_path = os.path.join(dest_dir, "resource", "app_icon.ico")

        shell = Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = target_exe
        shortcut.WorkingDirectory = dest_dir
        if os.path.exists(icon_path):
            shortcut.IconLocation = icon_path
        shortcut.save()
        print(f"Created shortcut: {shortcut_path}")
        print("Deployment successful!")

    except Exception as e:
        # Safe printing of error
        print(f"Error creating shortcut")


if __name__ == "__main__":
    deploy()
