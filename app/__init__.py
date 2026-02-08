from flask import Flask
from flask_login import LoginManager
from app.core.models import db, User
from config import Config

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
    
    # Register Blueprints
    from app.modules.auth.routes import auth_bp
    from app.modules.members.routes import members_bp
    from app.modules.finance.routes import finance_bp
    from app.modules.edification.routes import edification_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(members_bp, url_prefix='/members')
    app.register_blueprint(finance_bp, url_prefix='/finance')
    app.register_blueprint(edification_bp, url_prefix='/edification')
    
    # Main route
    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('auth.login'))
        
    return app
