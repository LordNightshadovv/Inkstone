import sqlite3
import os

db_path = 'app.db'
if os.path.exists(db_path):
    print(f"Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute('DROP TABLE IF EXISTS _alembic_tmp_community_card')
        conn.commit()
        print("Dropped _alembic_tmp_community_card successfully.")
    except Exception as e:
        print(f"Error dropping table: {e}")
    finally:
        conn.close()
else:
    print(f"Database file {db_path} not found.")
