# Arquivo completo: app/modules/admin/routes.py
# Consolidado com Gestão Global de Membros (filtros/totalizador) e Gestão de Cargos por Filial
# Atualizado para usar campo is_lead_pastor em vez de nome fixo 'Pastor Líder'
# + Nova rota para configuração do layout do cartão de membro

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app.core.models import Church, db, User, ChurchRole
from werkzeug.utils import secure_filename
import os
from datetime import datetime

admin_bp = Blueprint('admin', __name__)

def is_global_admin():
    return current_user.church_role and current_user.church_role.name == 'Administrador Global'

def can_edit_church(church):
    """Verifica se o usuário pode editar dados/layout da congregação"""
    if is_global_admin():
        return True
    if current_user.church_id == church.id and current_user.church_role and current_user.church_role.is_lead_pastor:
        return True
    return False

# ==================== GESTÃO DE CONGREGAÇÕES ====================

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
            is_main=bool(request.form.get('is_main')),
            postal_code=request.form.get('postal_code'),
            concelho=request.form.get('concelho'),
            localidade=request.form.get('localidade')
        )

        file = request.files.get('logo')
        if file and file.filename:
            filename = secure_filename(file.filename)
            logos_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'churches', 'logos')
            os.makedirs(logos_dir, exist_ok=True)
            full_path = os.path.join(logos_dir, filename)
            file.save(full_path)
            new_church.logo_path = f'uploads/churches/logos/{filename}'

        db.session.add(new_church)
        db.session.commit()
        flash('Congregação cadastrada com sucesso!', 'success')
        return redirect(url_for('admin.list_churches'))
        
    return render_template('admin/add_church.html')

@admin_bp.route('/church/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_church(id):
    church = Church.query.get_or_404(id)
    if not can_edit_church(church):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('admin.list_churches'))
    
    if request.method == 'POST':
        country = request.form.get('country', '')
        euro_countries = ['Portugal', 'Espanha', 'França', 'Alemanha', 'Itália', 'Bélgica', 'Holanda', 'Luxemburgo', 'Irlanda', 'Grécia', 'Áustria', 'Finlândia']
        church.currency_symbol = '€' if country in euro_countries else 'R$'
        
        church.name = request.form.get('name')
        church.address = request.form.get('address')
        church.city = request.form.get('city')
        church.country = country
        church.nif = request.form.get('nif')
        church.email = request.form.get('email')
        church.is_main = bool(request.form.get('is_main'))
        church.postal_code = request.form.get('postal_code')
        church.concelho = request.form.get('concelho')
        church.localidade = request.form.get('localidade')

        file = request.files.get('logo')
        if file and file.filename:
            filename = secure_filename(file.filename)
            logos_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'churches', 'logos')
            os.makedirs(logos_dir, exist_ok=True)
            full_path = os.path.join(logos_dir, filename)
            file.save(full_path)
            church.logo_path = f'uploads/churches/logos/{filename}'
        
        card_front = request.files.get('member_card_front')
        if card_front and card_front.filename:
            filename = secure_filename(card_front.filename)
            cards_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'churches', 'member_cards')
            os.makedirs(cards_dir, exist_ok=True)
            full_path = os.path.join(cards_dir, f'front_{church.id}_{filename}')
            card_front.save(full_path)
            church.member_card_front = f'uploads/churches/member_cards/front_{church.id}_{filename}'
        
        card_back = request.files.get('member_card_back')
        if card_back and card_back.filename:
            filename = secure_filename(card_back.filename)
            cards_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'churches', 'member_cards')
            os.makedirs(cards_dir, exist_ok=True)
            full_path = os.path.join(cards_dir, f'back_{church.id}_{filename}')
            card_back.save(full_path)
            church.member_card_back = f'uploads/churches/member_cards/back_{church.id}_{filename}'

        db.session.commit()
        flash('Congregação atualizada!', 'success')
        return redirect(url_for('admin.list_churches'))
    
    return render_template('admin/edit_church.html', church=church)

