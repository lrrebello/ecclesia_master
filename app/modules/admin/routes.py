# Arquivo completo: app/modules/admin/routes.py (adicionando rota para add_user)
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app.core.models import Church, db, User, ChurchRole
from werkzeug.utils import secure_filename
import os
from datetime import datetime

admin_bp = Blueprint('admin', __name__)

def is_global_admin():
    return current_user.church_role and current_user.church_role.name == 'Administrador Global'

@admin_bp.route('/churches')
@login_required
def list_churches():
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    churches = Church.query.all()
    return render_template('admin/churches.html', churches=churches)

@admin_bp.route('/church/add', methods=['GET', 'POST'])
@login_required
def add_church():
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    if request.method == 'POST':
        country = request.form.get('country', '')
        # Mapeamento robusto de moedas
        euro_countries = ['Portugal', 'Espanha', 'França', 'Alemanha', 'Itália', 'Bélgica', 'Holanda', 'Luxemburgo', 'Irlanda', 'Grécia', 'Áustria', 'Finlândia']
        currency = '€' if country in euro_countries else 'R$'
        
        new_church = Church(
            name=request.form.get('name'),
            address=request.form.get('address'),
            city=request.form.get('city'),
            country=country,
            nif=request.form.get('nif'),
            email=request.form.get('email'),
            currency_symbol=currency,
            is_main=True if request.form.get('is_main') else False
        )
        db.session.add(new_church)
        db.session.commit()
        flash('Congregação cadastrada com sucesso!', 'success')
        return redirect(url_for('admin.list_churches'))
    
    return render_template('admin/add_church.html')

@admin_bp.route('/church/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_church(id):
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('admin.list_churches'))
    
    church = Church.query.get_or_404(id)
    
    if request.method == 'POST':
        country = request.form.get('country', '')
        # Atualiza a moeda se o país mudar
        euro_countries = ['Portugal', 'Espanha', 'França', 'Alemanha', 'Itália', 'Bélgica', 'Holanda', 'Luxemburgo', 'Irlanda', 'Grécia', 'Áustria', 'Finlândia']
        church.currency_symbol = '€' if country in euro_countries else 'R$'
        
        church.name = request.form.get('name')
        church.address = request.form.get('address')
        church.city = request.form.get('city')
        church.country = country
        church.nif = request.form.get('nif')
        church.email = request.form.get('email')
        church.is_main = 'is_main' in request.form
        db.session.commit()
        flash('Congregação atualizada!', 'success')
        return redirect(url_for('admin.list_churches'))
    
    return render_template('admin/edit_church.html', church=church)

@admin_bp.route('/members')
@login_required
def list_members():
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    church_id = request.args.get('church_id', type=int)
    churches = Church.query.order_by(Church.name).all()
    
    if church_id:
        selected_church = Church.query.get(church_id)
        if selected_church:
            members = User.query.filter_by(church_id=church_id).order_by(User.name).all()
        else:
            members = []
            flash('Congregação não encontrada.', 'warning')
    else:
        selected_church = None
        members = User.query.order_by(User.name).all()
    
    return render_template(
        'admin/members.html',
        members=members,
        churches=churches,
        selected_church=selected_church,
        current_church_id=church_id
    )

@admin_bp.route('/member/add', methods=['GET', 'POST'])
@login_required
def add_member():
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('admin.list_members'))
    
    churches = Church.query.all()
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        birth_date = datetime.strptime(request.form.get('birth_date'), '%Y-%m-%d').date() if request.form.get('birth_date') else None
        gender = request.form.get('gender')
        documents = request.form.get('documents')
        address = request.form.get('address')
        phone = request.form.get('phone')
        church_id = int(request.form.get('church_id')) if request.form.get('church_id') else None
        status = request.form.get('status', 'active')
        
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
            church_id=church_id,
            status=status
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Membro criado com sucesso!', 'success')
        return redirect(url_for('admin.list_members'))
    
    return render_template('admin/add_member.html', churches=churches)

@admin_bp.route('/member/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_member(id):
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    member = User.query.get_or_404(id)
    churches = Church.query.all()
    roles = ChurchRole.query.filter_by(church_id=member.church_id).order_by(ChurchRole.order, ChurchRole.name).all() if member.church_id else []
    
    if request.method == 'POST':
        member.name = request.form.get('name')
        member.email = request.form.get('email')
        member.church_role_id = int(request.form.get('church_role_id')) if request.form.get('church_role_id') else None
        member.church_id = int(request.form.get('church_id')) if request.form.get('church_id') else None
        member.status = request.form.get('status')
        member.birth_date = datetime.strptime(request.form.get('birth_date'), '%Y-%m-%d').date() if request.form.get('birth_date') else member.birth_date
        member.gender = request.form.get('gender')
        member.documents = request.form.get('documents')
        member.tax_id = request.form.get('tax_id')
        member.address = request.form.get('address')
        member.phone = request.form.get('phone')
        
        file = request.files.get('profile_photo')
        if file:
            filename = secure_filename(file.filename)
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles', filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            file.save(full_path)
            member.profile_photo = 'uploads/profiles/' + filename
        
        db.session.commit()
        flash('Membro atualizado com sucesso!', 'success')
        return redirect(url_for('admin.list_members'))
    
    return render_template('admin/edit_member.html', member=member, churches=churches, roles=roles)

# ... (restante igual ao seu TXT)

@admin_bp.route('/roles')
@login_required
def list_roles():
    if not current_user.church_role or current_user.church_role.name not in ['Administrador Global', 'Pastor Líder']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    roles = ChurchRole.query.filter_by(church_id=current_user.church_id).order_by(ChurchRole.order, ChurchRole.name).all()
    return render_template('admin/list_roles.html', roles=roles)

@admin_bp.route('/role/add', methods=['GET', 'POST'])
@login_required
def add_role():
    if not current_user.church_role or current_user.church_role.name not in ['Administrador Global', 'Pastor Líder']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('admin.list_roles'))
    
    if request.method == 'POST':
        new_role = ChurchRole(
            name=request.form.get('name'),
            description=request.form.get('description'),
            order=int(request.form.get('order')) if request.form.get('order') else 0,
            church_id=current_user.church_id
        )
        db.session.add(new_role)
        db.session.commit()
        flash('Cargo criado com sucesso!', 'success')
        return redirect(url_for('admin.list_roles'))
    
    return render_template('admin/add_role.html')

@admin_bp.route('/role/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_role(id):
    role = ChurchRole.query.get_or_404(id)
    
    if not current_user.church_role or current_user.church_role.name not in ['Administrador Global', 'Pastor Líder'] or role.church_id != current_user.church_id:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('admin.list_roles'))
    
    if request.method == 'POST':
        role.name = request.form.get('name')
        role.description = request.form.get('description')
        role.order = int(request.form.get('order')) if request.form.get('order') else 0
        role.is_active = 'is_active' in request.form
        db.session.commit()
        flash('Cargo atualizado!', 'success')
        return redirect(url_for('admin.list_roles'))
    
    return render_template('admin/edit_role.html', role=role)

@admin_bp.route('/role/delete/<int:id>')
@login_required
def delete_role(id):
    role = ChurchRole.query.get_or_404(id)
    
    if not current_user.church_role or current_user.church_role.name not in ['Administrador Global', 'Pastor Líder'] or role.church_id != current_user.church_id:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('admin.list_roles'))
    
    db.session.delete(role)
    db.session.commit()
    flash('Cargo excluído com sucesso!', 'success')
    return redirect(url_for('admin.list_roles'))
