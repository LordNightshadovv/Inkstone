import os

# Get the absolute path of the directory where this file is located
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Secret key for signing session cookies and other security-related needs
    # It's read from an environment variable for security, with a fallback for development
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'

    # Database configuration
    # Azure App Service runs code from /tmp but only /home persists
    # Use absolute paths to /home for all persistent data
    if os.environ.get('WEBSITE_INSTANCE_ID'):  # Running on Azure
        # Use HOME environment variable for portability
        home_dir = os.environ.get('HOME', '/home')
        db_path = os.path.join(home_dir, 'site', 'wwwroot', 'data', 'app.db')
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    else:  # Local development
        db_path = os.path.join(basedir, 'app.db')
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + db_path

    # Disable an SQLAlchemy feature that is not needed and adds overhead
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'Vold'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'Inkstone'

    # Server Name for URL generation outside of request context
    # SERVER_NAME = 'localhost:5000'
