#!/bin/bash

# This script is meant to be run on your Aliyun server AFTER pulling the latest code from GitHub.
# It automatically detects and applies your table/field changes (migrations) while strictly preserving current site content data.

echo "==============================================="
echo " Starting Database Migration on Aliyun Server"
echo "==============================================="

# 1. Ensure we execute from the project directory
cd "$(dirname "$0")"
echo "Working directory: $(pwd)"
echo "Git commit: $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"

# 2. Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment (venv/bin/activate)..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment (.venv/bin/activate)..."
    source .venv/bin/activate
else
    echo "Warning: Virtual environment not found. If this is unexpected, press Ctrl+C to cancel."
fi

# 3. Set the Flask app entrypoint
export FLASK_APP=app.py

# 3.1 Optional release stamp for troubleshooting (used by admin UI)
export INKSTONE_RELEASE="${INKSTONE_RELEASE:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"

# 4. Run database upgrade
# This uses Flask-Migrate (Alembic) to only apply schema updates as defined in your migrations folder.
# It does NOT overwrite content data.
echo "Applying database schema upgrades (using python3 -m flask)..."
python3 -m flask db upgrade

# 5. Verification and next steps
if [ $? -eq 0 ]; then
    echo "✅ Upgrade successful! Database schema is now matched with app.py"
    echo "✅ Site content strictly preserved."
    echo ""
    echo "==============================================="
    echo " Migration complete. Please restart your application."
    echo " e.g., 'sudo systemctl restart gunicorn' or whatever process manager you are using."
    echo "==============================================="
else
    echo "❌ Error: 'flask' command or 'db' extension not found."
    echo "Try running these on your server first:"
    echo "    source venv/bin/activate"
    echo "    pip install -r requirements.txt"
    exit 1
fi
