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
    nif = db.Column(db.String(20)) # Número de Contribuinte
    email = db.Column(db.String(120))
    currency_symbol = db.Column(db.String(5), default='R$')
    is_main = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    logo_path = db.Column(db.String(255), nullable=True)  # Novo campo para o logo
    member_card_front = db.Column(db.String(255), nullable=True)  # Arte da frente do cartão
    member_card_back = db.Column(db.String(255), nullable=True)  # Arte do verso do cartão
    card_front_layout = db.Column(db.JSON, nullable=True)  # ex: {'name': {'x': 30, 'y': 20, 'width': 50}, 'photo': {...}, ...}
    card_back_layout = db.Column(db.JSON, nullable=True)
    
    # Novos campos para Church
    postal_code = db.Column(db.String(20), nullable=True)  # Código postal
    concelho = db.Column(db.String(100), nullable=True)    # Concelho (município)
    localidade = db.Column(db.String(100), nullable=True)  # Localidade
    
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
    # ─── Novo campo ────────────────────────────────────────
    is_lead_pastor = db.Column(db.Boolean, default=False, nullable=False)   # ou is_pastor, escolha o nome que preferir
    
    users = db.relationship('User', backref='church_role', lazy=True)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    
    # Dados Pessoais Expandidos
    birth_date = db.Column(db.Date)
    baptism_date = db.Column(db.Date, nullable=True)
    conversion_date = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(20))
    marital_status = db.Column(db.String(50), nullable=True)
    spouse_name = db.Column(db.String(100), nullable=True)
    documents = db.Column(db.String(200)) # Flexível para diferentes países
    tax_id = db.Column(db.String(20), nullable=True)  # NIF (PT), CPF/CNPJ (BR), etc.
    address = db.Column(db.Text)
    phone = db.Column(db.String(50))
    profile_photo = db.Column(db.String(255), nullable=True)
    
    # Novos campos para User
    postal_code = db.Column(db.String(20), nullable=True)     # Código postal
    concelho = db.Column(db.String(100), nullable=True)       # Concelho (município)
    localidade = db.Column(db.String(100), nullable=True)     # Localidade
    education_level = db.Column(db.String(100), nullable=True)  # Escolaridade
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Criado em
    
    # Status e Permissões
    status = db.Column(db.String(20), default='pending') # pending, active, rejected
    is_email_verified = db.Column(db.Boolean, default=False)
    email_verification_token = db.Column(db.String(100), unique=True, nullable=True)
    
    # Consentimento RGPD/LGPD
    data_consent = db.Column(db.Boolean, default=False)
    data_consent_date = db.Column(db.DateTime)
    marketing_consent = db.Column(db.Boolean, default=False)
    
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
    is_kids_ministry = db.Column(db.Boolean, default=False)
    
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

class TransactionCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(10), nullable=False) # income, expense
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    
    church = db.relationship('Church', backref='transaction_categories')

class PaymentMethod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    is_electronic = db.Column(db.Boolean, default=False) # Tag para lógica fiscal
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    
    church = db.relationship('Church', backref='payment_methods')

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10)) # income, expense
    category_id = db.Column(db.Integer, db.ForeignKey('transaction_category.id'), nullable=True)
    category_name = db.Column(db.String(100))
    payment_method_id = db.Column(db.Integer, db.ForeignKey('payment_method.id'), nullable=True)
    payment_method_name = db.Column(db.String(100))
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'))
    receipt_path = db.Column(db.String(255))
    
    category = db.relationship('TransactionCategory', backref='transactions')
    payment_method = db.relationship('PaymentMethod', backref='transactions')
    church = db.relationship('Church', backref='transactions')
    user = db.relationship('User', backref='transactions')

class MinistryTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ministry_id = db.Column(db.Integer, db.ForeignKey('ministry.id'), nullable=False)
    type = db.Column(db.String(10)) # income, expense
    category_id = db.Column(db.Integer, db.ForeignKey('transaction_category.id'), nullable=True)
    category_name = db.Column(db.String(100))
    payment_method_id = db.Column(db.Integer, db.ForeignKey('payment_method.id'), nullable=True)
    payment_method_name = db.Column(db.String(100))
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)
    is_debt = db.Column(db.Boolean, default=False) # "Põe na conta"
    debtor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_paid = db.Column(db.Boolean, default=True) # Se for débito, marca se já foi pago
    
    category = db.relationship('TransactionCategory')
    payment_method = db.relationship('PaymentMethod')
    debtor = db.relationship('User', backref='debts')

class KidsActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text)
    age_group = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BibleStory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(255)) # URL ou caminho da ilustração
    reference = db.Column(db.String(100)) # Ex: Gênesis 1
    order = db.Column(db.Integer, default=0)
    game_data = db.Column(db.Text) # JSON com palavras e dicas para jogos
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    quizzes = db.relationship('BibleQuiz', backref='story', lazy=True, cascade="all, delete-orphan")

class BibleQuiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('bible_story.id'), nullable=False)
    question = db.Column(db.String(500), nullable=False)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=True)
    correct_option = db.Column(db.String(1)) # 'A', 'B', 'C' ou 'D'
    explanation = db.Column(db.Text) # Breve explicação do porquê ser a correta
    is_published = db.Column(db.Boolean, default=True)

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
    options = db.Column(db.Text) # JSON string com as opções
    correct_option = db.Column(db.String(1)) # 1=A, 2=B, 3=C, 4=D
    explanation = db.Column(db.Text)
    is_published = db.Column(db.Boolean, default=False)

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