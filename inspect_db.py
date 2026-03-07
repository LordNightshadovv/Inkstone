import sqlite3
import os

db_path = 'app.db'
if os.path.exists(db_path):
    print(f"Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Drop temp tables
    try:
        cursor.execute('DROP TABLE IF EXISTS _alembic_tmp_theme')
        cursor.execute('DROP TABLE IF EXISTS _alembic_tmp_community_card')
        conn.commit()
        print("Dropped temp tables.")
    except Exception as e:
        print(f"Error dropping temp tables: {e}")
        
    # Inspect theme schema
    try:
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='theme'")
        schema = cursor.fetchone()
        if schema:
            print("\nTheme Table Schema:")
            print(schema[0])
        else:
            print("\nTheme table not found.")
    except Exception as e:
        print(f"Error inspecting schema: {e}")
        
    finally:
        conn.close()
else:
    print(f"Database file {db_path} not found.")
