from flask import Flask, render_template
from flask_login import LoginManager
from app.core.models import db, User, Event, Media
from config import Config
from datetime import datetime

login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Context processor para eventos públicos na inicial
    @app.context_processor
    def inject_public_events():
        public_events = Event.query.filter(
            Event.ministry_id.is_(None),
            Event.start_time >= datetime.utcnow()
        ).order_by(Event.start_time.asc()).limit(5).all()
        return dict(public_events=public_events)
    
    # Register Blueprints
    from app.modules.auth.routes import auth_bp
    from app.modules.members.routes import members_bp
    from app.modules.finance.routes import finance_bp
    from app.modules.edification.routes import edification_bp
    from app.modules.admin.routes import admin_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(members_bp, url_prefix='/members')
    app.register_blueprint(finance_bp, url_prefix='/finance')
    app.register_blueprint(edification_bp, url_prefix='/edification')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # Main route
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.context_processor
    def inject_recent_media():
        recent_media = Media.query.filter_by(church_id=1).order_by(Media.created_at.desc()).limit(6).all()  # ajuste church_id se necessário
        return dict(recent_media=recent_media)
        
    return app