@admin_bp.route('/church/delete/<int:id>', methods=['POST'])
@login_required
def delete_church(id):
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    church = Church.query.get_or_404(id)
    
    if church.is_main and Church.query.filter_by(is_main=True).count() <= 1:
        if Church.query.count() <= 1:
            flash('Não é possível excluir a única congregação do sistema.', 'warning')
            return redirect(url_for('admin.list_churches'))

    try:
        User.query.filter_by(church_id=id).update({User.church_id: None})
        db.session.delete(church)
        db.session.commit()
        flash(f'Congregação {church.name} excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir congregação: {str(e)}', 'danger')
        
    return redirect(url_for('admin.list_churches'))

@admin_bp.route('/my-church', methods=['GET', 'POST'])
@login_required
def edit_my_church():
    church = current_user.church
    if not church or not can_edit_church(church):
        flash('Acesso negado ou você não está vinculado a nenhuma congregação.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    if request.method == 'POST':
        country = request.form.get('country', '')
        euro_countries = ['Portugal', 'Espanha', 'França', 'Alemanha', 'Itália', 'Bélgica', 'Holanda', 'Luxemburgo', 'Irlanda', 'Grécia', 'Áustria', 'Finlândia']
        church.currency_symbol = '€' if country in euro_countries else 'R$'
        
        church.name = request.form.get('name')
        church.address = request.form.get('address')
        church.city = request.form.get('city')
        church.country = country
        church.nif = request.form.get('nif')
        church.email = request.form.get('email')
        church.postal_code = request.form.get('postal_code')
        church.concelho = request.form.get('concelho')
        church.localidade = request.form.get('localidade')

        file = request.files.get('logo')
        if file and file.filename:
            filename = secure_filename(file.filename)
            logos_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'churches', 'logos')
            os.makedirs(logos_dir, exist_ok=True)
            full_path = os.path.join(logos_dir, filename)
            file.save(full_path)
            church.logo_path = f'uploads/churches/logos/{filename}'
        
        card_front = request.files.get('member_card_front')
        if card_front and card_front.filename:
            filename = secure_filename(card_front.filename)
            cards_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'churches', 'member_cards')
            os.makedirs(cards_dir, exist_ok=True)
            full_path = os.path.join(cards_dir, f'front_{church.id}_{filename}')
            card_front.save(full_path)
            church.member_card_front = f'uploads/churches/member_cards/front_{church.id}_{filename}'
        
        card_back = request.files.get('member_card_back')
        if card_back and card_back.filename:
            filename = secure_filename(card_back.filename)
            cards_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'churches', 'member_cards')
            os.makedirs(cards_dir, exist_ok=True)
            full_path = os.path.join(cards_dir, f'back_{church.id}_{filename}')
            card_back.save(full_path)
            church.member_card_back = f'uploads/churches/member_cards/back_{church.id}_{filename}'

        db.session.commit()
        flash('Dados da congregação atualizados com sucesso!', 'success')
        return redirect(url_for('admin.edit_my_church'))
    
    return render_template('admin/edit_my_church.html', church=church)

# ==================== CONFIGURAÇÃO DO LAYOUT DO CARTÃO DE MEMBRO ====================

