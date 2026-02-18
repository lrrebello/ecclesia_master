# Arquivo completo: app/modules/auth/routes.py (adicionando foto no register)
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
from flask_mail import Message
from app import mail
from app.core.models import db, User, Church
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid

auth_bp = Blueprint('auth', __name__)

def send_verification_email(user):
    token = str(uuid.uuid4())
    user.email_verification_token = token
    db.session.commit()
    
    # Busca a filial do usuário para pegar o e-mail oficial
    church = Church.query.get(user.church_id) if user.church_id else None
    sender_email = current_app.config.get('MAIL_DEFAULT_SENDER')
    # Se a igreja tiver um e-mail configurado, usamos ele como remetente visual (Reply-To) 
    # mas o remetente técnico deve ser o MAIL_USERNAME para evitar bloqueios de SMTP
    church_name = church.name if church else "Ecclesia Master"

    # Se o servidor de e-mail estiver configurado, tenta enviar
    if current_app.config.get('MAIL_USERNAME'):
        try:
            msg = Message(f'Verifique seu e-mail - {church_name}',
                          sender=(church_name, current_app.config.get('MAIL_USERNAME')),
                          recipients=[user.email])
            if church and church.email:
                msg.reply_to = church.email
                
            link = url_for('auth.verify_email', token=token, _external=True)
            msg.body = f"Olá {user.name},\n\nBem-vindo à {church_name}!\n\nFicamos muito felizes com seu interesse em se juntar a nós. Por favor, clique no link abaixo para verificar seu e-mail e ativar sua conta no sistema Ecclesia Master:\n\n{link}\n\nQue Deus te abençoe ricamente!"
            mail.send(msg)
            current_app.logger.info(f"E-mail de verificação enviado para {user.email}")
        except Exception as e:
            current_app.logger.error(f"Erro SMTP ao enviar e-mail para {user.email}: {str(e)}")
            print(f"Erro ao enviar e-mail: {e}")
            # Se falhar, ainda mostramos o token no console para debug
            print(f"DEBUG: Token de verificação para {user.email}: {token}")
    else:
        print(f"DEBUG: E-mail de verificação para {user.email} (Simulação). Token: {token}")
    
    return token

