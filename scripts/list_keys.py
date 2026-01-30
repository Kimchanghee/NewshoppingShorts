from utils.secrets_manager import SecretsManager

def list_all_keys():
    keys = SecretsManager.list_stored_keys()
    print(f"Stored keys in SecretsManager: {keys}")
    
    for key in keys:
        val = SecretsManager.get_api_key(key)
        print(f"Key: {key}, Value length: {len(val) if val else 0}")

if __name__ == "__main__":
    list_all_keys()
