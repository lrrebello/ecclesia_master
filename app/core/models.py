from sqlalchemy import JSON
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

    # 🔥 CONFIGURAÇÕES POR FILIAL
    smtp_server = db.Column(db.String(255), nullable=True)
    smtp_port = db.Column(db.Integer, default=587)
    smtp_user = db.Column(db.String(255), nullable=True)
    smtp_password = db.Column(db.String(255), nullable=True)
    smtp_use_tls = db.Column(db.Boolean, default=True)
    email_from = db.Column(db.String(255), nullable=True)
    email_from_name = db.Column(db.String(255), nullable=True)
    gemini_api_key = db.Column(db.String(500), nullable=True)
    maintenance_mode = db.Column(db.Boolean, default=False)
    
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
    observations = db.Column(db.Text, nullable=True)  # Observações gerais (tamanho roupa, sapato, alergias, etc.)

    # Recuperação de senha
    reset_password_token = db.Column(db.String(100), unique=True, nullable=True)
    reset_password_expires = db.Column(db.DateTime, nullable=True)
    
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
    vice_leader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_kids_ministry = db.Column(db.Boolean, default=False)
    extra_leaders = db.Column(db.JSON, default=[])  # 🔥 Lista de IDs extras

    
    events = db.relationship('Event', backref='ministry', lazy=True)
    leader = db.relationship('User', foreign_keys=[leader_id])
    transactions = db.relationship('MinistryTransaction', backref='ministry', lazy=True)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
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
    requires_linked_entity = db.Column(db.Boolean, default=False)  # 🔥 NOVO CAMPO
    
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
    bank_account_id = db.Column(db.Integer, db.ForeignKey('bank_accounts.id'), nullable=True)
    
    # 🔥 ADICIONAR ESTA LINHA
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.id'), nullable=True)
    
    # Relacionamentos
    bank_account = db.relationship('BankAccount', backref='transactions')
    category = db.relationship('TransactionCategory', backref='transactions')
    payment_method = db.relationship('PaymentMethod', backref='transactions')
    church = db.relationship('Church', backref='transactions')
    user = db.relationship('User', backref='transactions')
    
    # 🔥 ADICIONAR ESTE RELACIONAMENTO
    bill = db.relationship('Bill', backref=db.backref('transactions', lazy='dynamic'))


class MinistryTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ministry_id = db.Column(db.Integer, db.ForeignKey('ministry.id'), nullable=False)
    type = db.Column(db.String(10)) # income, expense
    
    # Categorias (geral - já existente)
    category_id = db.Column(db.Integer, db.ForeignKey('transaction_category.id'), nullable=True)
    category_name = db.Column(db.String(100))
    
    # 🔥 NOVO: Categoria personalizada do ministério
    ministry_category_id = db.Column(db.Integer, db.ForeignKey('ministry_categories.id'), nullable=True)
    
    # Métodos de pagamento (geral - já existente)
    payment_method_id = db.Column(db.Integer, db.ForeignKey('payment_method.id'), nullable=True)
    payment_method_name = db.Column(db.String(100))
    
    # 🔥 NOVO: Método de pagamento personalizado do ministério
    ministry_payment_method_id = db.Column(db.Integer, db.ForeignKey('ministry_payment_methods.id'), nullable=True)
    
    # 🔥 NOVO: Conta bancária (opcional)
    bank_account_id = db.Column(db.Integer, db.ForeignKey('bank_accounts.id'), nullable=True)
    
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)
    is_debt = db.Column(db.Boolean, default=False) # "Põe na conta"
    debtor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_paid = db.Column(db.Boolean, default=True) # Se for débito, marca se já foi pago
    
    # Relacionamentos EXISTENTES (mantidos iguais)
    category = db.relationship('TransactionCategory')
    payment_method = db.relationship('PaymentMethod')
    debtor = db.relationship('User', backref='debts')
    
    # 🔥 NOVOS relacionamentos COM primaryjoin EXPLÍCITO
    ministry_category = db.relationship(
        'MinistryCategory',
        primaryjoin="MinistryTransaction.ministry_category_id == MinistryCategory.id",
        backref=db.backref('ministry_transactions', lazy='dynamic'),
        foreign_keys=[ministry_category_id]
    )
    
    ministry_payment_method = db.relationship(
        'MinistryPaymentMethod',
        primaryjoin="MinistryTransaction.ministry_payment_method_id == MinistryPaymentMethod.id",
        backref=db.backref('ministry_transactions', lazy='dynamic'),
        foreign_keys=[ministry_payment_method_id]
    )
    
    bank_account = db.relationship(
        'BankAccount',
        primaryjoin="MinistryTransaction.bank_account_id == BankAccount.id",
        backref=db.backref('ministry_transactions', lazy='dynamic'),
        foreign_keys=[bank_account_id]
    )

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