@auth_bp.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email.lower().strip()).first()
        
        if user:
            if user.is_email_verified:
                flash('Este e-mail já foi verificado. Por favor, faça login.', 'info')
                return redirect(url_for('auth.login'))
            
            token = send_verification_email(user)
            flash('Um novo e-mail de verificação foi enviado. Verifique sua caixa de entrada.', 'success')
            
            if current_app.config.get('DEBUG'):
                flash(f'DEBUG: Link de verificação: {url_for("auth.verify_email", token=token, _external=True)}', 'warning')
                
            return redirect(url_for('auth.login'))
        else:
            flash('E-mail não encontrado no sistema.', 'danger')
            
    return render_template('auth/resend_verification.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('members.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if not user.is_email_verified:
                flash('Por favor, verifique seu e-mail antes de fazer login.', 'warning')
                return redirect(url_for('auth.login'))
            
            if user.status == 'active':
                login_user(user)
                flash('Login bem-sucedido!', 'success')
                return redirect(url_for('members.dashboard'))
            elif user.status == 'pending':
                flash('Sua conta está aguardando aprovação.', 'warning')
            else:
                flash('Sua solicitação de conta foi rejeitada.', 'danger')
        else:
            flash('E-mail ou senha incorretos.', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('members.dashboard'))  # ou sua rota de dashboard

    churches = Church.query.all()  # Carrega para o template (GET e POST)

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        birth_date_str = request.form.get('birth_date')
        gender = request.form.get('gender')
        documents = request.form.get('documents')
        address = request.form.get('address')
        phone = request.form.get('phone')
        church_id_str = request.form.get('church_id')
        
        # Consentimentos
        data_consent = 'data_consent' in request.form
        marketing_consent = 'marketing_consent' in request.form
        
        if not data_consent:
            flash('Você deve aceitar os termos de tratamento de dados para se cadastrar.', 'danger')
            return render_template('auth/register.html', churches=churches)

        # Validação básica antes de prosseguir
        if not name or not email or not password:
            flash('Preencha os campos obrigatórios: nome, e-mail e senha.', 'danger')
            return render_template('auth/register.html', churches=churches)

        # Normaliza e-mail
        email = email.lower().strip()

        # Verifica duplicidade ANTES de criar o objeto
        if User.query.filter_by(email=email).first():
            flash('Este e-mail já está cadastrado. Faça login ou use outro e-mail.', 'danger')
            return render_template('auth/register.html', churches=churches)

        # Processa data de nascimento (com try/except para evitar crash)
        birth_date = None
        if birth_date_str:
            try:
                birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Data de nascimento inválida. Use o formato correto (YYYY-MM-DD).', 'danger')
                return render_template('auth/register.html', churches=churches)

        # Processa igreja
        church_id = None
        if church_id_str and church_id_str.isdigit():
            church_id = int(church_id_str)

        # Upload de foto
        profile_photo = None
        file = request.files.get('profile_photo')
        if file and file.filename:
            filename = secure_filename(file.filename)
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles', filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            file.save(full_path)
            profile_photo = 'uploads/profiles/' + filename

        # Cria o usuário
        new_user = User(
            name=name.strip(),
            email=email,
            birth_date=birth_date,
            gender=gender,
            documents=documents,
            address=address,
            phone=phone,
            profile_photo=profile_photo,
            church_id=church_id,
            status='pending',
            is_email_verified=False,
            data_consent=data_consent,
            data_consent_date=datetime.utcnow(),
            marketing_consent=marketing_consent
        )
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()

            # Enviar e-mail de verificação
            token = send_verification_email(new_user)  # assume que esta função existe e retorna o token

            flash('Cadastro realizado! Por favor, verifique seu e-mail para ativar sua conta.', 'success')
            
            # Debug em dev (mantenho como você tinha)
            if current_app.config.get('DEBUG'):
                flash(f'DEBUG: Clique aqui para verificar (Simulação): {url_for("auth.verify_email", token=token, _external=True)}', 'warning')

            return redirect(url_for('auth.login'))

        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"IntegrityError no registro: {str(e)} - Email duplicado?")
            flash('Este e-mail já está em uso. Por favor escolha outro.', 'danger')
            return render_template('auth/register.html', churches=churches)

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro inesperado no registro: {str(e)}")
            flash('Ocorreu um erro ao criar sua conta. Tente novamente ou contate o suporte.', 'danger')
            return render_template('auth/register.html', churches=churches)

    # GET: apenas renderiza o form
    return render_template('auth/register.html', churches=churches)

@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    user = User.query.filter_by(email_verification_token=token).first_or_404()
    user.is_email_verified = True
    user.email_verification_token = None
    db.session.commit()
    flash('E-mail verificado com sucesso! Agora aguarde a aprovação da liderança.', 'success')
    return redirect(url_for('auth.login'))
    
    # Carrega todas as congregações para garantir que apareçam no registro
    churches = Church.query.all()
    return render_template('auth/register.html', churches=churches)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/approve_member/<int:user_id>', methods=['POST'])
@login_required
def approve_member(user_id):
    if not current_user.can_approve_members and not (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    member = User.query.get_or_404(user_id)
    if member.church_id != current_user.church_id and not is_global_admin():
        flash('Este membro não pertence à sua congregação.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    action = request.form.get('action')
    if action == 'approve':
        member.status = 'active'
        flash('Membro aprovado com sucesso!', 'success')
    elif action == 'reject':
        member.status = 'rejected'
        flash('Solicitação de membro rejeitada.', 'info')
    
    db.session.commit()
    return redirect(request.referrer or url_for('members.dashboard'))

@auth_bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        if current_user.check_password(old_password):
            current_user.set_password(new_password)
            db.session.commit()
            flash('Senha alterada com sucesso!', 'success')
            return redirect(url_for('members.profile'))
        else:
            flash('Senha atual incorreta.', 'danger')
    return render_template('auth/change_password.html')