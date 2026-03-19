import os
import re
import requests
import hashlib
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from flask_migrate import Migrate
from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import StringField, TextAreaField, BooleanField, SubmitField, PasswordField, IntegerField, ValidationError
from wtforms.validators import DataRequired, Length, NumberRange, Optional
from wtforms.fields import SelectMultipleField, SelectField

# Custom IntegerField that handles empty strings gracefully
class OptionalIntegerField(IntegerField):
    """IntegerField that treats empty strings as None instead of raising validation errors"""
    def process_formdata(self, valuelist):
        if valuelist:
            if valuelist[0] == '' or valuelist[0] is None:
                self.data = None
            else:
                try:
                    self.data = int(valuelist[0])
                except (ValueError, TypeError):
                    self.data = None
                    raise ValueError(self.gettext('Not a valid integer value.'))
from werkzeug.utils import secure_filename
from config import Config
from flask_compress import Compress
from PIL import Image
import io

# Initialize the Flask application
app = Flask(__name__)
# Load configuration from the Config class
app.config.from_object(Config)

# --- Deployment/runtime configuration ---
#
# Note: Aliyun production should provide stable env vars (especially SECRET_KEY) and
# should store uploads in a persistent directory that is NOT wiped by deploys.
#
# Allow explicit override first (works across all environments).
app.config['UPLOAD_FOLDER'] = os.environ.get('INKSTONE_UPLOAD_DIR') or app.config.get('UPLOAD_FOLDER')
app.config['STATIC_POSTS_FOLDER'] = os.environ.get('INKSTONE_STATIC_POSTS_DIR') or app.config.get('STATIC_POSTS_FOLDER')

# Configure default folders - use persistent storage on Azure
# Azure runs code from /tmp but only /home persists
if not app.config.get('UPLOAD_FOLDER') or not app.config.get('STATIC_POSTS_FOLDER'):
    if os.environ.get('WEBSITE_INSTANCE_ID'):  # Running on Azure
        home_dir = os.environ.get('HOME', '/home')
        app.config['UPLOAD_FOLDER'] = app.config.get('UPLOAD_FOLDER') or os.path.join(home_dir, 'site', 'wwwroot', 'uploads')
        # Also configure static posts folder for generated HTML files
        app.config['STATIC_POSTS_FOLDER'] = app.config.get('STATIC_POSTS_FOLDER') or os.path.join(home_dir, 'site', 'wwwroot', 'static', 'posts')
    else:  # Default / local / Aliyun if not overridden
        app.config['UPLOAD_FOLDER'] = app.config.get('UPLOAD_FOLDER') or 'static/uploads'
        app.config['STATIC_POSTS_FOLDER'] = app.config.get('STATIC_POSTS_FOLDER') or 'static/posts'

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config.get('STATIC_POSTS_FOLDER', 'static/posts'), exist_ok=True)

# A simple release identifier used for cache-busting and troubleshooting.
APP_RELEASE = (
    os.environ.get('INKSTONE_RELEASE')
    or os.environ.get('RELEASE')
    or os.environ.get('GIT_SHA')
    or os.environ.get('SOURCE_VERSION')
    or datetime.utcnow().strftime('%Y%m%d%H%M%S')
)

# Enable compression for all responses
compress = Compress()
compress.init_app(app)

# Configure compression settings
app.config['COMPRESS_MIMETYPES'] = [
    'text/html',
    'text/css',
    'text/xml',
    'application/json',
    'application/javascript',
    'text/javascript',
    'image/svg+xml'
]
app.config['COMPRESS_LEVEL'] = 6  # Compression level (1-9, 6 is default)
app.config['COMPRESS_MIN_SIZE'] = 500  # Minimum response size to compress (bytes)

# Initialize the database extension
db = SQLAlchemy(app)
# Initialize the database migration extension
migrate = Migrate(app, db)

# --- Forms ---

# --- Response hardening for admin correctness ---
@app.after_request
def add_admin_no_cache_headers(response):
    """
    Admin UI must not be cached by browsers/proxies, otherwise stale HTML/CSS can
    present as a 'corrupted' or old CMS intermittently.
    """
    try:
        if request.path.startswith('/admin'):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            response.headers['X-Inkstone-Release'] = APP_RELEASE
    except Exception:
        # Never break responses due to header logic.
        pass
    return response


@app.context_processor
def inject_app_release():
    return {'app_release': APP_RELEASE}

# Form for the admin login page
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

# Form for creating and editing multi-modal posts
# Form for creating initiative posts (simplified version)
class InitiativePostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=120)])
    abstract = TextAreaField('Abstract', validators=[DataRequired(), Length(max=500)], render_kw={'rows': 3})
    poster_upload = FileField('Poster Image')
    text_content = TextAreaField('Text Content', render_kw={'id': 'text-editor'})
    youtube_url = StringField('YouTube URL')
    use_youtube_poster = BooleanField('Use YouTube Video as Poster')
    gallery_template = StringField('Gallery Template')
    is_featured = BooleanField('Featured Post')
    featured_template = StringField('Featured Template')
    theme_id = SelectField('Initiative Theme', coerce=int, validators=[DataRequired()])
    series_id = SelectField('Series', coerce=int, validators=[DataRequired()])
    frame_color = StringField('Frame Color', validators=[Length(max=7)], default='#2563eb')
    # Publication date fields
    pub_year = IntegerField('Year', validators=[NumberRange(min=2020, max=2030)], default=datetime.utcnow().year)
    pub_month = IntegerField('Month', validators=[NumberRange(min=1, max=12)], default=datetime.utcnow().month)
    pub_day = IntegerField('Day', validators=[NumberRange(min=1, max=31)], default=datetime.utcnow().day)
    submit = SubmitField('Publish Initiative')

class PostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=120)])
    slug = StringField('URL Slug', validators=[Length(max=200)])
    author = StringField('Author', validators=[DataRequired(), Length(max=200)])
    editors = StringField('Edited By', validators=[Length(max=200)])
    translated_by = StringField('Translated By', validators=[Length(max=200)])
    keywords = StringField('Keywords', validators=[Length(max=300)])
    abstract = TextAreaField('Abstract', validators=[Length(max=500)], render_kw={'rows': 3})
    poster_upload = FileField('Poster Image') # New field for poster
    text_content = TextAreaField('Text Content', render_kw={'id': 'text-editor'})
    youtube_url = StringField('YouTube URL')
    use_youtube_poster = BooleanField('Use YouTube Video as Poster')
    gallery_template = StringField('Gallery Template')  # Will be set via JavaScript
    is_featured = BooleanField('Featured Post')
    featured_template = StringField('Featured Template')  # Will be set via JavaScript
    tags = SelectMultipleField('Tags', coerce=int)
    theme_id = SelectField('Theme', coerce=int, validators=[])
    series_id = SelectField('Series', coerce=int, validators=[])
    series_order = OptionalIntegerField('Order in Series', validators=[])
    # Publication date fields
    pub_year = IntegerField('Year', validators=[NumberRange(min=2020, max=2030)], default=datetime.utcnow().year)
    pub_month = IntegerField('Month', validators=[NumberRange(min=1, max=12)], default=datetime.utcnow().month)
    pub_day = IntegerField('Day', validators=[NumberRange(min=1, max=31)], default=datetime.utcnow().day)
    submit = SubmitField('Publish')
    
    def validate(self, extra_validators=None):
        """Custom validation: post must have content (text, images, or video)"""
        # Call parent validation
        if not super().validate(extra_validators):
            print(f"❌ Base validation failed: {self.errors}")
            return False
        
        # Check if post has any content
        has_text = bool(self.text_content.data and self.text_content.data.strip())
        has_youtube = bool(self.youtube_url.data and self.youtube_url.data.strip())
        has_gallery = bool(self.gallery_template.data and self.gallery_template.data.strip())
        
        print(f"📝 Content check - Text: {has_text}, YouTube: {has_youtube}, Gallery: {has_gallery}")
        
        if not (has_text or has_youtube or has_gallery):
            print("❌ No content found")
            self.text_content.errors.append('Post must have at least one of: text content, images, or YouTube video')
            return False
        
        print("✅ Content validation passed")
        return True

# Form for creating and editing themes
class ThemeForm(FlaskForm):
    name = StringField('Theme Name', validators=[DataRequired(), Length(max=50)])
    slug = StringField('URL Slug', validators=[DataRequired(), Length(max=50)], 
                      render_kw={'placeholder': 'chinese-culture'})
    description = TextAreaField('Description', validators=[DataRequired()], render_kw={'rows': 3})
    icon = StringField('Icon (Emoji/Text)', validators=[Length(max=10)], default='📝')
    icon_file = FileField('Icon Image', validators=[])
    color = StringField('Color', validators=[DataRequired(), Length(max=7)], default='#3A7467')
    background_image = FileField('Hero Banner (Theme Page)', validators=[])
    card_image = FileField('Card Image (Explore Themes)', validators=[])
    is_active = BooleanField('Active Theme', default=True)
    is_initiative = BooleanField('Initiative Theme (accepts only initiative posts)', default=False)
    submit = SubmitField('Save Theme')

# Form for creating and editing series
class SeriesForm(FlaskForm):
    title = StringField('Series Title', validators=[DataRequired(), Length(max=120)])
    description = TextAreaField('Description', validators=[Length(max=500)], render_kw={'rows': 3})
    is_active = BooleanField('Active Series', default=True)
    submit = SubmitField('Save Series')
    
    def __init__(self, *args, series_id=None, **kwargs):
        super(SeriesForm, self).__init__(*args, **kwargs)
        self.series_id = series_id
    
    def validate_title(self, field):
        """Validate that series title is unique"""
        # Check if another series with this title exists
        query = Series.query.filter(Series.title == field.data)
        # If editing, exclude the current series from the check
        if self.series_id:
            query = query.filter(Series.id != self.series_id)
        
        existing_series = query.first()
        if existing_series:
            raise ValidationError('A series with this title already exists. Please choose a different title.')

# Form for creating and editing protagonist profiles
class ProtagonistForm(FlaskForm):
    name = StringField('Protagonist Name', validators=[DataRequired(), Length(max=200)])
    is_active = BooleanField('Active (displayed in posts)', default=True)
    submit = SubmitField('Save Protagonist')
    
    def __init__(self, *args, protagonist_id=None, **kwargs):
        super(ProtagonistForm, self).__init__(*args, **kwargs)
        self.protagonist_id = protagonist_id
    
    def validate_name(self, field):
        """Validate that protagonist name is unique (case-insensitive)"""
        # Check if another protagonist with this name exists
        query = Protagonist.query.filter(
            db.func.lower(Protagonist.name) == field.data.lower()
        )
        # If editing, exclude the current protagonist from the check
        if self.protagonist_id:
            query = query.filter(Protagonist.id != self.protagonist_id)
        
        existing_protagonist = query.first()
        if existing_protagonist:
            raise ValidationError('A protagonist with this name already exists. Please choose a different name.')

# Form for creating and editing keywords
class KeywordForm(FlaskForm):
    name = StringField('Keyword', 
                      validators=[DataRequired(), Length(max=50)],
                      render_kw={'placeholder': 'Enter keyword (any case)'})
    submit = SubmitField('Save Keyword')
    
    def __init__(self, *args, keyword_id=None, **kwargs):
        super(KeywordForm, self).__init__(*args, **kwargs)
        self.keyword_id = keyword_id
    
    def validate_name(self, field):
        """Validate that keyword is unique (case-insensitive)."""
        # Normalize to lowercase for comparison
        normalized_name = field.data.strip().lower()
        
        query = Keyword.query.filter(
            db.func.lower(Keyword.name) == normalized_name
        )
        if self.keyword_id:
            query = query.filter(Keyword.id != self.keyword_id)
        
        existing = query.first()
        if existing:
            raise ValidationError(
                f'The keyword "{existing.display_name}" already exists. '
                'Please choose a different keyword.'
            )

# --- Models ---

# Function to generate a URL-friendly slug from a string
def slugify(s):
    # Replace non-word characters with a hyphen
    return re.sub(r'[^\w]+', '-', s).lower()

def handle_theme_icon_upload(icon_file):
    """Handle theme icon file upload and return filename"""
    if icon_file and icon_file.filename:
        # Check if file has allowed extension
        allowed_extensions = {'jpg', 'jpeg', 'png'}
        if '.' in icon_file.filename and \
           icon_file.filename.rsplit('.', 1)[1].lower() in allowed_extensions:
            
            # Create secure filename
            filename = secure_filename(icon_file.filename)
            # Add timestamp to avoid conflicts
            import time
            timestamp = str(int(time.time()))
            name, ext = filename.rsplit('.', 1)
            filename = f"theme_icon_{timestamp}_{name}.{ext}"
            
            # Save file
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            icon_file.save(filepath)
            
            return filename
    return None

