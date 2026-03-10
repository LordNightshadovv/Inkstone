import os
import sys
import json
from datetime import datetime

# Add the current directory to path so it can find app.py
sys.path.append(os.getcwd())

try:
    from app import app, db, Post, Theme, Series, Protagonist, Keyword, CMSUser, PendingUpdate, regenerate_all_static_pages
except ImportError as e:
    print(f"❌ Error: Could not import app modules. Are you in the right directory? {e}")
    sys.exit(1)

def run_fix():
    print("🚀 Starting Production Fix Script...")
    
    with app.app_context():
        # 1. Check Tables
        print("\n📊 Checking Database Structure...")
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        
        required_tables = ['cms_user', 'pending_update']
        for table in required_tables:
            if table in tables:
                print(f"  ✓ Table '{table}' exists.")
            else:
                print(f"  ⚠️ Table '{table}' is MISSING! Please run 'flask db upgrade' first.")

        # 2. Fix NULL Statuses
        print("\n🔧 Repairing 'status' fields...")
        models_to_fix = [Post, Theme, Series, Protagonist, Keyword]
        for model in models_to_fix:
            try:
                # Check if status column exists
                columns = [c['name'] for c in inspector.get_columns(model.__tablename__)]
                if 'status' not in columns:
                    print(f"  ⚠️ Model {model.__name__} is missing 'status' column. Run migrations!")
                    continue
                
                # Update NULL or empty statuses to 'published'
                count = 0
                items = model.query.all()
                for item in items:
                    if not item.status or item.status.strip() == '':
                        item.status = 'published'
                        count += 1
                
                if count > 0:
                    db.session.commit()
                    print(f"  ✓ Fixed {count} records in {model.__name__}.")
                else:
                    print(f"  ✓ {model.__name__} status fields are already healthy.")
            except Exception as e:
                print(f"  ❌ Error fixing {model.__name__}: {e}")

        # 3. Ensure Admin User exists
        print("\n👤 Checking Admin Account...")
        vold = CMSUser.query.filter_by(username='Vold').first()
        if not vold:
            print("  ⚠️ Admin 'Vold' not found. Creating default admin...")
            new_admin = CMSUser(
                username='Vold',
                password='Volkerrechtssubjectivitat',
                name='Vold',
                role='admin'
            )
            db.session.add(new_admin)
            db.session.commit()
            print("  ✓ Admin 'Vold' created.")
        else:
            # Ensure password is correct based on user requested change
            if vold.password != 'Volkerrechtssubjectivitat':
                vold.password = 'Volkerrechtssubjectivitat'
                db.session.commit()
                print("  ✓ Admin password updated.")
            print("  ✓ Admin account is correct.")

        # 4. Regenerate Static Pages
        print("\n🖼️ Regenerating Static Pages...")
        try:
            success = regenerate_all_static_pages()
            if success:
                print("  ✓ Static pages regenerated successfully.")
            else:
                print("  ❌ Static page regeneration failed.")
        except Exception as e:
            print(f"  ❌ Error during regeneration: {e}")

    print("\n✅ All production fixes complete!")

if __name__ == "__main__":
    run_fix()
