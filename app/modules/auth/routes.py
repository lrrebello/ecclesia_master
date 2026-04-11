from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
from app.core.models import db, User, Church
from app.utils.logger import log_action
from app.utils.email_utils import send_verification_email_via_smtp
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('members.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if user.status == 'active':
                # Verificar se email foi verificado
                if not user.is_email_verified:
                    flash('Por favor, verifique seu e-mail antes de fazer login. Verifique sua caixa de entrada e spam.', 'warning')
                    return redirect(url_for('auth.login'))
                
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
        email = request.form.get('email').lower().strip()
        
        # Verificar se e-mail já existe
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Este e-mail já está cadastrado no sistema.', 'danger')
            return render_template('auth/register.html', church=church)
        
        name = request.form.get('name')
        password = request.form.get('password')
        
        birth_date_str = request.form.get('birth_date')
        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None
        
        baptism_date_str = request.form.get('baptism_date')
        baptism_date = datetime.strptime(baptism_date_str, '%Y-%m-%d').date() if baptism_date_str else None
        
        gender = request.form.get('gender')
        marital_status = request.form.get('marital_status')
        spouse_name = request.form.get('spouse_name')
        tax_id = request.form.get('tax_id')
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
        
        token = str(uuid.uuid4())
        
        new_user = User(
            name=name.strip() if name else '',
            email=email,
            birth_date=birth_date,
            baptism_date=baptism_date,
            gender=gender,
            marital_status=marital_status,
            spouse_name=spouse_name if marital_status == 'Casado(a)' else None,
            tax_id=tax_id,
            address=address,
            phone=phone,
            profile_photo=profile_photo,
            church_id=church.id,
            status='pending',
            data_consent=data_consent,
            data_consent_date=datetime.utcnow(),
            marketing_consent=marketing_consent,
            is_email_verified=False,  # Agora exige verificação
            email_verification_token=token
        )
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()
        
        # Enviar email de verificação
        success, message = send_verification_email_via_smtp(new_user)
        
        if success:
            flash('Cadastro realizado! Enviamos um link de verificação para seu e-mail. Verifique sua caixa de entrada e também a pasta de spam.', 'success')
        else:
            flash(f'Cadastro realizado, mas não foi possível enviar o email de verificação: {message}. Entre em contato com o administrador.', 'warning')
                
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', church=church)


@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    user = User.query.filter_by(email_verification_token=token).first_or_404()
    user.is_email_verified = True
    user.email_verification_token = None
    db.session.commit()
    
    log_action(
        action='VERIFY_EMAIL',
        module='AUTH',
        description=f"E-mail verificado: {user.name}",
        new_values={'user_id': user.id, 'email': user.email},
        church_id=user.church_id
    )
    
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
                success, message = send_verification_email_via_smtp(user)
                if success:
                    flash('Um novo link de verificação foi enviado para seu e-mail!', 'success')
                else:
                    flash(f'Erro ao enviar email: {message}', 'danger')
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
    old_status = member.status
    
    if action == 'approve':
        member.status = 'active'
        
        log_action(
            action='APPROVE',
            module='MEMBERS',
            description=f"Membro aprovado: {member.name}",
            old_values={'status': old_status},
            new_values={'status': 'active', 'id': member.id, 'name': member.name},
            church_id=member.church_id
        )
        
        flash('Membro aprovado com sucesso!', 'success')
        
    elif action == 'reject':
        member.status = 'rejected'
        
        log_action(
            action='REJECT',
            module='MEMBERS',
            description=f"Membro rejeitado: {member.name}",
            old_values={'status': old_status},
            new_values={'status': 'rejected', 'id': member.id, 'name': member.name},
            church_id=member.church_id
        )
        
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
            
            log_action(
                action='CHANGE_PASSWORD',
                module='AUTH',
                description=f"Senha alterada: {current_user.name}",
                new_values={'user_id': current_user.id},
                church_id=current_user.church_id
            )
            
            flash('Senha alterada com sucesso!', 'success')
            return redirect(url_for('members.profile'))
            
    return render_template('auth/change_password.html')