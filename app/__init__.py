# Arquivo completo: app/__init__.py
from flask import Flask, render_template, request, current_app
from flask_login import LoginManager, current_user
from flask_mail import Mail
from app.core.models import db, User, Event, Ministry, Media
from config import Config
from datetime import datetime
from flask_migrate import Migrate

login_manager = LoginManager()
mail = Mail()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    login_manager.login_view = 'auth.login'
    migrate.init_app(app, db)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Blueprints - Importações dentro da função para evitar ciclos
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

    import json
    @app.template_filter('from_json')
    def from_json_filter(value):
        if not value:
            return {}
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return {}

    # Rota inicial
    @app.route('/')
    def index():
        return render_template('index.html')

    # ========== CONTEXT PROCESSORS ==========
    
    @app.context_processor
    def inject_public_events():
        if current_user.is_authenticated:
            public_events = Event.query.filter(Event.ministry_id.is_(None), Event.church_id == current_user.church_id).order_by(Event.start_time.asc()).limit(5).all()
        else:
            public_events = Event.query.filter(Event.ministry_id.is_(None)).order_by(Event.start_time.asc()).limit(5).all()
        return dict(public_events=public_events)

    @app.context_processor
    def inject_is_ministry_leader():
        """Função para verificar se o usuário é líder, vice ou líder extra do ministério"""
        def is_ministry_leader(ministry):
            """
            Verifica se o usuário atual é líder, vice-líder ou está na lista extra do ministério.
            Pode receber um objeto Ministry ou um ID (inteiro)
            """
            if not current_user.is_authenticated:
                return False
            
            # Se receber um ID, busca o ministério
            if isinstance(ministry, int):
                ministry_obj = Ministry.query.get(ministry)
                if not ministry_obj:
                    return False
            else:
                ministry_obj = ministry
            
            # Verifica líder e vice
            if ministry_obj.leader_id == current_user.id or ministry_obj.vice_leader_id == current_user.id:
                return True
            
            # Verifica na lista extra (JSON)
            if ministry_obj.extra_leaders and current_user.id in ministry_obj.extra_leaders:
                return True
            
            return False
        return dict(is_ministry_leader=is_ministry_leader)

    @app.context_processor
    def inject_public_media():
        if current_user.is_authenticated:
            public_media = Media.query.filter_by(church_id=current_user.church_id, ministry_id=None).order_by(Media.created_at.desc()).limit(5).all()
        else:
            public_media = Media.query.filter(Media.ministry_id.is_(None)).order_by(Media.created_at.desc()).limit(5).all()
        return dict(public_media=public_media)

    # Opcional: injetar data/hora atual para templates
    @app.context_processor
    def inject_now():
        return dict(now=datetime.now)

    return app