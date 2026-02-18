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
    sender_email = church.email if church and church.email else current_app.config.get('MAIL_DEFAULT_SENDER')
    church_name = church.name if church else "Ecclesia Master"

    # Se o servidor de e-mail estiver configurado, tenta enviar
    if current_app.config.get('MAIL_USERNAME'):
        try:
            msg = Message(f'Verifique seu e-mail - {church_name}',
                          sender=sender_email,
                          recipients=[user.email])
            link = url_for('auth.verify_email', token=token, _external=True)
            msg.body = f"Olá {user.name},\n\nBem-vindo à {church_name}!\n\nFicamos muito felizes com seu interesse em se juntar a nós. Por favor, clique no link abaixo para verificar seu e-mail e ativar sua conta no sistema Ecclesia Master:\n\n{link}\n\nQue Deus te abençoe ricamente!"
            mail.send(msg)
        except Exception as e:
            print(f"Erro ao enviar e-mail via {sender_email}: {e}")
            # Se falhar, ainda mostramos o token no console para debug
            print(f"DEBUG: Token de verificação para {user.email}: {token}")
    else:
        print(f"DEBUG: E-mail de verificação para {user.email} (Remetente: {sender_email}). Token: {token}")
    
    return token

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
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        birth_date = datetime.strptime(request.form.get('birth_date'), '%Y-%m-%d').date()
        gender = request.form.get('gender')
        documents = request.form.get('documents')
        address = request.form.get('address')
        phone = request.form.get('phone')
        church_id = request.form.get('church_id')
        
        # Consentimento RGPD/LGPD
        data_consent = True if request.form.get('data_consent') else False
        marketing_consent = True if request.form.get('marketing_consent') else False
        
        if not data_consent:
            flash('Você deve aceitar os termos de tratamento de dados para se cadastrar.', 'danger')
            return redirect(url_for('auth.register'))

        # Upload de foto
        file = request.files.get('profile_photo')
        profile_photo = None
        if file:
            filename = secure_filename(file.filename)
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles', filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            file.save(full_path)
            profile_photo = 'uploads/profiles/' + filename
        
        new_user = User(
            name=name,
            email=email,
            birth_date=birth_date,
            gender=gender,
            documents=documents,
            address=address,
            phone=phone,
            profile_photo=profile_photo,
            church_id=int(church_id) if church_id else None,
            status='pending',
            data_consent=data_consent,
            data_consent_date=datetime.utcnow(),
            marketing_consent=marketing_consent
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        # Enviar e-mail de verificação
        token = send_verification_email(new_user)
        
        flash('Cadastro realizado! Por favor, verifique seu e-mail para ativar sua conta.', 'info')
        # Em ambiente de desenvolvimento, vamos facilitar o teste:
        flash(f'DEBUG: Clique aqui para verificar (Simulação): {url_for("auth.verify_email", token=token, _external=True)}', 'warning')
        
        return redirect(url_for('auth.login'))
    
    # Carrega todas as congregações para o formulário de registro
    churches = Church.query.all()
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