import sys
import os
import time
from sqlalchemy import text

print("--- Starting Migration Script ---")

# Add backend dir to sys.path to allow imports from app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    print("Importing app.database...")
    from app.database import engine
    print("Import successful.")
except Exception as e:
    print(f"Failed to import engine: {e}")
    sys.exit(1)

def run_migration_file(filename):
    print(f"Running migration: {filename}")
    if not os.path.exists(filename):
        print(f"Error: File not found: {filename}")
        return

    with open(filename, 'r', encoding='utf-8') as f:
        sql = f.read()

    statements = sql.split(';')
    
    print("Attempting to connect to database...")
    start_time = time.time()
    try:
        with engine.connect() as connection:
            print(f"Connected successfully in {time.time() - start_time:.2f}s")
            for statement in statements:
                if statement.strip():
                    try:
                        print(f"Executing: {statement.strip().splitlines()[0][:50]}...")
                        connection.execute(text(statement))
                    except Exception as e:
                        print(f"Error executing statement: {e}")
            
            print("Committing changes...")
            connection.commit()
            print("Migration execution finished.")
    except Exception as e:
        print(f"Connection failed after {time.time() - start_time:.2f}s: {e}")

if __name__ == "__main__":
    sql_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations", "add_admin_columns.sql")
    run_migration_file(sql_file)
