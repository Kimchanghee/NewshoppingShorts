import pymysql
import sys
import time

host = "34.122.103.96"
user = "ssmaker_user"
password = "Cd.Bl}`0ZOvR*9ob" # Correct backtick
db = "ssmaker_auth"

print(f"Connecting to {host} as {user}...")
try:
    conn = pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=db,
        connect_timeout=10
    )
    print("Connection successful!")
    with conn.cursor() as cursor:
        print("Adding columns...")
        # Ignore errors if columns exist
        queries = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_plain VARCHAR(255) NULL;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_online BOOLEAN NOT NULL DEFAULT FALSE;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_heartbeat TIMESTAMP NULL;",
            "ALTER TABLE registration_requests ADD COLUMN IF NOT EXISTS password_plain VARCHAR(255) NULL;"
        ]
        for q in queries:
            try:
                print(f"Executing: {q[:50]}...")
                cursor.execute(q)
                print("Done.")
            except Exception as q_e:
                print(f"Query error (ignoring): {q_e}")
        
        conn.commit()
        print("Migration successful!")
    conn.close()
except Exception as e:
    print(f"Connection failed: {e}")
