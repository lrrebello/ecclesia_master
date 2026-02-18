# Arquivo completo: app/__init__.py (baseado no TXT, com context processor para public_media adicionado)
from flask import Flask, render_template, request, current_app
from flask_login import LoginManager, current_user
from flask_mail import Mail
from app.core.models import db, User, Event, Ministry, Media  # Adicionado Media para o context processor
from config import Config
from datetime import datetime

login_manager = LoginManager()
mail = Mail()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    login_manager.login_view = 'auth.login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Blueprints
    from app.modules.auth.routes import auth_bp
    from app.modules.members.routes import members_bp
    from app.modules.finance.routes import finance_bp
    from app.modules.finance.modelo25 import modelo25_bp
    from app.modules.edification.routes import edification_bp
    from app.modules.admin.routes import admin_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(members_bp, url_prefix='/members')
    app.register_blueprint(finance_bp, url_prefix='/finance')
    app.register_blueprint(modelo25_bp)
    app.register_blueprint(edification_bp, url_prefix='/edification')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Rota inicial
    @app.route('/')
    def index():
        return render_template('index.html')

    # Context Processor para eventos públicos
    @app.context_processor
    def inject_public_events():
        # Se não estiver logado, traz eventos gerais de qualquer igreja (ou da sede se preferir)
        # Se estiver logado, traz eventos gerais da sua igreja
        if current_user.is_authenticated:
            public_events = Event.query.filter(Event.ministry_id.is_(None), Event.church_id == current_user.church_id).order_by(Event.start_time.asc()).limit(5).all()
        else:
            public_events = Event.query.filter(Event.ministry_id.is_(None)).order_by(Event.start_time.asc()).limit(5).all()
        return dict(public_events=public_events)

    # Context Processor para is_ministry_leader
    @app.context_processor
    def inject_is_ministry_leader():
        def is_ministry_leader(ministry_id):
            ministry = Ministry.query.get(ministry_id)
            return ministry and ministry.leader_id == current_user.id
        return dict(is_ministry_leader=is_ministry_leader)

    # Novo Context Processor para midias públicas (slides)
    @app.context_processor
    def inject_public_media():
        if current_user.is_authenticated:
            public_media = Media.query.filter_by(church_id=current_user.church_id, ministry_id=None).order_by(Media.created_at.desc()).limit(5).all()
        else:
            public_media = Media.query.filter(Media.ministry_id.is_(None)).order_by(Media.created_at.desc()).limit(5).all()  # Públicas globais para não logados
        return dict(public_media=public_media)

    return app