class EmojiWord(db.Model):
    __tablename__ = 'emoji_words'
    
    id = db.Column(db.Integer, primary_key=True)
    emoji = db.Column(db.String(50), nullable=False)  # 👑 ou bi-crown
    emoji_type = db.Column(db.String(20), default='unicode')  # unicode, bootstrap, custom
    custom_icon = db.Column(db.String(255), nullable=True)
    words = db.Column(db.JSON, default=[])  # Lista de palavras ["DAVI", "REI", "SALOMÃO"]
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

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

# Adicione estas classes no seu app/core/models.py

class StudyProgress(db.Model):
    __tablename__ = 'study_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    study_id = db.Column(db.Integer, db.ForeignKey('study.id'), nullable=False)
    last_page = db.Column(db.Integer, default=1)
    last_position = db.Column(db.Integer, default=0)
    completed = db.Column(db.Boolean, default=False)
    last_access = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='study_progress')
    study = db.relationship('Study', backref='user_progress')


class StudyHighlight(db.Model):
    __tablename__ = 'study_highlights'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    study_id = db.Column(db.Integer, db.ForeignKey('study.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    note = db.Column(db.Text, nullable=True)  # Anotação associada
    color = db.Column(db.String(20), default='yellow')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='study_highlights')
    study = db.relationship('Study', backref='highlights')


class StudyNote(db.Model):
    __tablename__ = 'study_notes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    study_id = db.Column(db.Integer, db.ForeignKey('study.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    note = db.Column(db.Text, nullable=False)
    page = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='study_notes')
    study = db.relationship('Study', backref='notes')

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

class SystemLog(db.Model):
    __tablename__ = 'system_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=True)
    action = db.Column(db.String(20), nullable=False)
    module = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    old_values = db.Column(JSON, nullable=True)  # <--- AGORA FUNCIONA
    new_values = db.Column(JSON, nullable=True)  # <--- AGORA FUNCIONA
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('logs', lazy='dynamic'))
    church = db.relationship('Church', backref=db.backref('logs', lazy='dynamic'))

class ChurchTheme(db.Model):
    __tablename__ = 'church_themes'
    
    id = db.Column(db.Integer, primary_key=True)
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=False, unique=True)
    is_custom = db.Column(db.Boolean, default=False)
    
    # Tema Claro
    light_primary = db.Column(db.String(7), default='#4f46e5')
    light_primary_hover = db.Column(db.String(7), default='#4338ca')
    light_secondary = db.Column(db.String(7), default='#64748b')
    light_success = db.Column(db.String(7), default='#10b981')
    light_danger = db.Column(db.String(7), default='#ef4444')
    light_warning = db.Column(db.String(7), default='#f59e0b')
    light_info = db.Column(db.String(7), default='#06b6d4')
    light_bg_main = db.Column(db.String(7), default='#f8fafc')
    light_bg_card = db.Column(db.String(7), default='#ffffff')
    light_text_main = db.Column(db.String(7), default='#1e293b')
    light_text_muted = db.Column(db.String(7), default='#64748b')
    light_border = db.Column(db.String(7), default='#e2e8f0')
    light_sidebar_bg = db.Column(db.String(7), default='#1e293b')
    light_sidebar_text = db.Column(db.String(7), default='#f8fafc')
    light_input_bg = db.Column(db.String(7), default='#ffffff')
    
    # 🔥 NOVOS CAMPOS DE TABELA (TEMA CLARO)
    light_table_header_bg = db.Column(db.String(7), default='#f8fafc')
    light_table_header_text = db.Column(db.String(7), default='#1e293b')
    light_table_row_bg = db.Column(db.String(7), default='#ffffff')
    light_table_row_hover = db.Column(db.String(7), default='#f1f5f9')
    light_table_border = db.Column(db.String(7), default='#e2e8f0')
    
    # Tema Escuro
    dark_primary = db.Column(db.String(7), default='#6366f1')
    dark_primary_hover = db.Column(db.String(7), default='#818cf8')
    dark_secondary = db.Column(db.String(7), default='#94a3b8')
    dark_success = db.Column(db.String(7), default='#34d399')
    dark_danger = db.Column(db.String(7), default='#f87171')
    dark_warning = db.Column(db.String(7), default='#fbbf24')
    dark_info = db.Column(db.String(7), default='#22d3ee')
    dark_bg_main = db.Column(db.String(7), default='#0f172a')
    dark_bg_card = db.Column(db.String(7), default='#1e293b')
    dark_text_main = db.Column(db.String(7), default='#f1f5f9')
    dark_text_muted = db.Column(db.String(7), default='#94a3b8')
    dark_border = db.Column(db.String(7), default='#334155')
    dark_sidebar_bg = db.Column(db.String(7), default='#020617')
    dark_sidebar_text = db.Column(db.String(7), default='#f1f5f9')
    dark_input_bg = db.Column(db.String(7), default='#1e293b')
    
    # 🔥 NOVOS CAMPOS DE TABELA (TEMA ESCURO)
    dark_table_header_bg = db.Column(db.String(7), default='#1e293b')
    dark_table_header_text = db.Column(db.String(7), default='#f1f5f9')
    dark_table_row_bg = db.Column(db.String(7), default='#0f172a')
    dark_table_row_hover = db.Column(db.String(7), default='#1e293b')
    dark_table_border = db.Column(db.String(7), default='#334155')

    # Variáveis específicas do Devocional
    devotional_overlay_light = db.Column(db.Text, default='rgba(0,0,0,0.4)')
    devotional_overlay_dark = db.Column(db.Text, default='rgba(0,0,0,0.6)')
    devotional_text_color = db.Column(db.String(7), default='#ffffff')
    devotional_badge_bg = db.Column(db.String(7), default='#ffffff')
    devotional_badge_text = db.Column(db.String(7), default='#4f46e5')
    devotional_gradient_start = db.Column(db.String(7), default='#4f46e5')
    devotional_gradient_end = db.Column(db.String(7), default='#06b6d4')
    
    # Logos
    logo_light = db.Column(db.String(255), nullable=True)
    logo_dark = db.Column(db.String(255), nullable=True)
    
    # CSS personalizado extra
    custom_css = db.Column(db.Text, nullable=True)
    
    # Metadados
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relacionamento
    church = db.relationship('Church', backref=db.backref('theme', uselist=False))