@admin_bp.route('/church/<int:church_id>/card-layout', methods=['GET', 'POST'])
@login_required
def edit_card_layout(church_id):
    church = Church.query.get_or_404(church_id)
    
    if not can_edit_church(church):
        flash('Acesso negado. Apenas administradores globais ou pastores líderes desta congregação podem configurar o layout do cartão.', 'danger')
        return redirect(url_for('admin.list_churches'))
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            church.card_front_layout = data.get('front', {})
            church.card_back_layout = data.get('back', {})
            db.session.commit()
            return jsonify({'success': True, 'message': 'Layout do cartão salvo com sucesso!'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return render_template('admin/edit_card_layout.html', church=church)

# ==================== GESTÃO DE MEMBROS ====================

@admin_bp.route('/members')
@login_required
def list_members():
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    church_id = request.args.get('church_id', type=int)
    role_id = request.args.get('role_id', type=int)
    
    query = User.query
    selected_church = None
    selected_role = None
    
    if church_id:
        selected_church = Church.query.get(church_id)
        if selected_church:
            query = query.filter_by(church_id=church_id)
    
    if role_id:
        selected_role = ChurchRole.query.get(role_id)
        if selected_role:
            query = query.filter_by(church_role_id=role_id)
    
    members = query.order_by(User.name).all()
    total_members = len(members)
    
    churches = Church.query.order_by(Church.name).all()
    roles = ChurchRole.query.order_by(ChurchRole.name).all()
    
    return render_template(
        'admin/members.html',
        members=members,
        churches=churches,
        roles=roles,
        selected_church=selected_church,
        selected_role=selected_role,
        current_church_id=church_id,
        current_role_id=role_id,
        total_members=total_members
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
        birth_date_str = request.form.get('birth_date')
        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None
        
        new_user = User(
            name=name,
            email=email,
            birth_date=birth_date,
            documents=request.form.get('documents'),
            address=request.form.get('address'),
            phone=request.form.get('phone'),
            gender=request.form.get('gender'),
            church_id=int(request.form.get('church_id')) if request.form.get('church_id') else None,
            status=request.form.get('status', 'active'),
            postal_code=request.form.get('postal_code'),
            concelho=request.form.get('concelho'),
            localidade=request.form.get('localidade'),
            education_level=request.form.get('education_level')
        )
        new_user.set_password(request.form.get('password'))
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
        return redirect(url_for('admin.list_members'))

    member = User.query.get_or_404(id)
    churches = Church.query.all()
    roles = ChurchRole.query.filter_by(church_id=member.church_id).order_by(ChurchRole.order, ChurchRole.name).all() if member.church_id else []

    if request.method == 'POST':
        member.name = request.form.get('name')
        member.email = request.form.get('email')
        birth_date_str = request.form.get('birth_date')
        member.birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None
        member.gender = request.form.get('gender')
        member.documents = request.form.get('documents')
        member.tax_id = request.form.get('tax_id')
        member.address = request.form.get('address')
        member.phone = request.form.get('phone')
        member.church_id = int(request.form.get('church_id')) if request.form.get('church_id') else None
        member.church_role_id = int(request.form.get('church_role_id')) if request.form.get('church_role_id') else None
        member.status = request.form.get('status', 'active')
        
        member.postal_code = request.form.get('postal_code')
        member.concelho = request.form.get('concelho')
        member.localidade = request.form.get('localidade')
        member.education_level = request.form.get('education_level')
        
        file = request.files.get('profile_photo')
        if file and file.filename:
            filename = secure_filename(file.filename)
            profiles_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles')
            os.makedirs(profiles_dir, exist_ok=True)
            full_path = os.path.join(profiles_dir, filename)
            file.save(full_path)
            member.profile_photo = f'uploads/profiles/{filename}'
        
        db.session.commit()
        flash('Membro atualizado com sucesso!', 'success')
        return redirect(url_for('admin.list_members'))
    
    return render_template('admin/edit_member.html', member=member, churches=churches, roles=roles)

@admin_bp.route('/member/card/<int:id>')
@login_required
def member_card(id):
    member = User.query.get_or_404(id)
    
    is_global = is_global_admin()
    is_lead_pastor = (
        current_user.church_role 
        and current_user.church_role.is_lead_pastor 
        and current_user.church_id == member.church_id
    )
    
    if not (is_global or is_lead_pastor):
        flash('Acesso negado. Você não tem permissão para gerar o cartão deste membro.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    return render_template('admin/member_card.html', member=member)

# ==================== GESTÃO DE CARGOS LOCAIS (Pastor Líder) ====================

@admin_bp.route('/roles')
@login_required
def list_roles():
    if not current_user.church_role or (
        not is_global_admin() and not current_user.church_role.is_lead_pastor
    ):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    roles = ChurchRole.query.filter_by(church_id=current_user.church_id)\
                   .order_by(ChurchRole.order, ChurchRole.name).all()
    return render_template('admin/list_roles.html', roles=roles)


@admin_bp.route('/role/add', methods=['GET', 'POST'])
@login_required
def add_role():
    if not current_user.church_role or (
        not is_global_admin() and not current_user.church_role.is_lead_pastor
    ):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('admin.list_roles'))
    
    if request.method == 'POST':
        new_role = ChurchRole(
            name=request.form.get('name'),
            description=request.form.get('description'),
            order=int(request.form.get('order') or 0),
            church_id=current_user.church_id,
            is_lead_pastor='is_lead_pastor' in request.form,
            is_active=True
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
    
    if not current_user.church_role or (
        not is_global_admin() 
        and (not current_user.church_role.is_lead_pastor or role.church_id != current_user.church_id)
    ):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('admin.list_roles'))
    
    if request.method == 'POST':
        role.name = request.form.get('name')
        role.description = request.form.get('description')
        role.order = int(request.form.get('order') or 0)
        role.is_active = 'is_active' in request.form
        role.is_lead_pastor = 'is_lead_pastor' in request.form
        db.session.commit()
        flash('Cargo atualizado!', 'success')
        return redirect(url_for('admin.list_roles'))
    
    return render_template('admin/edit_role.html', role=role)


@admin_bp.route('/role/delete/<int:id>')
@login_required
def delete_role(id):
    role = ChurchRole.query.get_or_404(id)
    
    if not current_user.church_role or (
        not is_global_admin() 
        and (not current_user.church_role.is_lead_pastor or role.church_id != current_user.church_id)
    ):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('admin.list_roles'))
    
    db.session.delete(role)
    db.session.commit()
    flash('Cargo excluído com sucesso!', 'success')
    return redirect(url_for('admin.list_roles'))

# ==================== GESTÃO DE CARGOS POR FILIAL (ADMIN GLOBAL) ====================

@admin_bp.route('/church-roles')
@login_required
def list_church_roles():
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    churches = Church.query.order_by(Church.name).all()
    return render_template('admin/church_roles_select.html', churches=churches)


@admin_bp.route('/church-roles/<int:church_id>')
@login_required
def list_church_roles_by_id(church_id):
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    church = Church.query.get_or_404(church_id)
    roles = ChurchRole.query.filter_by(church_id=church_id)\
                   .order_by(ChurchRole.order, ChurchRole.name).all()
    
    return render_template('admin/church_roles_list.html', church=church, roles=roles)


@admin_bp.route('/church-roles/<int:church_id>/add', methods=['GET', 'POST'])
@login_required
def add_church_role(church_id):
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    church = Church.query.get_or_404(church_id)
    
    if request.method == 'POST':
        new_role = ChurchRole(
            name=request.form.get('name'),
            description=request.form.get('description'),
            order=int(request.form.get('order') or 0),
            church_id=church_id,
            is_lead_pastor='is_lead_pastor' in request.form,
            is_active=True
        )
        db.session.add(new_role)
        db.session.commit()
        flash('Cargo criado com sucesso!', 'success')
        return redirect(url_for('admin.list_church_roles_by_id', church_id=church_id))
    
    return render_template('admin/add_church_role.html', church=church)


@admin_bp.route('/church-roles/<int:church_id>/edit/<int:role_id>', methods=['GET', 'POST'])
@login_required
def edit_church_role(church_id, role_id):
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    church = Church.query.get_or_404(church_id)
    role = ChurchRole.query.get_or_404(role_id)
    
    if role.church_id != church_id:
        flash('Cargo não encontrado nesta congregação.', 'danger')
        return redirect(url_for('admin.list_church_roles_by_id', church_id=church_id))
    
    if request.method == 'POST':
        role.name = request.form.get('name')
        role.description = request.form.get('description')
        role.order = int(request.form.get('order') or 0)
        role.is_active = 'is_active' in request.form
        role.is_lead_pastor = 'is_lead_pastor' in request.form
        db.session.commit()
        flash('Cargo atualizado!', 'success')
        return redirect(url_for('admin.list_church_roles_by_id', church_id=church_id))
    
    return render_template('admin/edit_church_role.html', church=church, role=role)


@admin_bp.route('/church-roles/<int:church_id>/delete/<int:role_id>')
@login_required
def delete_church_role(church_id, role_id):
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    church = Church.query.get_or_404(church_id)
    role = ChurchRole.query.get_or_404(role_id)
    
    if role.church_id != church_id:
        flash('Cargo não encontrado nesta congregação.', 'danger')
        return redirect(url_for('admin.list_church_roles_by_id', church_id=church_id))
    
    db.session.delete(role)
    db.session.commit()
    flash('Cargo excluído com sucesso!', 'success')
    return redirect(url_for('admin.list_church_roles_by_id', church_id=church_id))