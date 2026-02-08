# -*- coding: utf-8 -*-
"""
SSMaker Auto-Updater
This standalone script is responsible for replacing the main application executable
with a newly downloaded version. It waits for the main application to terminate,
replaces the file, and then restarts the application.

Usage:
    updater.exe <source_path> <dest_path> <execute_after> <pid_to_wait>
"""
import sys
import os
import time
import shutil
import subprocess
import logging

# Setup basic logging to a file in the temp directory or same dir
log_file = os.path.join(os.getcwd(), 'updater.log')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    try:
        if len(sys.argv) < 5:
            logging.error(f"Insufficient arguments: {sys.argv}")
            print("Usage: updater.exe <source_path> <dest_path> <execute_after> <pid_to_wait>")
            sys.exit(1)

        source_path = sys.argv[1]
        dest_path = sys.argv[2]
        execute_after = sys.argv[3]
        pid_to_wait = int(sys.argv[4])

        logging.info(f"Updater started.")
        logging.info(f"Source: {source_path}")
        logging.info(f"Dest: {dest_path}")
        logging.info(f"Restart: {execute_after}")
        logging.info(f"Waiting for PID: {pid_to_wait}")

        # 1. Wait for the main application to close
        max_retries = 30  # Wait up to 30 seconds
        process_closed = False
        
        for i in range(max_retries):
            try:
                # Check if process exists
                os.kill(pid_to_wait, 0)
                logging.info(f"Process {pid_to_wait} still running... waiting ({i+1}/{max_retries})")
                time.sleep(1)
            except OSError:
                # Process is gone
                process_closed = True
                logging.info(f"Process {pid_to_wait} has terminated.")
                break
        
        if not process_closed:
            logging.error("Timeout waiting for application to close.")
            sys.exit(1)
            
        # Double check to ensure file handles are released
        time.sleep(1)

        # 2. Replace the file
        logging.info("Replacing application file...")
        try:
            if os.path.exists(dest_path):
                # Create a backup just in case
                backup_path = dest_path + ".bak"
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                os.rename(dest_path, backup_path)
            
            shutil.copy2(source_path, dest_path)
            logging.info("File replaced successfully.")
            
            # Clean up source file
            try:
                os.remove(source_path)
            except Exception as e:
                logging.warning(f"Failed to remove source file: {e}")

        except Exception as e:
            logging.error(f"Failed to replace file: {e}")
            # Try to restore backup
            if os.path.exists(dest_path + ".bak"):
                try:
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    os.rename(dest_path + ".bak", dest_path)
                    logging.info("Restored backup.")
                except:
                    pass
            sys.exit(1)

        # 3. Restart the application
        logging.info(f"Restarting application: {execute_after}")
        try:
            # Wait a bit to ensure all file handles are released
            time.sleep(2)

            if os.path.exists(execute_after):
                logging.info(f"Launching: {execute_after}")
                # Use shell=True and appropriate creation flags for Windows
                if sys.platform == "win32":
                    subprocess.Popen(
                        [execute_after],
                        shell=True,
                        creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
                    )
                else:
                    subprocess.Popen([execute_after])
                logging.info("Application restarted successfully.")
            else:
                logging.error(f"Execute path does not exist: {execute_after}")
                # Try dest_path as fallback
                if os.path.exists(dest_path):
                    logging.info(f"Trying dest_path: {dest_path}")
                    if sys.platform == "win32":
                        subprocess.Popen(
                            [dest_path],
                            shell=True,
                            creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
                        )
                    else:
                        subprocess.Popen([dest_path])
                    logging.info("Application restarted successfully (using dest_path).")
                else:
                    logging.error(f"Both execute_after and dest_path do not exist!")
        except Exception as e:
            logging.error(f"Failed to restart application: {e}", exc_info=True)

    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