# ==================== CLASSES PARA CONFIGURACAO DAS CHAVES  ====================

class SystemSetting(db.Model):
    """Configurações do sistema (chaves de API, email, etc.)"""
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    description = db.Column(db.String(255))
    is_encrypted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get(cls, key, default=None):
        setting = cls.query.filter_by(key=key).first()
        return setting.value if setting else default
    
    @classmethod
    def set(cls, key, value, description=None, is_encrypted=False):
        setting = cls.query.filter_by(key=key).first()
        if setting:
            setting.value = value
            if description:
                setting.description = description
            setting.is_encrypted = is_encrypted
        else:
            setting = cls(key=key, value=value, description=description, is_encrypted=is_encrypted)
            db.session.add(setting)
        db.session.commit()
        return setting
    
# ==================== NOVAS CLASSES PARA MÓDULO BANCÁRIO (NÃO ALTERAM O EXISTENTE) ====================

class BankAccount(db.Model):
    __tablename__ = 'bank_accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=False)
    ministry_id = db.Column(db.Integer, db.ForeignKey('ministry.id'), nullable=True)
    bank_name = db.Column(db.String(100), nullable=False)
    account_type = db.Column(db.String(20))
    account_number = db.Column(db.String(50), nullable=False)
    agency = db.Column(db.String(20))
    iban = db.Column(db.String(34))
    swift = db.Column(db.String(20))
    pix_key = db.Column(db.String(100))
    mbway_phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relacionamentos - SEM BACKREFS CONFLITANTES
    church = db.relationship('Church', backref=db.backref('bank_accounts', lazy='dynamic'))
    ministry = db.relationship('Ministry', backref=db.backref('bank_accounts', lazy='dynamic'))


class MBWay(db.Model):
    __tablename__ = 'mbway'
    
    id = db.Column(db.Integer, primary_key=True)
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=False)
    ministry_id = db.Column(db.Integer, db.ForeignKey('ministry.id'), nullable=True)
    phone_number = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos - SEM BACKREFS CONFLITANTES
    church = db.relationship('Church', backref=db.backref('mbway_numbers', lazy='dynamic'))
    ministry = db.relationship('Ministry', backref=db.backref('mbway_numbers', lazy='dynamic'))


class MinistryCategory(db.Model):
    __tablename__ = 'ministry_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    ministry_id = db.Column(db.Integer, db.ForeignKey('ministry.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # 'income', 'expense'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos - SEM BACKREFS CONFLITANTES
    ministry = db.relationship('Ministry', backref=db.backref('custom_categories', lazy='dynamic'))


