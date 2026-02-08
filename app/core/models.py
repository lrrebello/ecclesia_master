from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Tabela de associação para Membros e Ministérios (Muitos-para-Muitos)
member_ministries = db.Table('member_ministries',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('ministry_id', db.Integer, db.ForeignKey('ministry.id'), primary_key=True)
)

class Church(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200))
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    is_main = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    members = db.relationship('User', backref='church', lazy=True)
    ministries = db.relationship('Ministry', backref='church', lazy=True)
    assets = db.relationship('Asset', backref='church', lazy=True)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    
    # Dados Pessoais Expandidos
    birth_date = db.Column(db.Date)
    gender = db.Column(db.String(20))
    documents = db.Column(db.String(200)) # Flexível para diferentes países
    address = db.Column(db.Text)
    phone = db.Column(db.String(50))
    
    # Status e Permissões
    role = db.Column(db.String(20), default='member') # admin, pastor_leader, treasurer, member
    status = db.Column(db.String(20), default='pending') # pending, active, rejected
    is_ministry_leader = db.Column(db.Boolean, default=False)
    
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'))
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=True)
    
    # Relacionamentos
    ministries = db.relationship('Ministry', secondary=member_ministries, backref=db.backref('members', lazy='dynamic'))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Ministry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'))
    leader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    events = db.relationship('Event', backref='ministry', lazy=True)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_time = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200))
    ministry_id = db.Column(db.Integer, db.ForeignKey('ministry.id'), nullable=True) # Se nulo, é evento geral da igreja
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'))

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50)) # Equipamento, Veículo, Móvel
    identifier = db.Column(db.String(50)) # Placa, Serial
    purchase_date = db.Column(db.Date)
    value = db.Column(db.Float)
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'))
    
    maintenance_logs = db.relationship('MaintenanceLog', backref='asset', lazy=True)

class MaintenanceLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    date = db.Column(db.Date, default=datetime.utcnow().date)
    description = db.Column(db.Text)
    cost = db.Column(db.Float, default=0.0)
    type = db.Column(db.String(50)) # Combustível, Seguro, Reparo

class Family(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    users = db.relationship('User', backref='family_group', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10)) # income, expense
    category = db.Column(db.String(50))
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'))
    receipt_path = db.Column(db.String(255))

class KidsActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text) # Markdown ou link para imagem/PDF
    age_group = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Study(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='Geral')
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    questions = db.relationship('StudyQuestion', backref='study', lazy=True)

class StudyQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    study_id = db.Column(db.Integer, db.ForeignKey('study.id'))
    question_text = db.Column(db.Text, nullable=False)
    options = db.Column(db.Text) # JSON string com opções
    correct_option = db.Column(db.Integer)

class Devotional(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    verse = db.Column(db.String(200))
    date = db.Column(db.Date, default=datetime.utcnow().date)