# Association table for the many-to-many relationship between posts and tags
post_tags = db.Table('post_tags',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

# Association table for the many-to-many relationship between posts and keywords
post_keywords = db.Table('post_keywords',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('keyword_id', db.Integer, db.ForeignKey('keyword.id'), primary_key=True)
)

# Association table for the many-to-many relationship between posts and themes
post_themes = db.Table('post_themes',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('theme_id', db.Integer, db.ForeignKey('theme.id'), primary_key=True)
)

# Association table for the many-to-many relationship between posts and protagonists
post_protagonists = db.Table('post_protagonists',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('protagonist_id', db.Integer, db.ForeignKey('protagonist.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)

# Database model for themes
class Theme(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(255), default='📝')  # Emoji icon or filename
    icon_type = db.Column(db.String(10), default='emoji')  # 'emoji' or 'file'

    color = db.Column(db.String(7), default='#3A7467')  # Hex color code
    background_image = db.Column(db.String(255), nullable=True) # Background image for theme hero/banner
    card_image = db.Column(db.String(255), nullable=True) # Image for explore themes card
    is_active = db.Column(db.Boolean, default=True)
    is_initiative = db.Column(db.Boolean, default=False)  # Initiative themes accept only initiative posts
    status = db.Column(db.String(20), default='published')  # 'published' or 'pending'
    
    # Note: Many-to-many relationship with posts is defined in Post model via post_themes table

    @property
    def published_posts(self):
        """Return all published posts for this theme (from both relationships)"""
        # Get posts from many-to-many relationship
        m2m_posts = [p for p in self.posts if p.status == 'published']
        # Get posts from foreign key relationship
        fk_posts = Post.query.filter(Post.theme_id == self.id, Post.status == 'published').all()
        # Combine and remove duplicates
        all_posts = list(set(m2m_posts + fk_posts))
        return all_posts
    
    @property
    def published_post_count(self):
        """Return count of all posts for this theme"""
        return len(self.published_posts)

    def __repr__(self):
        return f'<Theme {self.name}>'

# Database model for tags
class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    category = db.Column(db.String(20), nullable=False)  # media_type, display_type, content_type
    color = db.Column(db.String(7), default='#3A7467')  # Hex color code

    def __repr__(self):
        return f'<Tag {self.name}>'

# Database model for keywords
class Keyword(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # Stored in lowercase
    usage_count = db.Column(db.Integer, default=0, nullable=False)  # Accurate count
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = db.Column(db.String(20), default='published')  # 'published' or 'pending'
    
    @property
    def display_name(self):
        """Return keyword in uppercase for display."""
        return self.name.upper()
    
    @property
    def post_count(self):
        """Return count of associated posts (same as usage_count)."""
        return self.usage_count
    
    def recalculate_usage_count(self):
        """Recalculate usage count from actual post associations."""
        self.usage_count = len(self.posts)
        return self.usage_count
    
    def __repr__(self):
        return f'<Keyword {self.name} (used {self.usage_count} times)>'

# Database model for series
class Series(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    status = db.Column(db.String(20), default='published')  # 'published' or 'pending'
    
    # Relationship to posts
    posts = db.relationship('Post', backref='series', lazy=True, order_by='Post.series_order')
    
    def __repr__(self):
        return f'<Series {self.title}>'

# Database model for protagonists (authors)
class Protagonist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    status = db.Column(db.String(20), default='published')  # 'published' or 'pending'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Many-to-many relationship with posts
    posts = db.relationship('Post', secondary=post_protagonists, 
                           backref=db.backref('protagonists', lazy='dynamic'),
                           lazy='dynamic')
    
    @property
    def post_count(self):
        """Return count of associated posts."""
        return self.posts.count()
    
    @property
    def active_display_name(self):
        """Return name only if active, empty string otherwise."""
        return self.name if self.is_active else ''
    
    def __repr__(self):
        return f'<Protagonist {self.name}>'

class CMSUser(db.Model):
    """Model for managing CMS accounts with roles and permissions."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)  # Stored as plain text per requirement
    name = db.Column(db.String(120), nullable=False)      # Real name
    role = db.Column(db.String(20), nullable=False, default='editor')  # admin, editor, visitor
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<CMSUser {self.username} ({self.role})>'

# Database model for pending updates
class PendingUpdate(db.Model):
    """Model for tracking proposed changes from visitor users."""
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)  # theme, post, keyword, protagonist, series
    action = db.Column(db.String(20), nullable=False)    # create, update, delete
    item_id = db.Column(db.Integer, nullable=True)       # ID of the item being updated/deleted
    item_name = db.Column(db.String(200), nullable=True) # Display name of the item
    data = db.Column(db.Text, nullable=True)             # JSON serialized data of the update
    user_id = db.Column(db.Integer, db.ForeignKey('cms_user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to user
    user = db.relationship('CMSUser', backref='pending_updates')

    def __repr__(self):
        return f'<PendingUpdate {self.category} {self.action} by user {self.user_id}>'



# Database model for multi-modal posts
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    author = db.Column(db.String(200), nullable=False)  # Increased length for multiple authors
    editors = db.Column(db.String(200), nullable=True)  # New field for editors
    translated_by = db.Column(db.String(200), nullable=True)  # New field for translators
    keywords = db.Column(db.String(300), nullable=True)  # New field for keywords
    abstract = db.Column(db.Text, nullable=True)  # Optional for regular posts, required for initiatives
    text_content = db.Column(db.Text, nullable=True)
    youtube_url = db.Column(db.String(255), nullable=True)
    gallery_template = db.Column(db.String(20), nullable=True)  # 'slideshow' or 'waterfall'
    is_featured = db.Column(db.Boolean, default=False)
    featured_template = db.Column(db.String(10), nullable=True)  # 'T1' or 'T2'
    poster_filename = db.Column(db.String(255), nullable=True)
    publication_date = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    theme_id = db.Column(db.Integer, db.ForeignKey('theme.id'), nullable=True)
    series_id = db.Column(db.Integer, db.ForeignKey('series.id'), nullable=True)
    series_order = db.Column(db.Integer, nullable=True)  # Order within the series
    is_initiative = db.Column(db.Boolean, default=False)  # Initiative posts have special rules
    frame_color = db.Column(db.String(7), default='#2563eb')  # Custom frame color for initiative posts
    use_youtube_poster = db.Column(db.Boolean, default=False)  # Use YouTube video as poster
    status = db.Column(db.String(20), default='published')  # 'published' or 'pending'
    
    # Relationship to pictures
    pictures = db.relationship('Picture', backref='post', lazy=True, cascade='all, delete-orphan', 
                              foreign_keys='Picture.post_id',
                              order_by='Picture.display_order')
    
    # Many-to-many relationship with tags
    tags = db.relationship('Tag', secondary=post_tags, lazy='subquery',
                           backref=db.backref('posts', lazy=True))
    
    # Many-to-many relationship with keywords
    post_keywords = db.relationship('Keyword', secondary=post_keywords, lazy='subquery',
                                   backref=db.backref('posts', lazy=True))
    
    # Many-to-many relationship with themes
    themes = db.relationship('Theme', secondary=post_themes, lazy='subquery',
                            backref=db.backref('posts', lazy=True))
    
    @property
    def theme(self):
        """Backward compatibility: return the theme from theme_id or first theme from themes list"""
        if self.theme_id:
            return Theme.query.get(self.theme_id)
        elif self.themes:
            return self.themes[0]
        return None
    
    @property
    def active_authors(self):
        """Return author string with only active protagonists displayed."""
        return get_active_authors_display(self)

    @property
    def youtube_embed_url(self):
        """Extracts YouTube video ID and returns embed URL."""
        if not self.youtube_url:
            return None
        
        # Simple regex for YouTube ID
        import re
        match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', self.youtube_url)
        if match:
            return f"https://www.youtube.com/embed/{match.group(1)}"
        return None

    def __repr__(self):
        return f'<Post {self.title}>'

# Generate slug before saving
@db.event.listens_for(Post, 'before_insert')
def receive_before_insert(mapper, connection, target):
    if target.title and not target.slug:
        target.slug = slugify(target.title)

@db.event.listens_for(Theme, 'before_insert')
def receive_theme_before_insert(mapper, connection, target):
    if target.name and not target.slug:
        target.slug = slugify(target.name)

# Series does not need slug generation - removed

# Database model for image galleries
class Picture(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

    def __repr__(self):
        return f'<Picture {self.filename}>'

# Database model for website status
class WebsiteStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(50), nullable=False, default='Maintenance & Updating')  # Public, Maintenance & Updating, Closed
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_by = db.Column(db.String(100), nullable=False, default='Admin')

    def __repr__(self):
        return f'<WebsiteStatus {self.status}>'

# Database model for website analytics
class WebsiteAnalytics(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    visitor_ip = db.Column(db.String(45), nullable=False)  # IPv6 can be up to 45 chars
    country = db.Column(db.String(100), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    page_visited = db.Column(db.String(255), nullable=False)
    visit_timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    session_id = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f'<WebsiteAnalytics {self.visitor_ip} - {self.page_visited}>'

# Database model for subscribers
class Subscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Subscriber {self.email} from {self.ip_address}>'

# Database model for slogan background pictures
class SloganBackground(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<SloganBackground {self.filename}>'

# --- Analytics Helper Functions ---

def get_client_ip():
    """Get the real client IP address"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr

def get_country_from_ip(ip_address):
    """Get country from IP address using a free geolocation service"""
    try:
        # Using ipapi.co free service (1000 requests per day)
        response = requests.get(f'https://ipapi.co/{ip_address}/country_name/', timeout=2)
        if response.status_code == 200:
            return response.text.strip()
    except:
        pass
    return 'Unknown'

def get_session_id():
    """Generate or get session ID for tracking unique visitors"""
    if 'visitor_session' not in session:
        # Create a unique session ID based on IP + User Agent
        ip = get_client_ip()
        user_agent = request.headers.get('User-Agent', '')
        session_data = f"{ip}_{user_agent}_{datetime.now().strftime('%Y%m%d')}"
        session['visitor_session'] = hashlib.md5(session_data.encode()).hexdigest()
    return session['visitor_session']

def is_website_public():
    """Check if website is in public mode for analytics tracking"""
    status = WebsiteStatus.query.order_by(WebsiteStatus.updated_at.desc()).first()
    return status and status.status == 'Public'

def track_visit():
    """Track website visit if analytics are enabled"""
    # Skip tracking for admin routes, static files, and CMS backend
    if (request.endpoint and 
        (request.endpoint.startswith('admin') or 
         request.endpoint.startswith('static') or
         request.path.startswith('/static/') or
         request.path.startswith('/admin/'))):
        return
    
    # Only track if website is public
    if not is_website_public():
        return
    
    try:
        ip = get_client_ip()
        country = get_country_from_ip(ip)
        user_agent = request.headers.get('User-Agent', '')
        page = request.path
        session_id = get_session_id()
        
        # Create analytics record
        analytics = WebsiteAnalytics(
            visitor_ip=ip,
            country=country,
            user_agent=user_agent,
            page_visited=page,
            session_id=session_id
        )
        
        db.session.add(analytics)
        db.session.commit()
    except Exception as e:
        # Don't let analytics errors break the site
        db.session.rollback()
        print(f"Analytics tracking error: {e}")

# Add before_request handler to track visits
@app.before_request
def before_request():
    track_visit()

def get_analytics_stats():
    """Get comprehensive analytics statistics - always show data, but tracking depends on status"""
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # Always calculate statistics from existing data
    views_today = WebsiteAnalytics.query.filter(WebsiteAnalytics.visit_timestamp >= today).count()
    views_week = WebsiteAnalytics.query.filter(WebsiteAnalytics.visit_timestamp >= week_ago).count()
    views_month = WebsiteAnalytics.query.filter(WebsiteAnalytics.visit_timestamp >= month_ago).count()
    total_views = WebsiteAnalytics.query.count()
    
    # Unique visitors (by session_id)
    unique_today = db.session.query(WebsiteAnalytics.session_id).filter(
        WebsiteAnalytics.visit_timestamp >= today
    ).distinct().count()
    
    unique_week = db.session.query(WebsiteAnalytics.session_id).filter(
        WebsiteAnalytics.visit_timestamp >= week_ago
    ).distinct().count()
    
    unique_month = db.session.query(WebsiteAnalytics.session_id).filter(
        WebsiteAnalytics.visit_timestamp >= month_ago
    ).distinct().count()
    
    # Countries statistics
    countries = db.session.query(
        WebsiteAnalytics.country, 
        db.func.count(WebsiteAnalytics.id).label('count')
    ).filter(
        WebsiteAnalytics.country != 'Unknown'
    ).group_by(WebsiteAnalytics.country).order_by(db.desc('count')).limit(5).all()
    
    countries_count = db.session.query(WebsiteAnalytics.country).filter(
        WebsiteAnalytics.country != 'Unknown'
    ).distinct().count()
    
    # Check if tracking is currently enabled
    is_tracking = is_website_public()
    
    return {
        'views_today': views_today,
        'views_week': views_week,
        'views_month': views_month,
        'total_views': total_views,
        'unique_visitors_today': unique_today,
        'unique_visitors_week': unique_week,
        'unique_visitors_month': unique_month,
        'countries_count': countries_count,
        'top_countries': [{'name': c.country, 'count': c.count} for c in countries],
        'enabled': is_tracking
    }

# --- Context Processor for Global Template Variables ---

@app.context_processor
def inject_footer_themes():
    """Make active themes available in all templates for footer navigation"""
    try:
        footer_themes = Theme.query.filter_by(is_active=True).order_by(Theme.name).limit(6).all()
        return dict(footer_themes=footer_themes)
    except:
        # In case of database error, return empty list
        return dict(footer_themes=[])

# --- Admin Routes ---

# Admin login page
@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    # If the user is already logged in, redirect to the admin dashboard
    if 'admin_logged_in' in session:
        return redirect(url_for('admin_dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # 1. Check if the hardcoded super-admin exists in DB (bootstrap if not)
        vold = CMSUser.query.filter_by(username='Vold').first()
        if not vold:
            try:
                # Use current config password as fallback if not set to requested one yet
                # But requirement says Vold's password should be Volkerrechtssubjectivitat
                vold = CMSUser(
                    username='Vold',
                    password='Volkerrechtssubjectivitat',
                    name='Vold',
                    role='admin'
                )
                db.session.add(vold)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"Error bootstrapping admin: {e}")

        # 2. Authenticate against DB
        user = CMSUser.query.filter_by(username=form.username.data).first()
        
        if user and user.password == form.password.data:
            session['admin_logged_in'] = True
            session['user_id'] = user.id
            session['username'] = user.username
            session['user_role'] = user.role
            session['user_name'] = user.name
            
            flash(f'Welcome back, {user.name}!')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password.', 'error')
            
    return render_template('admin/login.html', form=form)

# Admin logout
@app.route('/admin/logout')
def logout():
    # Clear all admin session data
    session.pop('admin_logged_in', None)
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('user_role', None)
    session.pop('user_name', None)
    
    flash('You were logged out.')
    return redirect(url_for('login'))

# --- CMS User Management ---

@app.route('/admin/cms-users')
def admin_cms_users():
    """List and manage CMS user accounts."""
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    # Only admins can access this page
    if session.get('user_role') != 'admin':
        flash('You do not have permission to access CMS user management.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    users = CMSUser.query.all()
    return render_template('admin/cms_users.html', users=users)

@app.route('/admin/cms-users/new', methods=['POST'])
def new_cms_user():
    """Create a new CMS user account."""
    if 'admin_logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if session.get('user_role') != 'admin':
        return jsonify({'error': 'Insufficient permissions'}), 403
    
    try:
        data = request.get_json()
        
        # Check if username already exists
        if CMSUser.query.filter_by(username=data.get('username')).first():
            return jsonify({'error': 'Username already exists'}), 400
            
        new_user = CMSUser(
            username=data.get('username'),
            password=data.get('password'),
            name=data.get('name'),
            role=data.get('role', 'editor')
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'success': True, 'id': new_user.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/cms-users/<int:user_id>/update', methods=['POST'])
def update_cms_user(user_id):
    """Update an existing CMS user account."""
    if 'admin_logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    currentUserRole = session.get('user_role')
    currentUserId = session.get('user_id')
    
    # Only admins can update ANY user. Other roles can potentially update ONLY themselves (if allowed).
    # For now, stick to requirement that admins manage accounts.
    if currentUserRole != 'admin' and currentUserId != user_id:
        return jsonify({'error': 'Insufficient permissions'}), 403
    
    try:
        user = CMSUser.query.get_or_404(user_id)
        data = request.get_json()
        
        # Super admin Vold's username shouldn't be changed if we want to guarantee its existence
        if user.username != 'Vold':
            user.username = data.get('username', user.username)
            
        user.name = data.get('name', user.name)
        user.password = data.get('password', user.password)
        
        # Only admins can change roles
        if currentUserRole == 'admin':
            user.role = data.get('role', user.role)
            
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/cms-users/<int:user_id>/delete', methods=['POST'])
def delete_cms_user(user_id):
    """Delete a CMS user account."""
    if 'admin_logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if session.get('user_role') != 'admin':
        return jsonify({'error': 'Insufficient permissions'}), 403
    
    try:
        user = CMSUser.query.get_or_404(user_id)
        
        # Prevent deleting the super-admin Vold
        if user.username == 'Vold':
            return jsonify({'error': 'Cannot delete the super-admin account'}), 400
            
        db.session.delete(user)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# --- Moderation & Pending Updates ---

@app.route('/admin/pending-updates')
def pending_updates():
    """List and manage pending updates."""
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    # Only admins can access this page
    if session.get('user_role') != 'admin':
        flash('You do not have permission to access moderation tools.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    updates = PendingUpdate.query.order_by(PendingUpdate.created_at.desc()).all()
    return render_template('admin/pending_updates.html', updates=updates)

@app.route('/admin/pending-updates/<int:update_id>/approve', methods=['POST'])
def approve_update(update_id):
    """Approve a pending update."""
    if 'admin_logged_in' not in session or session.get('user_role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        update = PendingUpdate.query.get_or_404(update_id)
        
        # Logic to apply the update based on category
        if update.category == 'Post Update':
            item = Post.query.get(update.item_id)
        elif update.category == 'Theme Update':
            item = Theme.query.get(update.item_id)
        elif update.category == 'Series Update':
            item = Series.query.get(update.item_id)
        elif update.category == 'Protagonist Update':
            item = Protagonist.query.get(update.item_id)
        elif update.category == 'Keyword Update':
            item = Keyword.query.get(update.item_id)
        else:
            item = None
            
        if item and hasattr(item, 'status'):
            item.status = 'published'
            # For items that affect static pages, trigger regeneration
            if update.category in ['Post Update', 'Theme Update', 'Series Update']:
                regenerate_all_static_pages()
        
        db.session.delete(update)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/pending-updates/<int:update_id>/decline', methods=['POST'])
def decline_update(update_id):
    """Decline a pending update."""
    if 'admin_logged_in' not in session or session.get('user_role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        update = PendingUpdate.query.get_or_404(update_id)
        
        if update.action == 'create':
            item = None
            if update.category == 'Post Update':
                item = Post.query.get(update.item_id)
            elif update.category == 'Theme Update':
                item = Theme.query.get(update.item_id)
            elif update.category == 'Series Update':
                item = Series.query.get(update.item_id)
            elif update.category == 'Protagonist Update':
                item = Protagonist.query.get(update.item_id)
            elif update.category == 'Keyword Update':
                item = Keyword.query.get(update.item_id)
                
            if item:
                db.session.delete(item)
        
        db.session.delete(update)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Admin dashboard
@app.route('/admin')
def admin_dashboard():
    # If the user is not logged in, redirect to the login page
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    # Get statistics
    total_posts = Post.query.count()
    total_themes = Theme.query.filter_by(is_active=True).count()
    total_series = Series.query.filter_by(is_active=True).count()
    active_protagonists = Protagonist.query.filter_by(is_active=True).count()
    
    # Get recent posts (all statuses for dashboard)
    recent_posts = Post.query.order_by(Post.publication_date.desc()).limit(5).all()
    
    # Get theme statistics
    theme_stats = db.session.query(
        Theme.name, Theme.color, db.func.count(Post.id).label('post_count')
    ).join(Post, Theme.id == Post.theme_id, isouter=True).filter(
        Theme.is_active == True
    ).group_by(Theme.id).all()
    
    # Get recent series
    recent_series = Series.query.filter_by(is_active=True).order_by(Series.created_at.desc()).limit(5).all()
    
    # Get website status and analytics
    current_status = WebsiteStatus.query.order_by(WebsiteStatus.updated_at.desc()).first()
    if not current_status:
        # Create default status if none exists
        current_status = WebsiteStatus(status='Maintenance & Updating')
        db.session.add(current_status)
        db.session.commit()
    
    analytics_stats = get_analytics_stats()
    
    return render_template('admin/dashboard.html', 
                         total_posts=total_posts,
                         total_themes=total_themes, 
                         total_series=total_series,
                         active_protagonists=active_protagonists,
                         recent_posts=recent_posts,
                         theme_stats=theme_stats,
                         recent_series=recent_series,
                         website_status=current_status,
                         analytics=analytics_stats)

@app.route('/admin/website-status/update', methods=['POST'])
def update_website_status():
    """Update website status (Public, Maintenance & Updating, Closed)"""
    if 'admin_logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    new_status = data.get('status')
    
    if new_status not in ['Public', 'Maintenance & Updating', 'Closed']:
        return jsonify({'error': 'Invalid status'}), 400
    
    try:
        # Create new status record
        status_record = WebsiteStatus(
            status=new_status,
            updated_by='Admin'
        )
        db.session.add(status_record)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'status': new_status,
            'message': f'Website status updated to {new_status}'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/analytics/refresh', methods=['GET'])
def refresh_analytics():
    """Refresh analytics data for dashboard"""
    if 'admin_logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        analytics_stats = get_analytics_stats()
        return jsonify(analytics_stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/posts')
def admin_posts():
    # If the user is not logged in, redirect to the login page
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    # Get all posts from the database
    posts = Post.query.order_by(Post.publication_date.desc()).all()
    
    return render_template('admin/list.html', posts=posts)

# AJAX endpoint for post details
@app.route('/admin/post/<int:post_id>/details')
def get_post_details(post_id):
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    post = Post.query.get_or_404(post_id)
    
    # Manually serialize the necessary fields
    post_data = {
        'id': post.id,
        'title': post.title,
        'author': post.author,
        'editors': post.editors,
        'translated_by': post.translated_by,
        'keywords': post.keywords,
        'abstract': post.abstract,
        'text_content': post.text_content,
        'youtube_url': post.youtube_url,
        'gallery_template': post.gallery_template,
        'is_featured': post.is_featured,
        'featured_template': post.featured_template,
        'publication_date': post.publication_date.isoformat() if post.publication_date else None,
        'tags': [tag.name for tag in post.tags],
        'theme_name': post.themes[0].name if post.themes else None,  # Use first theme from many-to-many
        'themes': [{'id': theme.id, 'name': theme.name} for theme in post.themes]  # All themes
    }
    
    return post_data

# AJAX endpoint for updating featured status
@app.route('/admin/post/<int:post_id>/featured', methods=['POST'])
def update_featured_status(post_id):
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    post = Post.query.get_or_404(post_id)
    data = request.get_json()
    
    is_featured = data.get('is_featured', False)
    featured_template = data.get('featured_template')

    # If setting this post as featured, unfeature all others first
    if is_featured:
        Post.query.filter(Post.id != post_id).update({'is_featured': False})
    
    post.is_featured = is_featured
    post.featured_template = featured_template if is_featured else None
    
    db.session.commit()
    
    return {'success': True}

# API endpoint for frontend modal integration
@app.route('/api/post/<int:post_id>')
def get_post_api(post_id):
    # Try to get from database first
    post = Post.query.get(post_id)
    if post:
        # Get pictures from database
        pictures = [{
            'id': pic.id,
            'filename': pic.filename,
            'display_order': pic.display_order,
            'url': f'https://images.unsplash.com/photo-{1544717297 + pic.display_order}?w=600&h={400 + (pic.display_order * 50)}&fit=crop&crop=faces'
        } for pic in post.pictures]
        
        # Convert to dict for JSON response
        response_data = {
            'id': post.id,
            'title': post.title,
            'author': post.author,
            'editors': post.editors,
            'translated_by': post.translated_by,
            'abstract': post.abstract,
            'text_content': post.text_content,
            'youtube_url': post.youtube_url,
            'gallery_template': post.gallery_template,
            'is_featured': post.is_featured,
            'featured_template': post.featured_template,
            'poster_filename': post.poster_filename,
            'pictures': pictures,
            'publication_date': post.publication_date.isoformat() if post.publication_date else None,
            'tags': [tag.name for tag in post.tags]
        }
        return response_data
    
    return {'error': 'Post not found'}, 404

def generate_static_post_page(post):
    """Generates a static HTML page for a given post."""
    try:
        with app.test_request_context():
            html = render_template("post.html", post=post)
            # Use configured static posts folder (persistent on Azure)
            static_posts_folder = app.config.get('STATIC_POSTS_FOLDER', 'static/posts')
            os.makedirs(static_posts_folder, exist_ok=True)
            filepath = os.path.join(static_posts_folder, f"{post.slug}.html")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html)
    except Exception as e:
        print(f"Error generating static page for {post.slug}: {e}")
        # Continue without failing the main operation

def process_keywords(keywords_string):
    """Process keywords string and return list of Keyword objects."""
    if not keywords_string or not keywords_string.strip():
        return []
    
    keyword_names = [k.strip().lower() for k in keywords_string.split(' | ') if k.strip()]
    keyword_objects = []
    
    for name in keyword_names:
        # Get or create keyword
        keyword = Keyword.query.filter_by(name=name).first()
        if keyword:
            # Increment usage count
            keyword.usage_count += 1
        else:
            # Create new keyword
            keyword = Keyword(name=name, usage_count=1)
            db.session.add(keyword)
        
        keyword_objects.append(keyword)
    
    return keyword_objects

def get_keywords_string(post):
    """Get keywords string from post's keyword relationships."""
    if not post.post_keywords:
        return ""
    return ", ".join([kw.name for kw in post.post_keywords])

def sync_keywords_from_post(post):
    """
    Synchronize keyword associations based on post.keywords field.
    Called when a post is created or updated.
    Updates usage counts accurately.
    """
    # Get current keyword associations
    current_keywords = set(post.post_keywords)
    
    if not post.keywords or not post.keywords.strip():
        # Clear all keyword associations and decrement counts
        for keyword in current_keywords:
            keyword.usage_count = max(0, keyword.usage_count - 1)
        post.post_keywords = []
        return
    
    # Parse keyword names (normalize to lowercase)
    keyword_names = [name.strip().lower() for name in post.keywords.split(',') 
                    if name.strip()]
    
    # Get or create keywords
    new_keywords = []
    for name in keyword_names:
        keyword = Keyword.query.filter(
            db.func.lower(Keyword.name) == name
        ).first()
        
        if not keyword:
            keyword = Keyword(name=name, usage_count=0)
            db.session.add(keyword)
            db.session.flush()
        
        new_keywords.append(keyword)
    
    # Calculate which keywords to add and remove
    new_keyword_set = set(new_keywords)
    keywords_to_add = new_keyword_set - current_keywords
    keywords_to_remove = current_keywords - new_keyword_set
    
    # Update associations and counts
    for keyword in keywords_to_remove:
        keyword.usage_count = max(0, keyword.usage_count - 1)
    
    for keyword in keywords_to_add:
        keyword.usage_count += 1
    
    # Update post associations
    post.post_keywords = new_keywords

def get_keywords_display(post):
    """
    Get comma-separated keyword string in uppercase for display.
    Uses the post_keywords relationship for accuracy.
    """
    if not post.post_keywords:
        return ''
    
    # Get keywords from associations and display in uppercase
    keyword_names = [k.display_name for k in post.post_keywords]
    return ', '.join(sorted(keyword_names))

def recalculate_all_keyword_counts():
    """
    Recalculate usage counts for all keywords.
    Useful for fixing any count discrepancies.
    """
    keywords = Keyword.query.all()
    
    for keyword in keywords:
        keyword.recalculate_usage_count()
    
    db.session.commit()
    
    return len(keywords)

def sync_protagonists_from_post(post):
    """
    Synchronize protagonist associations based on post.author field.
    Called when a post is created or updated.
    """
    if not post.author or not post.author.strip():
        # Clear all protagonist associations
        for protagonist in list(post.protagonists.all()):
            post.protagonists.remove(protagonist)
        return
    
    # Parse author names (support both ' | ' and '|' for backward compatibility)
    author_names = [name.strip() for name in post.author.split('|') if name.strip()]
    
    # Get or create protagonists
    protagonists = []
    for name in author_names:
        protagonist = Protagonist.query.filter(
            db.func.lower(Protagonist.name) == name.lower()
        ).first()
        
        if not protagonist:
            protagonist = Protagonist(name=name)
            db.session.add(protagonist)
            db.session.flush()
        
        protagonists.append(protagonist)
    
    # Update associations - remove old ones not in the list
    current_protagonists = list(post.protagonists.all())
    for current in current_protagonists:
        if current not in protagonists:
            post.protagonists.remove(current)
    
    # Add new associations
    for protagonist in protagonists:
        if protagonist not in current_protagonists:
            post.protagonists.append(protagonist)

def get_active_authors_display(post):
    """
    Get display string for post authors, filtering out inactive protagonists.
    Returns only active authors for display purposes.
    """
    if not post.author or not post.author.strip():
        return ''
    
    # Parse all author names from the field
    author_names = [name.strip() for name in post.author.split('|') if name.strip()]
    
    # Filter out inactive authors
    active_authors = []
    for name in author_names:
        protagonist = Protagonist.query.filter(
            db.func.lower(Protagonist.name) == name.lower()
        ).first()
        
        # Include if no protagonist exists (backward compatibility) or if protagonist is active
        if not protagonist or protagonist.is_active:
            active_authors.append(name)
    
    return ' | '.join(active_authors)

def regenerate_all_static_pages():
    """Regenerates all static pages when changes are made."""
    try:
        with app.app_context():
            print("🔄 Starting static page regeneration...")
            
            # Ensure directories exist
            os.makedirs('static/posts', exist_ok=True)
            os.makedirs('static/themes', exist_ok=True)
            
            # Regenerate all post pages
            all_posts = Post.query.all()
            print(f"📝 Regenerating {len(all_posts)} post pages...")
            for post in all_posts:
                try:
                    generate_static_post_page(post)
                except Exception as e:
                    print(f"  ✗ Error generating post page for {post.slug}: {e}")
            
            # Generate theme pages
            themes = Theme.query.filter_by(is_active=True, status='published').all()
            print(f"🎨 Regenerating {len(themes)} theme pages...")
            for theme in themes:
                try:
                    with app.test_request_context():
                        html = render_template("theme_posts.html", theme=theme, posts=theme.published_posts)
                    with open(f"static/themes/{theme.slug}.html", "w", encoding="utf-8") as f:
                        f.write(html)
                    print(f"  ✓ Generated theme page: {theme.slug}")
                except Exception as e:
                    print(f"  ✗ Error generating theme page for {theme.slug}: {e}")
            
            # Generate explore themes page
            try:
                with app.test_request_context():
                    html = render_template("explore_themes.html", themes=themes)
                with open(f"static/explore-themes.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"  ✓ Generated explore themes page")
            except Exception as e:
                print(f"  ✗ Error generating explore themes page: {e}")
                
            print("✅ All static pages regenerated successfully!")
            return True
    except Exception as e:
        print(f"❌ Error regenerating static pages: {e}")
        import traceback
        traceback.print_exc()
        return False

# Database seeding command
@app.cli.command("seed-db")
def seed_database():
    """Seeds the database with sample posts."""
    # Clear existing data
    Picture.query.delete()
    Post.query.delete()
    
    # Create sample posts
    sample_posts = [
        {
            'title': 'Finding My Voice Through Art',
            'author': 'Zhang Xiaoyu',
            'abstract': 'A glimpse into student art studios blending traditional ink painting with digital media techniques.',
            'text_content': '<p>The collision of tradition and modernity in ancient alleys, where I discovered the artistic language of our time. Every blue brick and red door tells a story of historical depth and modern vitality.</p><p>Walking through these narrow passages, I found myself sketching the interplay between old architecture and contemporary life.</p>',
            'gallery_template': 'waterfall',
            'is_featured': True,
            'featured_template': 'T1'
        },
        {
            'title': 'Beijing Through My Lens',
            'author': 'Li Mingxuan',
            'abstract': 'Short film by a Beijing high schooler about friendship and city life in modern China.',
            'youtube_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'is_featured': False
        },
        {
            'title': 'Digital Slang Evolution',
            'author': 'Wang Shihan',
            'abstract': 'Essays on the evolving slang and memes shaping Gen Z digital expression in China.',
            'text_content': '<p>Language evolves at the speed of light in the digital age. From "yyds" to "emo", each expression carries the weight of generational identity.</p><p>Through analyzing thousands of social media posts, I discovered patterns that reveal how young Chinese people are reshaping language itself.</p>',
            'is_featured': False
        },
        {
            'title': 'Modern Calligraphy',
            'author': 'Chen Yutong',
            'abstract': 'Interview with a young calligrapher exploring modern interpretations of traditional Chinese writing.',
            'text_content': '<p>Every stroke tells a story. In my work, I blend thousand-year-old techniques with contemporary themes, creating pieces that speak to both heritage and innovation.</p>',
            'gallery_template': 'slideshow',
            'is_featured': False
        },
        {
            'title': 'Street Food Chronicles',
            'author': 'Zhao Siqi',
            'abstract': 'Photo series capturing the vibrant energy and cultural significance of street food across Chinese cities.',
            'gallery_template': 'waterfall',
            'is_featured': False
        }
    ]
    
    for post_data in sample_posts:
        post = Post(**post_data)
        db.session.add(post)
        db.session.flush()  # Get the post ID
        
        # Add sample pictures for gallery posts
        if post_data.get('gallery_template'):
            # In a real app, these would be real uploaded files.
            # For seeding, we can create placeholder records.
            for i in range(3, 7):  # 3-6 images per gallery
                filename = f'sample_{post.id}_{i}.jpg'
                picture = Picture(
                    filename=filename,
                    display_order=i-3,
                    post_id=post.id
                )
                db.session.add(picture)
                
                # Set first image as poster
                if i == 3:
                    post.poster_filename = filename
    
    db.session.commit()

    # Manually push an application context to use url_for
    with app.app_context():
        # Generate static pages for all new posts
        all_posts = Post.query.all()
        for post in all_posts:
            generate_static_post_page(post)

    print('Database seeded with sample posts and static pages generated!')

@app.cli.command("seed-tags")
def seed_tags():
    """Seeds the database with predefined tags."""
    tags_data = [
        # Media types
        {'name': 'article', 'category': 'media_type', 'color': '#3A7467'},
        {'name': 'gallery', 'category': 'media_type', 'color': '#7BAF9E'},
        {'name': 'video', 'category': 'media_type', 'color': '#C94C4C'},
        # Display types
        {'name': 'waterfall', 'category': 'display_type', 'color': '#3A7467'},  # Greenest
        {'name': 'slideshow', 'category': 'display_type', 'color': '#C94C4C'},  # Reddest
        # Content types
        {'name': 'art', 'category': 'content_type', 'color': '#3A7467'},
        {'name': 'culture', 'category': 'content_type', 'color': '#7BAF9E'},
        {'name': 'photography', 'category': 'content_type', 'color': '#C94C4C'},
        {'name': 'sports', 'category': 'content_type', 'color': '#4E8C76'},
    ]
    
    for tag_data in tags_data:
        if not Tag.query.filter_by(name=tag_data['name']).first():
            tag = Tag(**tag_data)
            db.session.add(tag)
    db.session.commit()
    print('Database seeded with tags!')

@app.cli.command("seed-themes")
def seed_themes():
    """Seeds the database with predefined themes."""
    themes_data = [
        {'name': 'Art & Design', 'description': 'Visual arts, digital design, traditional crafts, and creative expressions', 'icon': '🎨', 'color': '#3A7467'},
        {'name': 'Chinese Culture', 'description': 'Traditional arts, philosophy, language, and cultural exploration', 'icon': '🐉', 'color': '#7BAF9E'},
        {'name': 'Photography', 'description': 'Street photography, portraits, landscapes, and visual storytelling', 'icon': '📸', 'color': '#C94C4C'},
        {'name': 'Sports & Wellness', 'description': 'Athletic achievements, sports culture, and physical wellness journeys', 'icon': '⚽', 'color': '#4E8C76'},
        {'name': 'Music & Performance', 'description': 'Musical compositions, performances, and artistic expressions', 'icon': '🎵', 'color': '#8B5A3C'},
        {'name': 'Writing & Literature', 'description': 'Stories, essays, poetry, and written expressions', 'icon': '📝', 'color': '#6B46C1'},
        {'name': 'Innovation & Technology', 'description': 'Tech innovations, digital creativity, and modern solutions', 'icon': '💡', 'color': '#4A90E2'},
        {'name': 'Food & Lifestyle', 'description': 'Culinary adventures, lifestyle stories, and cultural celebrations', 'icon': '🍜', 'color': '#FF8C42'},
    ]
    
    for theme_data in themes_data:
        if not Theme.query.filter_by(name=theme_data['name']).first():
            theme = Theme(**theme_data)
            db.session.add(theme)
    db.session.commit()
    print('Database seeded with themes!')

@app.cli.command("check-db")
def check_db():
    """Checks the database for posts and themes."""
    posts = Post.query.all()
    themes = Theme.query.all()
    print(f'Found {len(posts)} posts and {len(themes)} themes in the database.')

@app.cli.command("regenerate-static")
def regenerate_static():
    """Regenerates all static pages."""
    regenerate_all_static_pages()

@app.cli.command("test-themes")
def test_themes():
    """Test theme system by showing themes and their posts."""
    themes = Theme.query.all()
    print(f"\n=== Theme System Test ===")
    print(f"Found {len(themes)} themes:")
    
    for theme in themes:
        status = "Active" if theme.is_active else "Inactive"
        print(f"\n{theme.icon} {theme.name} ({status})")
        print(f"   Color: {theme.color}")
        print(f"   Description: {theme.description}")
        print(f"   Posts: {len(theme.posts)}")
        
        for post in theme.posts:
            print(f"     - {post.title} by {post.author}")
    
    unthemed_posts = Post.query.filter_by(theme_id=None).all()
    if unthemed_posts:
        print(f"\n📝 Unthemed Posts ({len(unthemed_posts)}):")
        for post in unthemed_posts:
            print(f"     - {post.title} by {post.author}")
    
    print(f"\n=== End Test ===\n")

@app.cli.command("migrate-protagonists")
def migrate_protagonists_command():
    """Migrate existing post authors to protagonist profiles."""
    posts = Post.query.all()
    protagonist_count = 0
    association_count = 0
    
    print(f"\n📊 Found {len(posts)} posts to process")
    
    for post in posts:
        if post.author and post.author.strip():
            # Parse author names
            author_names = [name.strip() for name in post.author.split('|') if name.strip()]
            
            for name in author_names:
                # Get or create protagonist
                protagonist = Protagonist.query.filter(
                    db.func.lower(Protagonist.name) == name.lower()
                ).first()
                
                if not protagonist:
                    protagonist = Protagonist(name=name)
                    db.session.add(protagonist)
                    db.session.flush()
                    protagonist_count += 1
                    print(f"  ✨ Created protagonist: {name}")
                
                # Create association if it doesn't exist
                if post not in protagonist.posts:
                    protagonist.posts.append(post)
                    association_count += 1
    
    db.session.commit()
    print(f"\n✅ Migration complete!")
    print(f"   - Created {protagonist_count} new protagonists")
    print(f"   - Created {association_count} post-protagonist associations")

# Create a new post
@app.route('/admin/new', methods=['GET', 'POST'])
def new_post():
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    form = PostForm()
    form.tags.choices = [(t.id, t.name) for t in Tag.query.order_by('name')]
    form.theme_id.choices = [(0, 'No Theme')] + [(t.id, t.name) for t in Theme.query.filter_by(is_active=True).order_by('name')]
    form.series_id.choices = [(0, 'No Series')] + [(s.id, s.title) for s in Series.query.filter_by(is_active=True).order_by('title')]
    
    # Initialize data for new post (prevent None errors)
    if request.method == 'GET':
        form.tags.data = []
    
    if form.validate_on_submit():
        print("✅ Form validation passed")
        try:
            # If setting as featured, unfeature all others
            if form.is_featured.data:
                Post.query.filter_by(is_featured=True).update({'is_featured': False})
                db.session.commit()
        
            # Create publication date from form inputs
            try:
                pub_date = datetime(form.pub_year.data, form.pub_month.data, form.pub_day.data)
            except ValueError:
                pub_date = datetime.utcnow()  # Fallback to current date if invalid
        
            # Generate slug from form or title
            if form.slug.data and form.slug.data.strip():
                slug = slugify(form.slug.data)
            else:
                slug = slugify(form.title.data)
            
            # Create a new Post object from the form data
            post = Post(
                title=form.title.data,
                slug=slug,
                author=form.author.data,
                editors=form.editors.data if form.editors.data else None,
                translated_by=form.translated_by.data if form.translated_by.data else None,
                keywords=form.keywords.data if form.keywords.data else None,
                abstract=form.abstract.data if form.abstract.data else '',
                text_content=form.text_content.data if form.text_content.data else None,
                youtube_url=form.youtube_url.data if form.youtube_url.data else None,
                gallery_template=form.gallery_template.data if form.gallery_template.data else None,
                is_featured=form.is_featured.data,
                use_youtube_poster=form.use_youtube_poster.data,
                featured_template=form.featured_template.data if form.featured_template.data else None,
                publication_date=pub_date,
                theme_id=form.theme_id.data if form.theme_id.data != 0 else None,
                series_id=form.series_id.data if form.series_id.data != 0 else None,
                series_order=form.series_order.data if form.series_order.data else None,
                status='pending' if session.get('user_role') == 'visitor' else 'published'
            )
            
            if session.get('user_role') == 'visitor':
                flash('Your post has been submitted for admin approval.', 'info')
            else:
                flash('Post successfully published!')
            # Add tags
            for tag_id in form.tags.data:
                tag = Tag.query.get(tag_id)
                if tag:
                    post.tags.append(tag)

            # Add the new post to the database session
            db.session.add(post)
            db.session.flush()  # Get the post ID for picture relationships
            
            # Sync keyword associations from keywords field
            sync_keywords_from_post(post)

            # Handle dedicated poster upload
            if form.poster_upload.data:
                file = form.poster_upload.data
                filename = secure_filename(file.filename)
                filename = f"poster_{post.id}_{datetime.now().timestamp()}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                post.poster_filename = filename
            
            # Handle uploaded images
            uploaded_files = request.files.getlist("images")
            poster_image_index = request.form.get('poster_image_index')
            
            if uploaded_files:
                newly_created_pictures = []
                for i, file in enumerate(uploaded_files):
                    if file:
                        filename = secure_filename(file.filename)
                        # To avoid filename conflicts, prepend post_id and a timestamp
                        filename = f"{post.id}_{datetime.now().timestamp()}_{filename}"
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                        picture = Picture(
                            filename=filename,
                            display_order=i,
                            post_id=post.id
                        )
                        db.session.add(picture)
                        db.session.flush()
                        newly_created_pictures.append(picture)

                # Set as poster image if selected
                if poster_image_index and newly_created_pictures:
                    try:
                        index = int(poster_image_index)
                        if 0 <= index < len(newly_created_pictures):
                            post.poster_filename = newly_created_pictures[index].filename
                    except (ValueError, IndexError):
                        pass # Ignore if index is invalid
        
            # Sync protagonist associations from author field
            sync_protagonists_from_post(post)
            
            # Commit all changes to the database
            db.session.commit()

            # Create PendingUpdate for moderation if visitor
            if session.get('user_role') == 'visitor':
                update = PendingUpdate(
                    category='Post Update',
                    action='create',
                    item_id=post.id,
                    item_name=post.title,
                    user_id=session.get('user_id'),
                    data=json.dumps({'post_id': post.id}) # Simplest case for now as item is in DB with status=pending
                )
                db.session.add(update)
                db.session.commit()

            generate_static_post_page(post) # Generate static page
            regenerate_all_static_pages() # Regenerate all static pages
            flash('Your post has been created successfully!')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating post: {str(e)}')
            return render_template('admin/form.html', form=form, legend='New Post')
    else:
        # Form validation failed
        if request.method == 'POST':
            print("❌ Form validation failed")
            print(f"Form errors: {form.errors}")
            print(f"Form data - Title: {form.title.data}, Author: {form.author.data}")
            print(f"Form data - Text: {bool(form.text_content.data)}, YouTube: {bool(form.youtube_url.data)}, Gallery: {bool(form.gallery_template.data)}")
            # Flash all validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{field}: {error}', 'error')
    
    return render_template('admin/form.html', form=form, legend='New Post')

# Create a new initiative post
@app.route('/admin/new-initiative', methods=['GET', 'POST'])
def new_initiative_post():
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    form = InitiativePostForm()
    # Only show initiative themes
    form.theme_id.choices = [(t.id, t.name) for t in Theme.query.filter_by(is_active=True, is_initiative=True).order_by('name')]
    form.series_id.choices = [(s.id, s.title) for s in Series.query.filter_by(is_active=True).order_by('title')]
    
    if form.validate_on_submit():
        print("✅ Initiative form validation passed")
        try:
            # If setting as featured, unfeature all others
            if form.is_featured.data:
                Post.query.filter_by(is_featured=True).update({'is_featured': False})
                db.session.commit()
        
            # Create publication date from form inputs
            try:
                pub_date = datetime(form.pub_year.data, form.pub_month.data, form.pub_day.data)
            except ValueError:
                pub_date = datetime.utcnow()
        
            # Create a new Initiative Post object
            post = Post(
                title=form.title.data,
                author='Initiative',  # Default author for initiatives
                abstract=form.abstract.data,
                text_content=form.text_content.data if form.text_content.data else None,
                youtube_url=form.youtube_url.data if form.youtube_url.data else None,
                use_youtube_poster=form.use_youtube_poster.data,
                gallery_template=form.gallery_template.data if form.gallery_template.data else None,
                is_featured=form.is_featured.data,
                featured_template=form.featured_template.data if form.featured_template.data else None,
                publication_date=pub_date,
                theme_id=form.theme_id.data,
                series_id=form.series_id.data,
                series_order=1,  # Always first in series
                is_initiative=True,
                frame_color=form.frame_color.data if form.frame_color.data else '#2563eb'
            )
            
            # Generate slug from title
            post.slug = slugify(post.title)
            
            # Handle poster upload
            if form.poster_upload.data:
                poster_file = form.poster_upload.data
                if poster_file.filename:
                    filename = secure_filename(poster_file.filename)
                    timestamp = str(int(datetime.utcnow().timestamp()))
                    name, ext = filename.rsplit('.', 1)
                    filename = f"poster_{timestamp}_{name}.{ext}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    poster_file.save(filepath)
                    post.poster_filename = filename
            
            db.session.add(post)
            
            # Sync protagonist associations from author field
            sync_protagonists_from_post(post)
            
            db.session.commit()
            
            generate_static_post_page(post)
            regenerate_all_static_pages()
            flash('Your initiative post has been created successfully!')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating initiative post: {str(e)}')
            return render_template('admin/initiative_form.html', form=form, legend='New Initiative Post')
    else:
        if request.method == 'POST':
            print("❌ Initiative form validation failed")
            print(f"Form errors: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{field}: {error}', 'error')
    
    return render_template('admin/initiative_form.html', form=form, legend='New Initiative Post')

# Edit an existing post
@app.route('/admin/edit/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    # Get post from database
    post = Post.query.get_or_404(post_id)
    form = PostForm()
    form.tags.choices = [(t.id, t.name) for t in Tag.query.order_by('name')]
    form.theme_id.choices = [(0, 'No Theme')] + [(t.id, t.name) for t in Theme.query.filter_by(is_active=True).order_by('name')]
    form.series_id.choices = [(0, 'No Series')] + [(s.id, s.title) for s in Series.query.filter_by(is_active=True).order_by('title')]
    
    if form.validate_on_submit():
        try:
            # Handle featured status - unfeature others if this is being set as featured
            if form.is_featured.data and not post.is_featured:
                Post.query.filter_by(is_featured=True).update({'is_featured': False})
                db.session.commit()
            
            # Update publication date from form inputs
            try:
                pub_date = datetime(form.pub_year.data, form.pub_month.data, form.pub_day.data)
            except ValueError:
                pub_date = post.publication_date  # Keep existing date if invalid
            
            # Update post attributes
            post.title = form.title.data
            # Update slug - auto-generate from title if not provided
            if form.slug.data and form.slug.data.strip():
                post.slug = slugify(form.slug.data)
            else:
                post.slug = slugify(form.title.data)
            post.author = form.author.data
            post.editors = form.editors.data if form.editors.data else None
            post.translated_by = form.translated_by.data if form.translated_by.data else None
            post.keywords = form.keywords.data if form.keywords.data else None
            post.abstract = form.abstract.data
            post.text_content = form.text_content.data if form.text_content.data else None
            post.youtube_url = form.youtube_url.data if form.youtube_url.data else None
            post.gallery_template = form.gallery_template.data if form.gallery_template.data else None
            post.is_featured = form.is_featured.data
            post.use_youtube_poster = form.use_youtube_poster.data
            post.featured_template = form.featured_template.data if form.featured_template.data else None
            post.publication_date = pub_date
            post.theme_id = form.theme_id.data if form.theme_id.data != 0 else None
            post.series_id = form.series_id.data if form.series_id.data != 0 else None
            post.series_order = form.series_order.data if form.series_order.data else None
            
            # If visitor, set to pending per requirement and create update record
            if session.get('user_role') == 'visitor':
                post.status = 'pending'
                update = PendingUpdate(
                    category='Post Update',
                    action='update',
                    item_id=post.id,
                    item_name=post.title,
                    user_id=session.get('user_id'),
                    data=json.dumps({'post_id': post.id})
                )
                db.session.add(update)
                flash('Your edits have been submitted for admin approval.', 'info')
            else:
                flash('Post successfully updated!')
            
            # Update tags
            post.tags.clear()
            for tag_id in form.tags.data:
                tag = Tag.query.get(tag_id)
                if tag:
                    post.tags.append(tag)
            
            # Sync keyword associations from keywords field
            sync_keywords_from_post(post)

            # Handle existing poster selection
            existing_poster = request.form.get('existing_poster_filename')
            if existing_poster:
                post.poster_filename = existing_poster

            # Handle dedicated poster upload
            if form.poster_upload.data:
                file = form.poster_upload.data
                filename = secure_filename(file.filename)
                # To avoid filename conflicts, prepend post_id and a timestamp
                filename = f"poster_{post.id}_{datetime.now().timestamp()}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                post.poster_filename = filename

            # Handle image deletions
            delete_images = request.form.getlist('delete_images')
            for picture_id in delete_images:
                picture = Picture.query.get(picture_id)
                if picture and picture.post_id == post.id:
                    # Delete file from filesystem
                    try:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], picture.filename))
                    except OSError:
                        pass  # File might not exist
                    # Delete from database
                    db.session.delete(picture)

            # Handle new image uploads
            uploaded_files = request.files.getlist("images")
            poster_image_index = request.form.get('poster_image_index')
            newly_created_pictures = []

            if uploaded_files:
                # Find the current max display_order
                max_order = db.session.query(db.func.max(Picture.display_order)).filter_by(post_id=post.id).scalar() or -1
                valid_file_count = 0
                for file in uploaded_files:
                    # Skip empty files
                    if file.filename == '' or not file.filename:
                        continue
                    
                    filename = secure_filename(file.filename)
                    # Skip if secure_filename returns empty (invalid filename)
                    if not filename:
                        continue
                        
                    filename = f"{post.id}_{datetime.now().timestamp()}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    picture = Picture(
                        filename=filename,
                        display_order=max_order + 1 + valid_file_count,
                        post_id=post.id
                    )
                    db.session.add(picture)
                    db.session.flush() # Flush to get the picture ID
                    newly_created_pictures.append(picture)
                    valid_file_count += 1

            # Set as poster image if selected from the new uploads
            if poster_image_index and newly_created_pictures:
                try:
                    index = int(poster_image_index)
                    if 0 <= index < len(newly_created_pictures):
                        post.poster_filename = newly_created_pictures[index].filename
                except (ValueError, IndexError):
                    pass # Ignore if index is invalid
            
            # Sync protagonist associations from author field
            sync_protagonists_from_post(post)
            
            # Commit changes to database
            db.session.commit()
            generate_static_post_page(post) # Re-generate static page
            regenerate_all_static_pages() # Regenerate all static pages
            flash('Your post has been updated successfully!')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating post: {str(e)}')
            return render_template('admin/form.html', form=form, legend='Edit Post', post=post)
    
    elif request.method == 'GET':
        # Pre-populate form with existing data
        form.title.data = post.title
        form.slug.data = post.slug
        form.author.data = post.author
        form.editors.data = post.editors
        form.translated_by.data = post.translated_by
        form.keywords.data = get_keywords_string(post)
        form.abstract.data = post.abstract
        form.text_content.data = post.text_content
        form.youtube_url.data = post.youtube_url
        form.use_youtube_poster.data = post.use_youtube_poster
        form.gallery_template.data = post.gallery_template
        form.is_featured.data = post.is_featured
        form.featured_template.data = post.featured_template
        form.tags.data = [tag.id for tag in post.tags]
        form.theme_id.data = post.theme_id if post.theme_id else 0
        form.series_id.data = post.series_id if post.series_id else 0
        form.series_order.data = post.series_order
        # Pre-populate publication date
        if post.publication_date:
            form.pub_year.data = post.publication_date.year
            form.pub_month.data = post.publication_date.month
            form.pub_day.data = post.publication_date.day
        
    return render_template('admin/form.html', form=form, legend='Edit Post', post=post)

# Delete a post
@app.route('/admin/post/<int:post_id>/approve', methods=['POST'])
def approve_post_route(post_id):
    """Approve and publish a pending post."""
    if 'admin_logged_in' not in session or session.get('user_role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        post = Post.query.get_or_404(post_id)
        post.status = 'published'
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/delete/<int:post_id>', methods=['POST', 'GET'])
def delete_post(post_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    # Get post from database
    post = Post.query.get_or_404(post_id)
    post_title = post.title  # Store title before deletion
    post_slug = post.slug
    
    try:
        # Delete static file if it exists (use configured path)
        static_posts_folder = app.config.get('STATIC_POSTS_FOLDER', 'static/posts')
        static_path = os.path.join(static_posts_folder, f"{post_slug}.html")
        if os.path.exists(static_path):
            os.remove(static_path)

        # Delete all associated pictures (cascade should handle this, but explicit is better)
        Picture.query.filter_by(post_id=post_id).delete()
        
        # Delete the post itself
        db.session.delete(post)
        db.session.commit()
        
        # Regenerate all static pages to update theme post counts
        regenerate_all_static_pages()
        
        flash(f'Post "{post_title}" and all associated images have been permanently deleted!')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting post: {str(e)}')
    
    return redirect(url_for('admin_dashboard'))

# --- Theme Management Routes ---

@app.route('/admin/themes')
def admin_themes():
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    themes = Theme.query.order_by(Theme.name).all()
    return render_template('admin/theme_list.html', themes=themes)

@app.route('/admin/theme/new', methods=['GET', 'POST'])
def new_theme():
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    form = ThemeForm()
    
    if form.validate_on_submit():
        try:
            # Handle icon - either emoji/text or file upload
            icon_value = form.icon.data or '📝'
            icon_type = 'emoji'
            
            # Check if file was uploaded
            if form.icon_file.data and form.icon_file.data.filename:
                uploaded_filename = handle_theme_icon_upload(form.icon_file.data)
                if uploaded_filename:
                    icon_value = uploaded_filename
                    icon_type = 'file'
            
            # Generate slug if not provided
            slug = form.slug.data or slugify(form.name.data)
            
            theme = Theme(
                name=form.name.data,
                slug=slug,
                description=form.description.data,
                icon=icon_value,
                icon_type=icon_type,
                color=form.color.data,
                is_active=form.is_active.data,
                is_initiative=form.is_initiative.data
            )
            
            # Handle background image upload
            if form.background_image.data and form.background_image.data.filename:
                bg_file = form.background_image.data
                bg_filename = secure_filename(bg_file.filename)
                timestamp = str(int(datetime.utcnow().timestamp()))
                name, ext = bg_filename.rsplit('.', 1) if '.' in bg_filename else (bg_filename, 'jpg')
                bg_filename = f"theme_bg_{timestamp}_{name}.{ext}"
                bg_filepath = os.path.join(app.config['UPLOAD_FOLDER'], bg_filename)
                os.makedirs(os.path.dirname(bg_filepath), exist_ok=True)
                bg_file.save(bg_filepath)
                theme.background_image = bg_filename
            
            # Handle card image upload
            if form.card_image.data and form.card_image.data.filename:
                card_file = form.card_image.data
                card_filename = secure_filename(card_file.filename)
                timestamp = str(int(datetime.utcnow().timestamp()))
                name, ext = card_filename.rsplit('.', 1) if '.' in card_filename else (card_filename, 'jpg')
                card_filename = f"theme_card_{timestamp}_{name}.{ext}"
                card_filepath = os.path.join(app.config['UPLOAD_FOLDER'], card_filename)
                os.makedirs(os.path.dirname(card_filepath), exist_ok=True)
                card_file.save(card_filepath)
                theme.card_image = card_filename
            
            if session.get('user_role') == 'visitor':
                theme.status = 'pending'
            
            db.session.add(theme)
            db.session.commit()

            if session.get('user_role') == 'visitor':
                update = PendingUpdate(
                    category='Theme Update',
                    action='create',
                    item_id=theme.id,
                    item_name=theme.name,
                    user_id=session.get('user_id'),
                    data=json.dumps({'theme_id': theme.id})
                )
                db.session.add(update)
                db.session.commit()
                flash('Your theme has been submitted for admin approval.', 'info')
            else:
                regenerate_all_static_pages()
                flash('Theme created successfully!')
            
            return redirect(url_for('admin_themes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating theme: {str(e)}')
    
    return render_template('admin/theme_form.html', form=form, legend='New Theme')

@app.route('/admin/theme/<int:theme_id>/edit', methods=['GET', 'POST'])
def edit_theme(theme_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    theme = Theme.query.get_or_404(theme_id)
    form = ThemeForm()
    
    if form.validate_on_submit():
        try:
            theme.name = form.name.data
            theme.slug = form.slug.data or slugify(form.name.data)
            theme.description = form.description.data
            theme.color = form.color.data
            theme.is_active = form.is_active.data
            theme.is_initiative = form.is_initiative.data
            
            # Handle icon update
            if form.icon_file.data and form.icon_file.data.filename:
                # New file uploaded
                uploaded_filename = handle_theme_icon_upload(form.icon_file.data)
                if uploaded_filename:
                    # Delete old file if it exists
                    if hasattr(theme, 'icon_type') and theme.icon_type == 'file' and theme.icon:
                        old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], theme.icon)
                        if os.path.exists(old_filepath):
                            os.remove(old_filepath)
                    
                    theme.icon = uploaded_filename
                    theme.icon_type = 'file'
            elif form.icon.data:
                # Emoji/text icon provided
                if hasattr(theme, 'icon_type') and theme.icon_type == 'file' and theme.icon:
                    # Delete old file if switching from file to emoji
                    old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], theme.icon)
                    if os.path.exists(old_filepath):
                        os.remove(old_filepath)
                
                theme.icon = form.icon.data
                theme.icon_type = 'emoji'
            
            # Handle background image update
            if form.background_image.data and form.background_image.data.filename:
                bg_file = form.background_image.data
                bg_filename = secure_filename(bg_file.filename)
                timestamp = str(int(datetime.utcnow().timestamp()))
                name, ext = bg_filename.rsplit('.', 1) if '.' in bg_filename else (bg_filename, 'jpg')
                bg_filename = f"theme_bg_{timestamp}_{name}.{ext}"
                bg_filepath = os.path.join(app.config['UPLOAD_FOLDER'], bg_filename)
                os.makedirs(os.path.dirname(bg_filepath), exist_ok=True)
                
                # Delete old file
                if theme.background_image:
                    old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], theme.background_image)
                    if os.path.exists(old_filepath):
                        os.remove(old_filepath)
                        
                bg_file.save(bg_filepath)
                theme.background_image = bg_filename
            
            # Handle card image update
            if form.card_image.data and form.card_image.data.filename:
                card_file = form.card_image.data
                card_filename = secure_filename(card_file.filename)
                timestamp = str(int(datetime.utcnow().timestamp()))
                name, ext = card_filename.rsplit('.', 1) if '.' in card_filename else (card_filename, 'jpg')
                card_filename = f"theme_card_{timestamp}_{name}.{ext}"
                card_filepath = os.path.join(app.config['UPLOAD_FOLDER'], card_filename)
                os.makedirs(os.path.dirname(card_filepath), exist_ok=True)
                
                # Delete old file
                if theme.card_image:
                    old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], theme.card_image)
                    if os.path.exists(old_filepath):
                        os.remove(old_filepath)
                        
                card_file.save(card_filepath)
                theme.card_image = card_filename
            
            if session.get('user_role') == 'visitor':
                theme.status = 'pending'
                update = PendingUpdate(
                    category='Theme Update',
                    action='update',
                    item_id=theme.id,
                    item_name=theme.name,
                    user_id=session.get('user_id'),
                    data=json.dumps({'theme_id': theme.id})
                )
                db.session.add(update)
                flash('Your edits have been submitted for admin approval.', 'info')
            else:
                regenerate_all_static_pages()
                flash('Theme updated successfully!')
            
            db.session.commit()
            return redirect(url_for('admin_themes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating theme: {str(e)}')
    
    elif request.method == 'GET':
        form.name.data = theme.name
        form.slug.data = getattr(theme, 'slug', slugify(theme.name))
        form.description.data = theme.description
        # Handle missing icon_type for existing themes
        if not hasattr(theme, 'icon_type') or theme.icon_type == 'emoji':
            form.icon.data = theme.icon
        form.color.data = theme.color
        form.is_active.data = theme.is_active
        form.is_initiative.data = getattr(theme, 'is_initiative', False)
    
    return render_template('admin/theme_form.html', form=form, legend='Edit Theme', theme=theme)

@app.route('/admin/theme/<int:theme_id>/toggle', methods=['POST'])
def toggle_theme_status(theme_id):
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    theme = Theme.query.get_or_404(theme_id)
    data = request.get_json()
    
    theme.is_active = data.get('is_active', False)
    db.session.commit()
    regenerate_all_static_pages()
    
    return {'success': True}

@app.route('/admin/theme/<int:theme_id>/delete', methods=['POST'])
def delete_theme(theme_id):
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    theme = Theme.query.get_or_404(theme_id)
    
    # Check if theme has posts
    if theme.posts:
        return {'error': 'Cannot delete theme with posts'}, 400
    
    try:
        db.session.delete(theme)
        db.session.commit()
        regenerate_all_static_pages()
        return {'success': True}
    except Exception as e:
        db.session.rollback()
        return {'error': str(e)}, 500

# --- Series Management Routes ---

@app.route('/admin/series')
def admin_series():
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    series = Series.query.order_by(Series.title).all()
    return render_template('admin/series_list.html', series=series)

@app.route('/admin/series/new', methods=['GET', 'POST'])
def new_series():
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    form = SeriesForm()
    if form.validate_on_submit():
        try:
            series = Series(
                title=form.title.data,
                description=form.description.data,
                is_active=form.is_active.data
            )
            if session.get('user_role') == 'visitor':
                series.status = 'pending'
            
            db.session.add(series)
            db.session.commit()

            if session.get('user_role') == 'visitor':
                update = PendingUpdate(
                    category='Series Update',
                    action='create',
                    item_id=series.id,
                    item_name=series.title,
                    user_id=session.get('user_id'),
                    data=json.dumps({'series_id': series.id})
                )
                db.session.add(update)
                db.session.commit()
                flash('Your series concept has been submitted for admin approval.', 'info')
            else:
                regenerate_all_static_pages()
                flash('Series created successfully!')
            
            return redirect(url_for('admin_series'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating series: {str(e)}')
    
    return render_template('admin/series_form.html', form=form, legend='New Series')

@app.route('/admin/series/<int:series_id>/edit', methods=['GET', 'POST'])
def edit_series(series_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    series = Series.query.get_or_404(series_id)
    form = SeriesForm(obj=series, series_id=series_id)
    
    if form.validate_on_submit():
        try:
            series.title = form.title.data
            series.description = form.description.data
            series.is_active = form.is_active.data
            
            if session.get('user_role') == 'visitor':
                series.status = 'pending'
                update = PendingUpdate(
                    category='Series Update',
                    action='update',
                    item_id=series.id,
                    item_name=series.title,
                    user_id=session.get('user_id'),
                    data=json.dumps({'series_id': series.id})
                )
                db.session.add(update)
                flash('Your series edits have been submitted for admin approval.', 'info')
            else:
                # Regenerate static pages for all posts in this series
                for post in series.posts:
                    generate_static_post_page(post)
                regenerate_all_static_pages()
                flash('Series updated successfully!')
            
            db.session.commit()
            return redirect(url_for('admin_series'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating series: {str(e)}')
    
    elif request.method == 'GET':
        form.title.data = series.title
        form.description.data = series.description
        form.is_active.data = series.is_active
    
    return render_template('admin/series_form.html', form=form, legend='Edit Series', series=series)

@app.route('/admin/series/<int:series_id>/toggle', methods=['POST'])
def toggle_series_status(series_id):
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    series = Series.query.get_or_404(series_id)
    data = request.get_json()
    series.is_active = data.get('is_active', False)
    db.session.commit()
    regenerate_all_static_pages()
    
    return {'success': True}

@app.route('/admin/series/<int:series_id>/delete', methods=['POST'])
def delete_series(series_id):
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    series = Series.query.get_or_404(series_id)
    try:
        # Remove series association from posts
        for post in series.posts:
            post.series_id = None
            post.series_order = None
        
        db.session.delete(series)
        db.session.commit()
        regenerate_all_static_pages()
        return {'success': True}
    except Exception as e:
        db.session.rollback()
        return {'error': str(e)}, 500

@app.route('/api/posts/available-for-series')
def get_available_posts_for_series():
    """Get posts that are not part of any series or part of a specific series."""
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    series_id = request.args.get('series_id', type=int)
    search = request.args.get('search', '').strip()
    
    # Get posts that are either not in any series or in the specified series
    query = Post.query
    if series_id:
        query = query.filter((Post.series_id == None) | (Post.series_id == series_id))
    else:
        query = query.filter(Post.series_id == None)
    
    if search:
        query = query.filter(Post.title.contains(search))
    
    posts = query.order_by(Post.publication_date.desc()).limit(20).all()
    
    return {
        'posts': [{
            'id': post.id,
            'title': post.title,
            'author': post.author,
            'publication_date': post.publication_date.strftime('%b %d, %Y') if post.publication_date else 'N/A',
            'series_order': post.series_order,
            'in_series': post.series_id == series_id if series_id else False
        } for post in posts]
    }

@app.route('/api/series/<int:series_id>/posts-list', methods=['GET'])
def get_series_posts_list(series_id):
    """Get list of posts in a series for preview."""
    series = Series.query.get_or_404(series_id)
    
    posts = Post.query.filter_by(series_id=series_id).order_by(Post.series_order, Post.publication_date.desc()).all()
    
    posts_data = [{
        'id': post.id,
        'title': post.title,
        'author': post.author,
        'series_order': post.series_order or 0,
        'publication_date': post.publication_date.strftime('%b %d, %Y') if post.publication_date else 'N/A'
    } for post in posts]
    
    return {'posts': posts_data}

@app.route('/api/series/<int:series_id>/posts', methods=['POST'])
def update_series_posts(series_id):
    """Update posts in a series."""
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    series = Series.query.get_or_404(series_id)
    data = request.get_json()
    
    try:
        # Track all affected posts for regeneration
        affected_posts = set()
        
        # Get the posts to add/update
        post_updates = data.get('posts', [])
        
        for post_data in post_updates:
            post_id = post_data.get('id')
            series_order = post_data.get('series_order')
            action = post_data.get('action')  # 'add' or 'remove'
            
            post = Post.query.get(post_id)
            if not post:
                continue
            
            affected_posts.add(post)
                
            if action == 'add':
                post.series_id = series_id
                post.series_order = series_order
            elif action == 'remove':
                post.series_id = None
                post.series_order = None
        
        db.session.commit()
        
        # Regenerate static pages for all affected posts (to update TOC)
        for post in affected_posts:
            generate_static_post_page(post)
        
        # Also regenerate all posts currently in the series (to update their TOC)
        for post in series.posts:
            if post not in affected_posts:
                generate_static_post_page(post)
        
        regenerate_all_static_pages()
        
        # Return updated posts list for immediate UI update
        posts_data = [{
            'id': p.id,
            'title': p.title,
            'series_order': p.series_order,
            'publication_date': p.publication_date.strftime('%Y-%m-%d') if p.publication_date else None
        } for p in series.posts]
        
        return {
            'success': True,
            'posts': posts_data
        }
        
    except Exception as e:
        db.session.rollback()
        return {'error': str(e)}, 500

# --- Protagonist Management Routes ---

@app.route('/admin/protagonists')
def admin_protagonists():
    """Display all protagonist profiles."""
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    protagonists = Protagonist.query.order_by(Protagonist.name).all()
    return render_template('admin/protagonist_list.html', protagonists=protagonists)

@app.route('/admin/protagonist/new', methods=['GET', 'POST'])
def new_protagonist():
    """Create a new protagonist profile."""
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    form = ProtagonistForm()
    
    if form.validate_on_submit():
        try:
            protagonist = Protagonist(name=form.name.data.strip())
            if session.get('user_role') == 'visitor':
                protagonist.status = 'pending'
            
            db.session.add(protagonist)
            db.session.commit()
            
            if session.get('user_role') == 'visitor':
                update = PendingUpdate(
                    category='Protagonist Update',
                    action='create',
                    item_id=protagonist.id,
                    item_name=protagonist.name,
                    user_id=session.get('user_id'),
                    data=json.dumps({'protagonist_id': protagonist.id})
                )
                db.session.add(update)
                db.session.commit()
                flash('Your protagonist entry has been submitted for admin approval.', 'info')
                return redirect(url_for('admin_protagonists'))
            else:
                flash('Protagonist profile created successfully!')
                return redirect(url_for('edit_protagonist', protagonist_id=protagonist.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating protagonist: {str(e)}')
    
    return render_template('admin/protagonist_form.html', form=form, legend='New Protagonist')

@app.route('/admin/protagonist/<int:protagonist_id>/edit', methods=['GET', 'POST'])
def edit_protagonist(protagonist_id):
    """Edit an existing protagonist profile."""
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    protagonist = Protagonist.query.get_or_404(protagonist_id)
    form = ProtagonistForm(protagonist_id=protagonist_id)
    
    if form.validate_on_submit():
        try:
            old_name = protagonist.name
            new_name = form.name.data.strip()
            old_active = protagonist.is_active
            new_active = form.is_active.data
            
            # Update protagonist name and status
            protagonist.name = new_name
            protagonist.is_active = new_active
            protagonist.updated_at = datetime.utcnow()
            
            # Update all associated posts' author fields
            for post in protagonist.posts.all():
                authors = [a.strip() for a in post.author.split('|')]
                authors = [new_name if a == old_name else a for a in authors]
                post.author = ' | '.join(authors)
                generate_static_post_page(post)
            
            if session.get('user_role') == 'visitor':
                protagonist.status = 'pending'
                update = PendingUpdate(
                    category='Protagonist Update',
                    action='update',
                    item_id=protagonist.id,
                    item_name=protagonist.name,
                    user_id=session.get('user_id'),
                    data=json.dumps({'protagonist_id': protagonist.id})
                )
                db.session.add(update)
                flash('Your protagonist edits have been submitted for admin approval.', 'info')
            else:
                regenerate_all_static_pages()
                flash('Protagonist profile updated successfully!')
            
            db.session.commit()
            return redirect(url_for('admin_protagonists'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating protagonist: {str(e)}')
    
    elif request.method == 'GET':
        form.name.data = protagonist.name
        form.is_active.data = protagonist.is_active
    
    return render_template('admin/protagonist_form.html', form=form, legend='Edit Protagonist', protagonist=protagonist)

@app.route('/admin/protagonist/<int:protagonist_id>/toggle-active', methods=['POST'])
def toggle_protagonist_active(protagonist_id):
    """Toggle protagonist active status (deactivate/reactivate)."""
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    protagonist = Protagonist.query.get_or_404(protagonist_id)
    
    try:
        # Toggle active status
        protagonist.is_active = not protagonist.is_active
        protagonist.updated_at = datetime.utcnow()
        
        # Regenerate static pages for all associated posts
        # (inactive authors won't be displayed)
        for post in protagonist.posts.all():
            generate_static_post_page(post)
        
        db.session.commit()
        regenerate_all_static_pages()
        
        return {
            'success': True,
            'is_active': protagonist.is_active,
            'message': f'Protagonist {"activated" if protagonist.is_active else "deactivated"} successfully'
        }
    except Exception as e:
        db.session.rollback()
        return {'error': str(e)}, 500

@app.route('/admin/protagonist/<int:protagonist_id>/delete', methods=['POST'])
def delete_protagonist(protagonist_id):
    """Delete a protagonist profile (only if inactive and has no post associations)."""
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    protagonist = Protagonist.query.get_or_404(protagonist_id)
    
    try:
        # Check if protagonist is inactive
        if protagonist.is_active:
            return {'error': 'Cannot delete an active protagonist. Please deactivate it first.'}, 400
        
        # Check if protagonist has any post associations
        post_count = protagonist.posts.count()
        if post_count > 0:
            return {'error': f'Cannot delete protagonist with {post_count} associated post(s). Please remove all post associations first.'}, 400
        
        # Safe to delete
        db.session.delete(protagonist)
        db.session.commit()
        
        return {'success': True, 'message': 'Protagonist deleted successfully'}
    except Exception as e:
        db.session.rollback()
        return {'error': str(e)}, 500

@app.route('/api/posts/available-for-protagonist')
def get_available_posts_for_protagonist():
    """Get posts available for adding to a protagonist."""
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    protagonist_id = request.args.get('protagonist_id', type=int)
    search = request.args.get('search', '').strip()
    
    if not protagonist_id:
        return {'error': 'Protagonist ID required'}, 400
    
    protagonist = Protagonist.query.get_or_404(protagonist_id)
    
    # Get posts associated with this protagonist
    associated_post_ids = {p.id for p in protagonist.posts.all()}
    
    # Build query
    query = Post.query
    if search:
        query = query.filter(
            or_(
                Post.title.ilike(f'%{search}%'),
                Post.author.ilike(f'%{search}%')
            )
        )
    
    posts = query.order_by(Post.publication_date.desc()).limit(50).all()
    
    # Format response
    posts_data = [{
        'id': post.id,
        'title': post.title,
        'author': post.author,
        'publication_date': post.publication_date.strftime('%b %d, %Y') if post.publication_date else 'N/A',
        'in_protagonist': post.id in associated_post_ids
    } for post in posts]
    
    return {'posts': posts_data}

@app.route('/api/protagonist/<int:protagonist_id>/posts', methods=['POST'])
def update_protagonist_posts(protagonist_id):
    """Add or remove posts from a protagonist profile."""
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    protagonist = Protagonist.query.get_or_404(protagonist_id)
    data = request.get_json()
    
    try:
        post_updates = data.get('posts', [])
        
        for post_data in post_updates:
            post_id = post_data.get('id')
            action = post_data.get('action')  # 'add' or 'remove'
            
            post = Post.query.get(post_id)
            if not post:
                continue
            
            if action == 'add':
                # Add association
                if post not in protagonist.posts:
                    protagonist.posts.append(post)
                    
                    # Update post author field
                    authors = [a.strip() for a in post.author.split('|') if a.strip()]
                    if protagonist.name not in authors:
                        authors.append(protagonist.name)
                    post.author = ' | '.join(authors)
                    
            elif action == 'remove':
                # Remove association
                if post in protagonist.posts:
                    protagonist.posts.remove(post)
                    
                    # Update post author field
                    authors = [a.strip() for a in post.author.split('|')]
                    authors = [a for a in authors if a != protagonist.name]
                    post.author = ' | '.join(authors) if authors else ''
            
            # Regenerate post static page
            generate_static_post_page(post)
        
        db.session.commit()
        regenerate_all_static_pages()
        
        # Return updated posts list
        posts_data = [{
            'id': p.id,
            'title': p.title,
            'author': p.author,
            'publication_date': p.publication_date.strftime('%b %d, %Y') if p.publication_date else 'N/A'
        } for p in protagonist.posts.all()]
        
        return {
            'success': True,
            'posts': posts_data
        }
        
    except Exception as e:
        db.session.rollback()
        return {'error': str(e)}, 500

# --- Keyword Management Routes ---

@app.route('/admin/keywords')
def admin_keywords():
    """Display all keywords with usage counts."""
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    # Get all keywords ordered alphabetically
    keywords = Keyword.query.order_by(Keyword.name).all()
    
    return render_template('admin/keyword_list.html', keywords=keywords)

@app.route('/admin/keyword/new', methods=['GET', 'POST'])
def new_keyword():
    """Create a new keyword."""
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    form = KeywordForm()
    
    if form.validate_on_submit():
        try:
            # Normalize to lowercase for storage
            normalized_name = form.name.data.strip().lower()
            
            keyword = Keyword(
                name=normalized_name,
                usage_count=0
            )
            if session.get('user_role') == 'visitor':
                keyword.status = 'pending'
            
            db.session.add(keyword)
            db.session.commit()
            
            if session.get('user_role') == 'visitor':
                update = PendingUpdate(
                    category='Keyword Update',
                    action='create',
                    item_id=keyword.id,
                    item_name=keyword.name,
                    user_id=session.get('user_id'),
                    data=json.dumps({'keyword_id': keyword.id})
                )
                db.session.add(update)
                db.session.commit()
                flash('Your keyword has been submitted for admin approval.', 'info')
                return redirect(url_for('admin_keywords'))
            else:
                flash(f'Keyword "{keyword.display_name}" created successfully!')
                return redirect(url_for('edit_keyword', keyword_id=keyword.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating keyword: {str(e)}')
    
    return render_template('admin/keyword_form.html', form=form, legend='New Keyword')

@app.route('/admin/keyword/<int:keyword_id>/edit', methods=['GET', 'POST'])
def edit_keyword(keyword_id):
    """Edit an existing keyword."""
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    keyword = Keyword.query.get_or_404(keyword_id)
    form = KeywordForm(keyword_id=keyword_id)
    
    if form.validate_on_submit():
        try:
            old_name = keyword.name
            # Normalize to lowercase for storage
            new_name = form.name.data.strip().lower()
            
            # Update keyword name
            keyword.name = new_name
            keyword.updated_at = datetime.utcnow()
            
            # Update all associated posts' keywords fields
            for post in keyword.posts:
                if post.keywords:
                    keywords_list = [k.strip().lower() for k in post.keywords.split(',') if k.strip()]
                    # Replace old keyword with new keyword
                    keywords_list = [new_name if k == old_name else k for k in keywords_list]
                    post.keywords = ', '.join(keywords_list)
                    generate_static_post_page(post)
            
            if session.get('user_role') == 'visitor':
                keyword.status = 'pending'
                update = PendingUpdate(
                    category='Keyword Update',
                    action='update',
                    item_id=keyword.id,
                    item_name=keyword.name,
                    user_id=session.get('user_id'),
                    data=json.dumps({'keyword_id': keyword.id})
                )
                db.session.add(update)
                flash('Your keyword edits have been submitted for admin approval.', 'info')
            else:
                regenerate_all_static_pages()
                flash('Keyword updated successfully!')
            
            db.session.commit()
            return redirect(url_for('admin_keywords'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating keyword: {str(e)}')
    
    elif request.method == 'GET':
        # Display in original case for editing (user can change case)
        form.name.data = keyword.name
    
    return render_template('admin/keyword_form.html', form=form, legend='Edit Keyword', keyword=keyword)

@app.route('/admin/keyword/<int:keyword_id>/delete', methods=['POST'])
def delete_keyword(keyword_id):
    """Delete a keyword and remove it from all posts."""
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    keyword = Keyword.query.get_or_404(keyword_id)
    
    try:
        keyword_name = keyword.name
        
        # Remove keyword from all associated posts' keywords fields
        for post in keyword.posts:
            if post.keywords:
                keywords_list = [k.strip().lower() for k in post.keywords.split(',') if k.strip()]
                keywords_list = [k for k in keywords_list if k != keyword_name]
                post.keywords = ', '.join(keywords_list) if keywords_list else ''
                generate_static_post_page(post)
        
        # Delete the keyword (associations will be deleted via cascade)
        db.session.delete(keyword)
        db.session.commit()
        regenerate_all_static_pages()
        
        return {
            'success': True,
            'message': f'Keyword "{keyword_name.upper()}" deleted successfully'
        }
    except Exception as e:
        db.session.rollback()
        return {'error': str(e)}, 500

# API Routes for Keyword Management

@app.route('/api/posts/available-for-keyword')
def get_available_posts_for_keyword():
    """Get posts available for adding to a keyword."""
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    keyword_id = request.args.get('keyword_id', type=int)
    search = request.args.get('search', '').strip()
    
    if not keyword_id:
        return {'error': 'Keyword ID required'}, 400
    
    keyword = Keyword.query.get_or_404(keyword_id)
    
    # Get posts associated with this keyword
    associated_post_ids = {p.id for p in keyword.posts}
    
    # Build query
    query = Post.query
    if search:
        query = query.filter(
            or_(
                Post.title.ilike(f'%{search}%'),
                Post.author.ilike(f'%{search}%'),
                Post.keywords.ilike(f'%{search}%')
            )
        )
    
    posts = query.order_by(Post.publication_date.desc()).limit(50).all()
    
    # Format response
    posts_data = [{
        'id': post.id,
        'title': post.title,
        'author': post.author,
        'keywords': post.keywords,
        'publication_date': post.publication_date.strftime('%b %d, %Y') if post.publication_date else 'N/A',
        'in_keyword': post.id in associated_post_ids
    } for post in posts]
    
    return {'posts': posts_data}

@app.route('/api/keyword/<int:keyword_id>/posts', methods=['POST'])
def update_keyword_posts(keyword_id):
    """Add or remove posts from a keyword."""
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    keyword = Keyword.query.get_or_404(keyword_id)
    data = request.get_json()
    
    try:
        post_updates = data.get('posts', [])
        
        for post_data in post_updates:
            post_id = post_data.get('id')
            action = post_data.get('action')  # 'add' or 'remove'
            
            post = Post.query.get(post_id)
            if not post:
                continue
            
            if action == 'add':
                # Add association
                if post not in keyword.posts:
                    keyword.posts.append(post)
                    keyword.usage_count += 1
                    
                    # Update post keywords field
                    keywords_list = [k.strip().lower() for k in post.keywords.split(',') 
                                   if k.strip()] if post.keywords else []
                    if keyword.name not in keywords_list:
                        keywords_list.append(keyword.name)
                    post.keywords = ', '.join(keywords_list)
                    
            elif action == 'remove':
                # Remove association
                if post in keyword.posts:
                    keyword.posts.remove(post)
                    keyword.usage_count -= 1
                    
                    # Update post keywords field
                    keywords_list = [k.strip().lower() for k in post.keywords.split(',') 
                                   if k.strip()] if post.keywords else []
                    keywords_list = [k for k in keywords_list if k != keyword.name]
                    post.keywords = ', '.join(keywords_list) if keywords_list else ''
            
            # Regenerate post static page
            generate_static_post_page(post)
        
        keyword.updated_at = datetime.utcnow()
        db.session.commit()
        regenerate_all_static_pages()
        
        # Return updated posts list
        posts_data = [{
            'id': p.id,
            'title': p.title,
            'author': p.author,
            'keywords': p.keywords,
            'publication_date': p.publication_date.strftime('%b %d, %Y') if p.publication_date else 'N/A'
        } for p in keyword.posts]
        
        return {
            'success': True,
            'usage_count': keyword.usage_count,
            'posts': posts_data
        }
        
    except Exception as e:
        db.session.rollback()
        return {'error': str(e)}, 500

@app.route('/api/keywords/search')
def search_keywords():
    """Search keywords for autocomplete."""
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return {'keywords': []}
    
    # Search keywords (case-insensitive)
    keywords = Keyword.query.filter(
        Keyword.name.ilike(f'%{query}%')
    ).order_by(Keyword.usage_count.desc()).limit(10).all()
    
    keywords_data = [{
        'name': kw.name,
        'display_name': kw.display_name,
        'usage_count': kw.usage_count
    } for kw in keywords]
    
    return {'keywords': keywords_data}

# --- Slogan Background Management Routes ---

@app.route('/admin/slogan-backgrounds')
def admin_slogan_backgrounds():
    """Display all slogan background pictures."""
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    backgrounds = SloganBackground.query.order_by(SloganBackground.created_at.desc()).all()
    return render_template('admin/slogan_backgrounds.html', backgrounds=backgrounds)

@app.route('/admin/slogan-backgrounds/upload', methods=['POST'])
def upload_slogan_background():
    """Upload a new slogan background picture."""
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    if 'background_image' not in request.files:
        flash('No file part')
        return redirect(url_for('admin_slogan_backgrounds'))
    
    file = request.files['background_image']
    name = request.form.get('name', '')
    
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('admin_slogan_backgrounds'))
    
    if file:
        filename = secure_filename(file.filename)
        # Add timestamp to avoid conflicts
        timestamp = str(int(datetime.utcnow().timestamp()))
        filename = f"slogan_bg_{timestamp}_{filename}"
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        file.save(filepath)
        
        # If this is the first background, make it active
        is_first = SloganBackground.query.count() == 0
        
        background = SloganBackground(
            filename=filename,
            name=name if name else file.filename,
            is_active=is_first
        )
        db.session.add(background)
        db.session.commit()
        
        flash('Background uploaded successfully')
        return redirect(url_for('admin_slogan_backgrounds'))

@app.route('/admin/slogan-backgrounds/<int:bg_id>/activate', methods=['POST'])
def activate_slogan_background(bg_id):
    """Set a slogan background as active."""
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    try:
        # Deactivate all
        SloganBackground.query.update({SloganBackground.is_active: False})
        
        # Activate selected
        background = SloganBackground.query.get_or_404(bg_id)
        background.is_active = True
        
        db.session.commit()
        return {'success': True}
    except Exception as e:
        db.session.rollback()
        return {'error': str(e)}, 500

@app.route('/admin/slogan-backgrounds/<int:bg_id>/delete', methods=['POST'])
def delete_slogan_background(bg_id):
    """Delete a slogan background."""
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    try:
        background = SloganBackground.query.get_or_404(bg_id)
        
        # Don't delete if active unless it's the last one
        if background.is_active and SloganBackground.query.count() > 1:
            return {'error': 'Cannot delete the active background. Activate another one first.'}, 400
        
        # Remove file
        try:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], background.filename)
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            print(f"Error deleting file: {e}")
        
        db.session.delete(background)
        db.session.commit()
        return {'success': True}
    except Exception as e:
        db.session.rollback()
        return {'error': str(e)}, 500

# --- Subscriber Management Routes ---

@app.route('/admin/subscribers')
def admin_subscribers():
    """Management view for table subscribers."""
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    # Fetch all subscribers order by date descending
    subscribers = Subscriber.query.order_by(Subscriber.created_at.desc()).all()
    return render_template('admin/subscriber_list.html', subscribers=subscribers)

@app.route('/admin/subscribers/<int:sub_id>/delete', methods=['POST'])
def delete_subscriber(sub_id):
    """Delete a subscriber."""
    if 'admin_logged_in' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        sub = Subscriber.query.get_or_404(sub_id)
        db.session.delete(sub)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# --- Public Interface Routes ---

@app.route('/subscribe', methods=['POST'])
def subscribe():
    """Handle newsletter subscription with IP tracking and update logic."""
    data = request.get_json()
    email = data.get('email')
    confirm_update = data.get('confirm', False)
    
    if not email or '@' not in email:
        return jsonify({'error': 'Invalid email address'}), 400
    
    try:
        ip = get_client_ip()
        
        # 1. Check if this IP is already associated with an email
        existing_by_ip = Subscriber.query.filter_by(ip_address=ip).first()
        
        if existing_by_ip:
            # If it's the same email, just say they are already subscribed
            if existing_by_ip.email == email:
                return jsonify({'success': True, 'message': 'You are already subscribed!'})
            
            # If it's a different email, we ask for confirmation unless they already confirmed
            if not confirm_update:
                return jsonify({
                    'success': False, 
                    'conflict': True, 
                    'message': 'You have already subscribed. Confirm if you want to update your email.'
                })
            
            # Update the email for this IP
            # Check if the new email is already taken by ANOTHER record (not very likely with one-IP-one-email rule but good to check)
            other_with_email = Subscriber.query.filter(Subscriber.email == email, Subscriber.ip_address != ip).first()
            if other_with_email:
                return jsonify({'error': 'This email is already associated with another subscription.'}), 400
                
            existing_by_ip.email = email
            existing_by_ip.created_at = datetime.utcnow() # Update subscription time
            db.session.commit()
            return jsonify({'success': True, 'message': 'Your email has been updated!'})

        # 2. Check if the email itself exists (from a different IP maybe)
        existing_by_email = Subscriber.query.filter_by(email=email).first()
        if existing_by_email:
            # Update IP and country if they moved or something? Or just say subscribed.
            # For now, let's keep it simple: if email exists, they are subscribed.
            return jsonify({'success': True, 'message': 'This email is already subscribed!'})
        
        # 3. New subscription
        country = get_country_from_ip(ip)
        subscriber = Subscriber(email=email, ip_address=ip, country=country)
        db.session.add(subscriber)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Successfully subscribed!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/search')
def search():
    """Search posts."""
    query = request.args.get('q', '').strip()
    if not query:
        return render_template('search_results.html', posts=[], query='')
    
    # Search in title, author, abstract, text_content
    posts = Post.query.filter(
        Post.status == 'published', # Only search published posts
        or_(
            Post.title.ilike(f'%{query}%'),
            Post.author.ilike(f'%{query}%'),
            Post.abstract.ilike(f'%{query}%'),
            Post.text_content.ilike(f'%{query}%')
        )
    ).order_by(Post.publication_date.desc()).all()
    
    return render_template('search_results.html', posts=posts, query=query)

# --- Theme Post Management API ---

@app.route('/api/posts/available-for-theme')
def get_available_posts_for_theme():
    """Get posts available for adding to a theme."""
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    theme_id = request.args.get('theme_id', type=int)
    search = request.args.get('search', '').strip()
    
    print(f"DEBUG: theme_id={theme_id}, search='{search}'")  # Debug logging
    
    if not theme_id:
        return {'error': 'Theme ID required'}, 400
    
    try:
        theme = Theme.query.get_or_404(theme_id)
    except Exception as e:
        print(f"ERROR: Failed to get theme: {e}")
        return {'error': f'Theme not found: {str(e)}'}, 404
    
    # Build query
    try:
        query = Post.query
        if search:
            query = query.filter(
                or_(
                    Post.title.ilike(f'%{search}%'),
                    Post.author.ilike(f'%{search}%')
                )
            )
        
        posts = query.order_by(Post.publication_date.desc()).limit(50).all()
        print(f"DEBUG: Found {len(posts)} posts")  # Debug logging
        
        # Format response
        posts_data = []
        for post in posts:
            posts_data.append({
                'id': post.id,
                'title': post.title,
                'author': post.author or 'Unknown',
                'publication_date': post.publication_date.strftime('%b %d, %Y') if post.publication_date else 'N/A',
                'in_theme': theme in post.themes
            })
        
        print(f"DEBUG: Returning {len(posts_data)} posts")  # Debug logging
        return {'posts': posts_data}
    except Exception as e:
        print(f"ERROR: Failed to query posts: {e}")
        import traceback
        traceback.print_exc()
        return {'error': f'Failed to load posts: {str(e)}'}, 500

@app.route('/api/theme/<int:theme_id>/posts', methods=['POST'])
def manage_theme_posts(theme_id):
    """Add or remove posts from a theme."""
    if 'admin_logged_in' not in session:
        return {'error': 'Unauthorized'}, 401
    
    theme = Theme.query.get_or_404(theme_id)
    data = request.get_json()
    
    if not data or 'posts' not in data:
        return {'error': 'Invalid request'}, 400
    
    try:
        for post_data in data['posts']:
            post_id = post_data.get('id')
            action = post_data.get('action')
            
            if not post_id or not action:
                continue
            
            post = Post.query.get(post_id)
            if not post:
                continue
            
            if action == 'add':
                if theme not in post.themes:
                    post.themes.append(theme)
            elif action == 'remove':
                if theme in post.themes:
                    post.themes.remove(theme)
        
        db.session.commit()
        
        # Regenerate static pages
        regenerate_all_static_pages()
        
        # Return updated posts list
        posts_data = []
        for post in theme.posts:
            posts_data.append({
                'id': post.id,
                'title': post.title,
                'author': post.author or 'Unknown',
                'publication_date': post.publication_date.strftime('%b %d, %Y') if post.publication_date else 'N/A'
            })
        
        return {'success': True, 'posts': posts_data}
    
    except Exception as e:
        db.session.rollback()
        return {'error': str(e)}, 500

@app.route('/api/protagonists/search')
def search_protagonists():
    """API endpoint for protagonist autocomplete in author field."""
    query = request.args.get('q', '').strip()
    if not query:
        return {'protagonists': []}
    
    # Search for protagonists that start with or contain the query (case-insensitive)
    protagonists = Protagonist.query.filter(
        Protagonist.name.ilike(f'%{query}%')
    ).order_by(Protagonist.name).limit(10).all()
    
    return {
        'protagonists': [
            {
                'name': p.name,
                'post_count': p.post_count,
                'is_active': p.is_active
            } for p in protagonists
        ]
    }

# --- Public Routes ---

@app.route('/')
def index():
    print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}") # New diagnostic print
    # Get all posts from the database (limit to 6)
    # Get regular posts (non-initiative) for the waterfall
    all_posts = Post.query.filter_by(status='published').order_by(Post.publication_date.desc()).limit(6).all()
    # Find active featured post
    featured_post = Post.query.filter_by(status='published', is_featured=True).order_by(Post.publication_date.desc()).first()
    # Get all keywords for search and convert to dict for JSON serialization
    keywords_query = Keyword.query.order_by(Keyword.name).all()
    keywords = [{'id': k.id, 'name': k.name, 'display_name': k.display_name, 'usage_count': k.usage_count} for k in keywords_query]

    active_slogan_bg = SloganBackground.query.filter_by(is_active=True).first()

    return render_template('index.html', 
                           posts=all_posts, 
                           featured_post=featured_post,
                           slogan_bg=active_slogan_bg,
                           keywords=keywords)

@app.route('/stories')
def stories():
    # Get all active themes for dynamic filtering
    themes = Theme.query.filter_by(is_active=True, status='published').all()
    
    # Get all published posts
    posts = Post.query.filter_by(status='published').order_by(Post.publication_date.desc()).all()
    
    return render_template('voices.html', posts=posts, themes=themes)

@app.route('/our_voices_all')
def our_voices_all():
    # Get filter parameter
    filter_tag = request.args.get('filter', 'all')
    # Get keyword filter parameter (comma-separated keyword IDs)
    keyword_ids = request.args.get('keywords', '')
    
    # Start with base query - only published posts
    query = Post.query.filter_by(status='published')
    
    # Apply tag filter
    if filter_tag != 'all':
        query = query.join(Post.tags).filter(Tag.name.ilike(f'%{filter_tag}%'))
    
    # Apply keyword filter (posts must have ALL selected keywords)
    if keyword_ids:
        keyword_id_list = [int(kid) for kid in keyword_ids.split(',') if kid.strip().isdigit()]
        if keyword_id_list:
            # Get posts that have all selected keywords
            for keyword_id in keyword_id_list:
                # Use subquery to check if post has this keyword
                subquery = db.session.query(post_keywords.c.post_id).filter(
                    post_keywords.c.keyword_id == keyword_id
                )
                query = query.filter(Post.id.in_(subquery))
    
    posts = query.order_by(Post.publication_date.desc()).all()
    
    # Get all tags for dynamic filtering
    tags = Tag.query.all()
    # Get all keywords for search and convert to dict for JSON serialization
    keywords_query = Keyword.query.order_by(Keyword.name).all()
    keywords = [{'id': k.id, 'name': k.name, 'display_name': k.display_name, 'usage_count': k.usage_count} for k in keywords_query]
    
    return render_template('our_voices_all.html', posts=posts, tags=tags, keywords=keywords)

@app.route('/our_voices_partial')
def our_voices_partial():
    # Get featured post
    featured_post = Post.query.filter_by(is_featured=True).first()
    # Get 5 newest posts (excluding featured if it exists)
    query = Post.query.order_by(Post.publication_date.desc())
    if featured_post:
        query = query.filter(Post.id != featured_post.id)
    newest_posts = query.limit(5).all()
    
    # Combine featured and newest posts
    posts = []
    if featured_post:
        posts.append(featured_post)
    posts.extend(newest_posts)
    
    return render_template('our_voices_partial.html', posts=posts, featured_post=featured_post)



@app.route('/about')
def about():
    # Get all active themes for the What We Publish section
    themes = Theme.query.filter_by(is_active=True, status='published').all()
    return render_template('about.html', themes=themes)

@app.route('/explore-themes')
def explore_themes():
    # Get all active themes
    themes = Theme.query.filter_by(is_active=True, status='published').all()
    return render_template('explore_themes.html', themes=themes)

@app.route('/theme/<theme_slug>')
def theme_posts(theme_slug):
    # Get theme by slug and its posts (from both FK and many-to-many relationships)
    theme = Theme.query.filter_by(slug=theme_slug, is_active=True, status='published').first_or_404()
    posts = sorted(theme.published_posts, key=lambda p: p.publication_date, reverse=True)
    return render_template('theme_posts.html', theme=theme, posts=posts)

@app.route('/post/<int:post_id>')
def post_detail(post_id):
    # Find post by ID for full-page view - must be published
    post = Post.query.filter_by(id=post_id, status='published').first_or_404()
    return render_template('post.html', post=post)

@app.route('/<slug>')
def post(slug):
    # Find post by slug - must be published
    post = Post.query.filter_by(slug=slug, status='published').first_or_404()
    return render_template('post.html', post=post)

# --- Main ---

# This block runs the application in debug mode when the script is executed directly
if __name__ == '__main__':
    app.run(debug=True, port=5001)
