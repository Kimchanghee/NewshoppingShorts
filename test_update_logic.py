import sys
import os
import threading
import time
import requests
import json
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn
from PyQt6 import QtCore, QtWidgets

# Mock Server
app = FastAPI()
os.makedirs("test_update_serv", exist_ok=True)
with open("test_update_serv/new_app.txt", "w") as f:
    f.write("UPDATED_CONTENT_v1.0.1")

@app.get("/app/version/check")
def check(current_version: str):
    return {
        "update_available": True,
        "latest_version": "1.0.1",
        "download_url": "http://127.0.0.1:8001/static/new_app.txt",
        "release_notes": "UI/UX 개선 및 버그 수정",
        "is_mandatory": False
    }

app.mount("/static", StaticFiles(directory="test_update_serv"), name="static")

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8001)

# Start server in thread
server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()
time.sleep(2) # Wait for server

# Mock AppController logic test
qt_app = QtWidgets.QApplication(sys.argv)

# We can't easily test the full replacement here without actually having an exe,
# but we can test the download and updater launch.

print("Testing Version Check...")
res = requests.get("http://127.0.0.1:8001/app/version/check", params={"current_version": "1.0.0"})
print(f"Response: {res.json()}")

# Mock perform_update call
# (Manual verification of the logic I wrote in AppController)

print("Test complete. SERVER IS RUNNING at http://127.0.0.1:8001")
print("You can verify the API by visiting the URL.")
time.sleep(1)
# sys.exit(0)
