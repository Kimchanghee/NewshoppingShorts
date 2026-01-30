from utils.secrets_manager import SecretsManager
import config

def clear_all_gemini_keys():
    print("Clearing all Gemini API keys from SecretsManager...")
    for i in range(1, 11):
        key_name = f"gemini_api_{i}"
        deleted = SecretsManager.delete_api_key(key_name)
        if deleted:
            print(f"Deleted {key_name}")
    
    # Also for main.py's legacy handler
    for i in range(1, 11):
        key_name = f"gemini_api_{i}"
        deleted = SecretsManager.delete_api_key(key_name)
    
    # Clear config
    config.GEMINI_API_KEYS = {}
    print("Clear complete.")

if __name__ == "__main__":
    clear_all_gemini_keys()
