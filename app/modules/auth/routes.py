from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.core.models import User, Church, db
from datetime import datetime

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
            if user.status == 'pending':
                flash('Seu cadastro ainda está em análise pela liderança.', 'warning')
                return redirect(url_for('auth.login'))
            if user.status == 'rejected':
                flash('Seu cadastro não foi aprovado. Entre em contato com a secretaria.', 'danger')
                return redirect(url_for('auth.login'))
            login_user(user, remember=True)
            return redirect(url_for('members.dashboard'))
        flash('E-mail ou senha incorretos.', 'danger')
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        if User.query.filter_by(email=email).first():
            flash('E-mail já cadastrado.', 'danger')
            return redirect(url_for('auth.register'))
            
        new_user = User(
            name=request.form.get('name'),
            email=email,
            birth_date=datetime.strptime(request.form.get('birth_date'), '%Y-%m-%d').date(),
            gender=request.form.get('gender'),
            documents=request.form.get('documents'),
            address=request.form.get('address'),
            phone=request.form.get('phone'),
            church_id=request.form.get('church_id'),
            status='pending'
        )
        new_user.set_password(request.form.get('password'))
        db.session.add(new_user)
        db.session.commit()
        flash('Solicitação enviada com sucesso! Aguarde a aprovação da liderança.', 'success')
        return redirect(url_for('auth.login'))
        
    churches = Church.query.all()
    return render_template('auth/register.html', churches=churches)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

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

# Rota de Aprovação (Acessível por Admin e Pastor Líder)
@auth_bp.route('/admin/approve/<int:user_id>/<string:action>')
@login_required
def approve_member(user_id, action):
    # Verifica se o usuário tem permissão (usando o novo campo church_role)
    if not current_user.church_role or current_user.church_role.name not in ['Administrador Global', 'Pastor Líder']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
        
    user = User.query.get_or_404(user_id)
    
    # Garante que o aprovador só aprove/rejeite membros da própria filial (exceto admin global)
    if current_user.church_role.name != 'Administrador Global' and user.church_id != current_user.church_id:
        flash('Você não tem permissão para aprovar membros de outras congregações.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    if action == 'approve':
        user.status = 'active'
        flash(f'Membro {user.name} aprovado com sucesso!', 'success')
    elif action == 'reject':
        user.status = 'rejected'
        flash(f'Membro {user.name} rejeitado.', 'warning')
    else:
        flash('Ação inválida.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    db.session.commit()
    return redirect(request.referrer or url_for('members.dashboard'))