# Arquivo completo: app/modules/auth/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
from flask_mail import Message
from app.core.models import db, User, Church
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid

auth_bp = Blueprint('auth', __name__)

def send_verification_email(user):
    # Importação local para evitar ciclo
    from app import mail
    
    token = str(uuid.uuid4())
    user.email_verification_token = token
    db.session.commit()
    
    # Busca apenas o nome da igreja para o assunto do e-mail
    church = Church.query.get(user.church_id) if user.church_id else None
    church_name = church.name if church else "Ecclesia Master"

    # Pega o remetente padrão configurado no .env
    default_sender = current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('MAIL_USERNAME')

    # Se o servidor de e-mail estiver configurado, tenta enviar
    if current_app.config.get('MAIL_USERNAME'):
        try:
            msg = Message(f'Verifique seu e-mail - {church_name}',
                          sender=default_sender,
                          recipients=[user.email])
            
            link = url_for('auth.verify_email', token=token, _external=True)
            msg.body = f"Olá {user.name},\n\nBem-vindo à {church_name}!\n\nFicamos muito felizes com seu interesse em se juntar a nós. Por favor, clique no link abaixo para verificar seu e-mail e ativar sua conta no sistema Ecclesia Master:\n\n{link}\n\nQue Deus te abençoe ricamente!"
            
            mail.send(msg)
            print(f"✓ E-mail enviado com sucesso para {user.email} via {default_sender}")
        except Exception as e:
            print(f"✗ Erro crítico ao enviar e-mail: {str(e)}")
            # Em desenvolvimento, mostramos o token no console caso o e-mail falhe
            print(f"DEBUG: Token de verificação para {user.email}: {token}")
    else:
        print(f"AVISO: MAIL_USERNAME não configurado. Simulando envio.")
        print(f"DEBUG: E-mail de verificação para {user.email}. Token: {token}")
    
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
        
        birth_date_str = request.form.get('birth_date')
        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None
        
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
            upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles')
            os.makedirs(upload_path, exist_ok=True)
            file.save(os.path.join(upload_path, filename))
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
        # Em produção, você pode remover a linha abaixo que mostra o link de simulação
        flash(f'DEBUG: Clique aqui para verificar (Simulação): {url_for("auth.verify_email", token=token, _external=True)}', 'warning')
        
        return redirect(url_for('auth.login'))
    
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

@auth_bp.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            if user.is_email_verified:
                flash('Este e-mail já foi verificado. Faça login normalmente.', 'info')
            else:
                token = send_verification_email(user)
                flash('Novo e-mail de verificação enviado!', 'success')
                flash(f'DEBUG: Clique aqui para verificar (Simulação): {url_for("auth.verify_email", token=token, _external=True)}', 'warning')
        else:
            flash('E-mail não encontrado.', 'danger')
        return redirect(url_for('auth.login'))
    return render_template('auth/resend_verification.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/approve_member/<int:user_id>', methods=['POST'])
@login_required
def approve_member(user_id):
    member = User.query.get_or_404(user_id)
    action = request.form.get('action')
    if action == 'approve':
        member.status = 'active'
        flash('Membro aprovado com sucesso!', 'success')
    elif action == 'reject':
        member.status = 'rejected'
        flash('Solicitação de membro rejeitada.', 'info')
    db.session.commit()
    return redirect(request.referrer or url_for('members.dashboard'))
