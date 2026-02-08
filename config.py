import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-ecclesia-2026'
    
    # Suporte dinâmico para PostgreSQL ou SQLite
    # No Heroku/Render, a variável DATABASE_URL é preenchida automaticamente
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = database_url or 'sqlite:///ecclesia.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app/static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
