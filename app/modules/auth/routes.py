# app/modules/auth/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
from app.core.models import db, User, Church
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid

# SendGrid imports
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

auth_bp = Blueprint('auth', __name__)

def send_verification_email(user):
    """
    Envia email de verificação usando SendGrid API (não SMTP).
    Retorna o token gerado ou None em caso de erro.
    """
    # Gera novo token se necessário (mas você já gera antes de chamar)
    token = user.email_verification_token
    if not token:
        token = str(uuid.uuid4())
        user.email_verification_token = token
        db.session.commit()

    # Busca nome da igreja para personalizar
    church = Church.query.get(user.church_id) if user.church_id else None
    church_name = church.name if church else "Ecclesia Master"

    # URL de verificação
    verification_url = url_for('auth.verify_email', token=token, _external=True)

    # Mensagem HTML bonita e simples
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6;">
        <h2>Olá {user.name},</h2>
        <p>Bem-vindo à <strong>{church_name}</strong>!</p>
        <p>Ficamos muito felizes com seu interesse em se juntar a nós.</p>
        <p>Para ativar sua conta no sistema Ecclesia Master, clique no botão abaixo:</p>
        <p style="text-align: center; margin: 30px 0;">
            <a href="{verification_url}" 
               style="background-color: #4CAF50; color: white; padding: 12px 24px; 
                      text-decoration: none; border-radius: 5px; font-size: 16px;">
                Verificar Meu Email Agora
            </a>
        </p>
        <p>Se o botão não funcionar, copie e cole este link no navegador:</p>
        <p><a href="{verification_url}">{verification_url}</a></p>
        <p>Este link expira em 24 horas.</p>
        <p>Que Deus te abençoe ricamente!</p>
        <p>Atenciosamente,<br>Equipe {church_name}</p>
    </body>
    </html>
    """

    message = Mail(
        from_email='adjesus.sede@gmail.com',  # Seu email verificado no SendGrid
        to_emails=user.email,
        subject=f'Verifique seu e-mail - {church_name}',
        html_content=html_content
    )

    try:
        sg = SendGridAPIClient(current_app.config.get('SENDGRID_API_KEY'))
        response = sg.send(message)
        current_app.logger.info(f"Email de verificação enviado para {user.email} - Status: {response.status_code}")
        print(f"✓ Email enviado com sucesso para {user.email} via SendGrid")
        return token
    except Exception as e:
        current_app.logger.error(f"Erro ao enviar email via SendGrid: {str(e)}")
        print(f"✗ Erro ao enviar email: {str(e)}")
        # Em dev, mostra o link de simulação
        flash(f'DEBUG (envio falhou): Clique aqui para verificar: {verification_url}', 'warning')
        return token  # Retorna token mesmo com erro para debug

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('members.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            # Verificação de e-mail desativada temporariamente conforme solicitado
            # if not user.is_email_verified:
            #     flash('Por favor, verifique seu e-mail antes de fazer login.', 'warning')
            #     return redirect(url_for('auth.login'))
            
            if user.status == 'active':
                login_user(user)
                flash('Login bem-sucedido!', 'success')
                return redirect(url_for('members.dashboard'))
            elif user.status == 'pending':
                flash('Sua conta está aguardando aprovação da liderança.', 'warning')
            else:
                flash('Sua solicitação de conta foi rejeitada.', 'danger')
        else:
            flash('E-mail ou senha incorretos.', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/register/select-church')
def select_church():
    churches = Church.query.all()
    return render_template('auth/select_church.html', churches=churches)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    church_id = request.args.get('church_id') or request.form.get('church_id')
    
    if not church_id:
        return redirect(url_for('auth.select_church'))
    
    church = Church.query.get_or_404(church_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        birth_date_str = request.form.get('birth_date')
        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None
        
        baptism_date_str = request.form.get('baptism_date')
        baptism_date = datetime.strptime(baptism_date_str, '%Y-%m-%d').date() if baptism_date_str else None
        
        gender = request.form.get('gender')
        tax_id = request.form.get('tax_id') # CPF ou NIF
        address = request.form.get('address')
        phone = request.form.get('phone')
        
        # Consentimento RGPD/LGPD
        data_consent = 'data_consent' in request.form
        marketing_consent = 'marketing_consent' in request.form
        
        if not data_consent:
            flash('Você deve aceitar os termos de tratamento de dados para se cadastrar.', 'danger')
            return render_template('auth/register.html', church=church)

        # Upload de foto
        profile_photo = None
        file = request.files.get('profile_photo')
        if file and file.filename:
            filename = secure_filename(file.filename)
            upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles')
            os.makedirs(upload_path, exist_ok=True)
            file.save(os.path.join(upload_path, filename))
            profile_photo = 'uploads/profiles/' + filename
        
        new_user = User(
            name=name.strip() if name else '',
            email=email.lower().strip() if email else '',
            birth_date=birth_date,
            baptism_date=baptism_date,
            gender=gender,
            tax_id=tax_id,
            address=address,
            phone=phone,
            profile_photo=profile_photo,
            church_id=church.id,
            status='pending',
            data_consent=data_consent,
            data_consent_date=datetime.utcnow(),
            marketing_consent=marketing_consent,
            is_email_verified=True # Definido como True por padrão enquanto a verificação está desativada
        )
        new_user.set_password(password)

        # Gera token antes de commit (mantido para compatibilidade futura)
        token = str(uuid.uuid4())
        new_user.email_verification_token = token

        db.session.add(new_user)
        db.session.commit()
        
        # Envio de e-mail desativado temporariamente conforme solicitado
        # send_verification_email(new_user)
        
        flash('Cadastro realizado com sucesso! Agora aguarde a aprovação da liderança para acessar o sistema.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', church=church)

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
                # token = send_verification_email(user)
                flash('A verificação de e-mail está desativada no momento.', 'info')
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

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not current_user.check_password(old_password):
            flash('Senha atual incorreta.', 'danger')
        elif new_password != confirm_password:
            flash('As novas senhas não coincidem.', 'danger')
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Senha alterada com sucesso!', 'success')
            return redirect(url_for('members.profile'))
            
    return render_template('auth/change_password.html')
