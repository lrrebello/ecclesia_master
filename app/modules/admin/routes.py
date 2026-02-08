from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.core.models import Church, db, User, ChurchRole

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/churches')
@login_required
def list_churches():
    if not current_user.church_role or current_user.church_role.name != 'Administrador Global':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    churches = Church.query.all()
    return render_template('admin/churches.html', churches=churches)

@admin_bp.route('/church/add', methods=['GET', 'POST'])
@login_required
def add_church():
    if not current_user.church_role or current_user.church_role.name != 'Administrador Global':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    if request.method == 'POST':
        new_church = Church(
            name=request.form.get('name'),
            address=request.form.get('address'),
            city=request.form.get('city'),
            country=request.form.get('country'),
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
    if not current_user.church_role or current_user.church_role.name != 'Administrador Global':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    church = Church.query.get_or_404(id)
    if request.method == 'POST':
        church.name = request.form.get('name')
        church.address = request.form.get('address')
        church.city = request.form.get('city')
        church.country = request.form.get('country')
        church.is_main = True if request.form.get('is_main') else False
        db.session.commit()
        flash('Congregação atualizada!', 'success')
        return redirect(url_for('admin.list_churches'))
    
    return render_template('admin/edit_church.html', church=church)

@admin_bp.route('/members')
@login_required
def list_members():
    if not current_user.church_role or current_user.church_role.name != 'Administrador Global':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    members = User.query.all()
    return render_template('admin/members.html', members=members)

@admin_bp.route('/member/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_member(id):
    if not current_user.church_role or current_user.church_role.name != 'Administrador Global':
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
        db.session.commit()
        flash('Membro atualizado com sucesso!', 'success')
        return redirect(url_for('admin.list_members'))
    
    return render_template('admin/edit_member.html', member=member, churches=churches, roles=roles)

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