class MinistryPaymentMethod(db.Model):
    __tablename__ = 'ministry_payment_methods'
    
    id = db.Column(db.Integer, primary_key=True)
    ministry_id = db.Column(db.Integer, db.ForeignKey('ministry.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_electronic = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos - SEM BACKREFS CONFLITANTES
    ministry = db.relationship('Ministry', backref=db.backref('custom_payment_methods', lazy='dynamic'))

class Supplier(db.Model):
    """Fornecedores da igreja (suporte internacional)"""
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    
    # Documentos fiscais (flexível para diferentes países)
    tax_id = db.Column(db.String(30), nullable=True)      # NIF (PT) / CNPJ/CPF (BR)
    tax_id_type = db.Column(db.String(10), default='NIF') # NIF (PT), CNPJ, CPF (BR)
    
    # Contato
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    mobile = db.Column(db.String(50), nullable=True)      # Celular
    website = db.Column(db.String(200), nullable=True)
    
    # Endereço (flexível)
    address = db.Column(db.Text, nullable=True)
    address_number = db.Column(db.String(20), nullable=True)
    complement = db.Column(db.String(100), nullable=True)
    neighborhood = db.Column(db.String(100), nullable=True)  # Bairro (BR) / Freguesia (PT)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(50), nullable=True)       # Estado (BR) / Distrito (PT)
    postal_code = db.Column(db.String(20), nullable=True) # CEP (BR) / Código Postal (PT)
    country = db.Column(db.String(50), default='Portugal')
    
    # Pessoa de contato
    contact_person = db.Column(db.String(100), nullable=True)
    contact_phone = db.Column(db.String(50), nullable=True)
    contact_email = db.Column(db.String(120), nullable=True)
    
    # Dados bancários (opcionais)
    bank_name = db.Column(db.String(100), nullable=True)
    bank_account = db.Column(db.String(50), nullable=True)
    iban = db.Column(db.String(34), nullable=True)        # IBAN (PT/Europa)
    swift = db.Column(db.String(20), nullable=True)       # SWIFT/BIC
    pix_key = db.Column(db.String(100), nullable=True)    # PIX (BR)
    
    # Informações gerais
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # 🔥 RELACIONAMENTOS CORRIGIDOS
    church = db.relationship('Church', backref='suppliers')
    bills = db.relationship('Bill', back_populates='supplier', lazy='dynamic', cascade='all, delete-orphan')
    
    @property
    def formatted_tax_id(self):
        """Retorna o documento formatado conforme o país"""
        if self.tax_id_type == 'NIF' and self.tax_id:
            return self.tax_id
        elif self.tax_id_type == 'CNPJ' and self.tax_id:
            # Formato BR: 00.000.000/0000-00
            return f"{self.tax_id[:2]}.{self.tax_id[2:5]}.{self.tax_id[5:8]}/{self.tax_id[8:12]}-{self.tax_id[12:]}"
        elif self.tax_id_type == 'CPF' and self.tax_id:
            # Formato BR: 000.000.000-00
            return f"{self.tax_id[:3]}.{self.tax_id[3:6]}.{self.tax_id[6:9]}-{self.tax_id[9:]}"
        return self.tax_id


class Bill(db.Model):
    """Contas a pagar (suporte internacional)"""
    __tablename__ = 'bills'
    
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    amount_paid = db.Column(db.Numeric(10, 2), default=0)
    
    # Datas
    issue_date = db.Column(db.Date, default=datetime.utcnow().date)
    due_date = db.Column(db.Date, nullable=False)
    payment_date = db.Column(db.Date, nullable=True)
    
    # Documento fiscal
    invoice_number = db.Column(db.String(50), nullable=True)   # Número da nota fiscal
    invoice_series = db.Column(db.String(10), nullable=True)   # Série (BR)
    nf_access_key = db.Column(db.String(50), nullable=True)    # Chave de acesso (BR)
    
    # Categorização
    category_id = db.Column(db.Integer, db.ForeignKey('transaction_category.id'), nullable=True)
    payment_method_id = db.Column(db.Integer, db.ForeignKey('payment_method.id'), nullable=True)
    bank_account_id = db.Column(db.Integer, db.ForeignKey('bank_accounts.id'), nullable=True)
    
    # Status
    status = db.Column(db.String(20), default='pending')  # pending, partial, paid, overdue, cancelled
    notes = db.Column(db.Text, nullable=True)
    
    # Rastreamento
    church_id = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # 🔥 RELACIONAMENTOS CORRIGIDOS
    supplier = db.relationship('Supplier', back_populates='bills')
    category = db.relationship('TransactionCategory', backref='bills')
    payment_method = db.relationship('PaymentMethod', backref='bills')
    bank_account = db.relationship('BankAccount', backref='bills')
    church = db.relationship('Church', backref='bills')
    created_by_user = db.relationship('User', backref='bills')
    
    @property
    def remaining_amount(self):
        """Valor restante a pagar"""
        return float(self.amount) - float(self.amount_paid)
    
    @property
    def is_overdue(self):
        """Verifica se a conta está vencida"""
        return self.status != 'paid' and self.due_date < datetime.utcnow().date()
    
    @property
    def payment_percentage(self):
        """Percentual pago"""
        if self.amount > 0:
            return (float(self.amount_paid) / float(self.amount)) * 100
        return 0