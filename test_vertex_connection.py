
import os
import sys

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv not installed.")

import logging
# Configure minimal logging
logging.basicConfig(level=logging.INFO)

print("--------------------------------------------------")
print("Vertex AI Connection Test")
print("--------------------------------------------------")
print(f"Project ID: {os.getenv('VERTEX_PROJECT_ID')}")
print(f"Location:   {os.getenv('VERTEX_LOCATION')}")
print("--------------------------------------------------")

try:
    from core.providers import VertexGeminiProvider
    
    print("Initializing Provider...")
    provider = VertexGeminiProvider()
    
    print("Attempting to generate text...")
    response = provider.generate_text("Hello, are you connected? Reply with 'Yes, I am connected.'")
    
    print("--------------------------------------------------")
    print(f"Response: {response}")
    print("--------------------------------------------------")
    
    if "Yes, I am connected" in response:
        print("SUCCESS: Vertex AI is connected and working!")
    elif "Model response unavailable" in response:
        print("FAILURE: Connection refused or authentication missing.")
    else:
        print("SUCCESS: Received response (content may vary).")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
