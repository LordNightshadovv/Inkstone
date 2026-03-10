import os
import sys
import json
from datetime import datetime

# Add the current directory to path so it can find app.py
sys.path.append(os.getcwd())

try:
    from app import app, db, Post, Theme, Series, Protagonist, Keyword, CMSUser, PendingUpdate, regenerate_all_static_pages, SloganBackground
except ImportError as e:
    print(f"❌ Error: Could not import app modules. Are you in the right directory? {e}")
    sys.exit(1)

def check_file(filename, category):
    if not filename:
        return True
    path = os.path.join('static', 'uploads', filename)
    if not os.path.exists(path):
        print(f"  🚩 MISSING FILE [{category}]: {path}")
        return False
    return True

def run_fix():
    print("====================================================")
    print("🚀 Inkstone Production Deep System Repair")
    print("====================================================")
    
    with app.app_context():
        # 1. Inspect Database Schema
        print("\n🔍 Phase 1: Checking Database Schema...")
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        
        # Check required tables
        critical_tables = ['cms_user', 'pending_update', 'post', 'theme', 'series', 'protagonist', 'keyword']
        for table in critical_tables:
            if table in tables:
                print(f"  [DB] ✓ Table '{table}' exists.")
                # Detailed column check
                columns = [c['name'] for c in inspector.get_columns(table)]
                if table in ['post', 'theme', 'series', 'protagonist', 'keyword']:
                    if 'status' not in columns:
                        print(f"  [DB] ❌ Table '{table}' is MISSING the 'status' column!")
                    else:
                        print(f"  [DB] ✓ Table '{table}' has 'status' column.")
            else:
                print(f"  [DB] ❌ Table '{table}' is MISSING from database!")
        
        # 2. Repair Data Integrity
        print("\n🔧 Phase 2: Repairing Data Integrity...")
        models_to_sync = [Post, Theme, Series, Protagonist, Keyword]
        for model in models_to_sync:
            try:
                count = 0
                items = model.query.all()
                for item in items:
                    # Fix NULL statuses
                    if not hasattr(item, 'status') or item.status is None or item.status.strip() == '':
                        item.status = 'published'
                        count += 1
                    
                    # Fix is_active if it exists (for models that have it)
                    if hasattr(item, 'is_active'):
                        if item.is_active is None:
                            item.is_active = True
                            count += 1
                            
                if count > 0:
                    db.session.commit()
                    print(f"  [DATA] ✓ Repaired {count} records in {model.__name__}.")
                else:
                    print(f"  [DATA] ✓ {model.__name__} data is healthy.")
            except Exception as e:
                print(f"  [DATA] ❌ Error processing {model.__name__}: {e}")

        # 3. Media Asset Audit
        print("\n🖼️ Phase 3: Media Asset Audit (static/uploads/)...")
        missing_count = 0
        
        # Check Post posters
        print("  Checking Post images...")
        for post in Post.query.all():
            if post.poster_filename:
                if not check_file(post.poster_filename, "Post Poster"): missing_count += 1
        
        # Check Theme images
        print("  Checking Theme images...")
        for theme in Theme.query.all():
            if theme.card_image:
                if not check_file(theme.card_image, "Theme Card"): missing_count += 1
            if theme.background_image:
                if not check_file(theme.background_image, "Theme Background"): missing_count += 1
                
        # Check Slogan Backgrounds
        print("  Checking Slogan backgrounds...")
        for bg in SloganBackground.query.all():
            if bg.filename:
                if not check_file(bg.filename, "Slogan BG"): missing_count += 1
        
        if missing_count == 0:
            print("  [MEDIA] ✓ All media assets found on disk.")
        else:
            print(f"  [MEDIA] ⚠️ Total {missing_count} media files missing from static/uploads/")
            print("  [MEDIA] TIP: You should upload these files to the production server.")

        # 4. Critical Account Safety
        print("\n🔐 Phase 4: Critical Account Check...")
        admin = CMSUser.query.filter_by(username='Vold').first()
        if not admin:
            print("  [AUTH] ⚠️ Admin 'Vold' missing. Recreating...")
            admin = CMSUser(
                username='Vold',
                password='Volkerrechtssubjectivitat',
                name='Vold',
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("  [AUTH] ✓ Secret Admin account restored.")
        else:
            if admin.password != 'Volkerrechtssubjectivitat':
                admin.password = 'Volkerrechtssubjectivitat'
                db.session.commit()
                print("  [AUTH] ✓ Admin password updated to required value.")
            if admin.role != 'admin':
                admin.role = 'admin'
                db.session.commit()
                print("  [AUTH] ✓ Admin role verified.")
            print("  [AUTH] ✓ Admin account is secure.")

        # 5. Static Site Integrity
        print("\n🏗️ Phase 5: Rebuilding Static Integrity...")
        try:
            success = regenerate_all_static_pages()
            if success:
                print("  [SITE] ✓ All static pages (posts/themes) have been refreshed.")
            else:
                print("  [SITE] ❌ Failed to regenerate all pages. Check app logs.")
        except Exception as e:
            print(f"  [SITE] ❌ Critical Error during rebuild: {e}")

    print("\n" + "="*50)
    print("✅ REPAIR COMPLETE")
    print("Please run: sudo systemctl restart inkstone")
    print("====================================================")

if __name__ == "__main__":
    run_fix()
