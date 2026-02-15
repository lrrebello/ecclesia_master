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
    currency_symbol = db.Column(db.String(5), default='R$')
    is_main = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    members = db.relationship('User', backref='church', lazy=True)
    ministries = db.relationship('Ministry', backref='church', lazy=True)
    assets = db.relationship('Asset', backref='church', lazy=True)
    roles = db.relationship('ChurchRole', backref='church', lazy=True, cascade="all, delete-orphan")

class ChurchRole(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=True)
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    order = db.Column(db.Integer, default=0)  # para ordenar na exibição
    
    users = db.relationship('User', backref='church_role', lazy=True)

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
    profile_photo = db.Column(db.String(255), nullable=True)
    
    # Status e Permissões
    status = db.Column(db.String(20), default='pending') # pending, active, rejected
    is_ministry_leader = db.Column(db.Boolean, default=False)
    
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'))
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=True)
    church_role_id = db.Column(db.Integer, db.ForeignKey('church_role.id'), nullable=True)
    
    # Relacionamentos
    ministries = db.relationship('Ministry', secondary=member_ministries, backref=db.backref('members', lazy='dynamic'))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    # Permissoes
    can_manage_ministries = db.Column(db.Boolean, default=False)
    can_manage_media = db.Column(db.Boolean, default=False)
    can_publish_devotionals = db.Column(db.Boolean, default=False)
    can_approve_members = db.Column(db.Boolean, default=False)
    can_manage_finance = db.Column(db.Boolean, default=False)
    can_manage_kids = db.Column(db.Boolean, default=False)
    can_manage_events = db.Column(db.Boolean, default=False)

    @property
    def is_global_admin(self):
        return self.church_role and self.church_role.name == 'Administrador Global'

class Ministry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'))
    leader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    events = db.relationship('Event', backref='ministry', lazy=True)
    leader = db.relationship('User', foreign_keys=[leader_id])
    transactions = db.relationship('MinistryTransaction', backref='ministry', lazy=True)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_time = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200))
    ministry_id = db.Column(db.Integer, db.ForeignKey('ministry.id'), nullable=True)
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'))
    recurrence = db.Column(db.String(20), default='none')

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    identifier = db.Column(db.String(50))
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
    type = db.Column(db.String(50))

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
    
    church = db.relationship('Church', backref='transactions')
    user = db.relationship('User', backref='transactions')

class MinistryTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ministry_id = db.Column(db.Integer, db.ForeignKey('ministry.id'), nullable=False)
    type = db.Column(db.String(10)) # income, expense
    category = db.Column(db.String(50)) # Cantina, Evento, Doação, etc.
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)
    is_debt = db.Column(db.Boolean, default=False) # "Põe na conta"
    debtor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_paid = db.Column(db.Boolean, default=True) # Se for débito, marca se já foi pago
    
    debtor = db.relationship('User', backref='debts')

class KidsActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text)
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
    options = db.Column(db.Text)
    correct_option = db.Column(db.Integer)

class Devotional(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    verse = db.Column(db.String(200))
    date = db.Column(db.Date, default=datetime.utcnow().date)

class Album(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=False)
    ministry_id = db.Column(db.Integer, db.ForeignKey('ministry.id'), nullable=True)
    
    media_items = db.relationship('Media', backref='album', lazy=True, cascade="all, delete-orphan")
    church = db.relationship('Church', backref='albums')
    ministry = db.relationship('Ministry', backref='albums')

class Media(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    file_path = db.Column(db.String(255), nullable=False)
    media_type = db.Column(db.String(20), default='image')
    event_name = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=False)
    ministry_id = db.Column(db.Integer, db.ForeignKey('ministry.id'), nullable=True)
    album_id = db.Column(db.Integer, db.ForeignKey('album.id'), nullable=True)
    
    church = db.relationship('Church', backref='media_items')
    ministry = db.relationship('Ministry', backref='media_items')
