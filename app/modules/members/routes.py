from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.core.models import User, Church, Ministry, Event, db, Devotional, Study, ChurchRole
from datetime import datetime
from sqlalchemy import func

members_bp = Blueprint('members', __name__)


def can_manage_members():
    return current_user.can_approve_members or (
        current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']
    )


def can_manage_ministries():
    return current_user.can_manage_ministries or (
        current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']
    )


@members_bp.route('/dashboard')
@login_required
def dashboard():
    latest_devotional = Devotional.query.order_by(Devotional.date.desc()).first()
    recent_studies = Study.query.order_by(Study.created_at.desc()).limit(3).all()

    ministry_ids = [m.id for m in current_user.ministries]
    personal_agenda = Event.query.filter(
        (Event.church_id == current_user.church_id) &
        ((Event.ministry_id == None) | (Event.ministry_id.in_(ministry_ids)))
    ).order_by(Event.start_time.asc()).all()

    pending_members = []
    if can_manage_members():
        pending_members = User.query.filter_by(
            church_id=current_user.church_id, status='pending'
        ).all()

    return render_template(
        'members/dashboard.html',
        devotional=latest_devotional,
        studies=recent_studies,
        agenda=personal_agenda,
        pending_members=pending_members,
        datetime=datetime
    )


@members_bp.route('/profile')
@login_required
def profile():
    return render_template('members/profile.html')


@members_bp.route('/ministries')
@login_required
def list_ministries():
    if current_user.church_role and current_user.church_role.name == 'Administrador Global':
        ministries = Ministry.query.all()
    elif can_manage_ministries():
        ministries = Ministry.query.filter_by(church_id=current_user.church_id).all()
    else:
        ministries = current_user.ministries

    return render_template('members/ministries.html', ministries=ministries)


@members_bp.route('/ministry/add', methods=['GET', 'POST'])
@login_required
def add_ministry():
    if not can_manage_ministries():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.list_ministries'))

    if request.method == 'POST':
        leader_id = request.form.get('leader_id')
        new_min = Ministry(
            name=request.form.get('name'),
            description=request.form.get('description'),
            church_id=current_user.church_id,
            leader_id=int(leader_id) if leader_id else None
        )
        db.session.add(new_min)
        db.session.commit()

        if leader_id:
            leader = User.query.get(int(leader_id))
            new_min.members.append(leader)
            db.session.commit()

        flash('Ministério criado com sucesso!', 'success')
        return redirect(url_for('members.list_ministries'))

    potential_leaders = User.query.filter_by(
        church_id=current_user.church_id, status='active'
    ).all()
    return render_template('members/add_ministry.html', leaders=potential_leaders)


@members_bp.route('/ministry/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_ministry(id):
    ministry = Ministry.query.get_or_404(id)

    if not can_manage_ministries():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.list_ministries'))

    if request.method == 'POST':
        ministry.name = request.form.get('name')
        ministry.description = request.form.get('description')
        ministry.leader_id = request.form.get('leader_id')

        if current_user.church_role and current_user.church_role.name == 'Administrador Global':
            church_id = request.form.get('church_id')
            if church_id:
                ministry.church_id = int(church_id)

        db.session.commit()

        if ministry.leader_id:
            leader = User.query.get(ministry.leader_id)
            if leader and leader not in ministry.members:
                ministry.members.append(leader)
                db.session.commit()

        flash('Ministério atualizado!', 'success')
        return redirect(url_for('members.list_ministries'))

    churches = Church.query.all() if (
        current_user.church_role and current_user.church_role.name == 'Administrador Global'
    ) else None
    potential_leaders = User.query.filter_by(
        church_id=ministry.church_id, status='active'
    ).all()
    return render_template(
        'members/edit_ministry.html',
        ministry=ministry,
        leaders=potential_leaders,
        churches=churches
    )


@members_bp.route('/ministry/<int:id>/delete')
@login_required
def delete_ministry(id):
    ministry = Ministry.query.get_or_404(id)

    if not can_manage_ministries():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.list_ministries'))

    db.session.delete(ministry)
    db.session.commit()
    flash('Ministério excluído com sucesso!', 'success')
    return redirect(url_for('members.list_ministries'))


@members_bp.route('/ministry/<int:id>/event/add', methods=['GET', 'POST'])
@login_required
def add_ministry_event(id):
    ministry = Ministry.query.get_or_404(id)

    is_leader = ministry.leader_id == current_user.id
    is_authorized = is_leader or current_user.can_manage_events or (
        current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']
    )

    if not is_authorized:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.list_ministries'))

    if request.method == 'POST':
        new_event = Event(
            title=request.form.get('title'),
            description=request.form.get('description'),
            start_time=datetime.strptime(request.form.get('start_time'), '%Y-%m-%dT%H:%M'),
            location=request.form.get('location'),
            ministry_id=ministry.id,
            church_id=current_user.church_id
        )
        db.session.add(new_event)
        db.session.commit()
        flash('Evento do ministério agendado!', 'success')
        return redirect(url_for('members.dashboard'))

    return render_template('members/add_event.html', ministry=ministry)


@members_bp.route('/event/add', methods=['GET', 'POST'])
@login_required
def add_general_event():
    is_authorized = current_user.can_manage_events or (
        current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']
    )

    if not is_authorized:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))

    if request.method == 'POST':
        new_event = Event(
            title=request.form.get('title'),
            description=request.form.get('description'),
            start_time=datetime.strptime(request.form.get('start_time'), '%Y-%m-%dT%H:%M'),
            location=request.form.get('location'),
            ministry_id=None,  # Evento geral
            church_id=current_user.church_id
        )
        db.session.add(new_event)
        db.session.commit()
        flash('Evento geral agendado!', 'success')
        return redirect(url_for('members.dashboard'))

    return render_template('members/add_event.html', ministry=None)


@members_bp.route('/my-church/members')
@login_required
def church_members():
    if not can_manage_members():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))

    members = User.query.filter_by(church_id=current_user.church_id).all()
    return render_template('members/church_members.html', members=members)


@members_bp.route('/member/promote/<int:id>', methods=['GET', 'POST'])
@login_required
def promote_member(id):
    if not can_manage_members():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))

    member = User.query.get_or_404(id)
    if member.church_id != current_user.church_id and not (
        current_user.church_role and current_user.church_role.name == 'Administrador Global'
    ):
        flash('Este membro não pertence à sua congregação.', 'danger')
        return redirect(url_for('members.church_members'))

    if request.method == 'POST':
        new_role_id = request.form.get('church_role_id')
        member.church_role_id = int(new_role_id) if new_role_id else None

        member.can_manage_ministries = 'can_manage_ministries' in request.form
        member.can_manage_media = 'can_manage_media' in request.form
        member.can_publish_devotionals = 'can_publish_devotionals' in request.form
        member.can_manage_finance = 'can_manage_finance' in request.form
        member.can_manage_events = 'can_manage_events' in request.form

        db.session.commit()
        flash(f'Cargo e permissões de {member.name} atualizados!', 'success')
        return redirect(url_for('members.church_members'))

    roles = ChurchRole.query.filter_by(
        church_id=member.church_id
    ).order_by(ChurchRole.order, ChurchRole.name).all()
    return render_template('members/promote_member.html', member=member, roles=roles)


@members_bp.route('/ministries/led-by-me')
@login_required
def my_led_ministries():
    led_ministries = Ministry.query.filter_by(leader_id=current_user.id).all()
    return render_template('members/my_led_ministries.html', led_ministries=led_ministries)


@members_bp.route('/ministry/<int:ministry_id>/manage-members')
@login_required
def ministry_manage_members(ministry_id):
    ministry = Ministry.query.get_or_404(ministry_id)

    is_leader = ministry.leader_id == current_user.id
    is_authorized = is_leader or can_manage_ministries()

    if not is_authorized:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.my_led_ministries'))

    current_members = ministry.members.all()
    available_members = User.query.filter(
        User.church_id == current_user.church_id,
        User.status == 'active',
        ~User.ministries.any(Ministry.id == ministry_id)
    ).order_by(User.name).all()

    total_members = len(current_members)
    gender_count = db.session.query(
        User.gender, func.count(User.id)
    ).filter(
        User.id.in_([m.id for m in current_members])
    ).group_by(User.gender).all()

    return render_template(
        'members/ministry_manage_members.html',
        ministry=ministry,
        current_members=current_members,
        available_members=available_members,
        total_members=total_members,
        gender_count=gender_count
    )


@members_bp.route('/ministry/<int:ministry_id>/add-member', methods=['POST'])
@login_required
def ministry_add_member(ministry_id):
    ministry = Ministry.query.get_or_404(ministry_id)

    is_leader = ministry.leader_id == current_user.id
    is_authorized = is_leader or can_manage_ministries()

    if not is_authorized:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.ministry_manage_members', ministry_id=ministry_id))

    user_id = request.form.get('user_id')
    if not user_id:
        flash('Selecione um membro.', 'warning')
        return redirect(url_for('members.ministry_manage_members', ministry_id=ministry_id))

    member = User.query.get_or_404(int(user_id))
    if member.church_id != ministry.church_id:
        flash('Membro não pertence a esta congregação.', 'danger')
    elif member not in ministry.members:
        ministry.members.append(member)
        db.session.commit()
        flash(f'{member.name} adicionado ao ministério!', 'success')

    return redirect(url_for('members.ministry_manage_members', ministry_id=ministry_id))


@members_bp.route('/ministry/<int:ministry_id>/remove-member/<int:user_id>')
@login_required
def ministry_remove_member(ministry_id, user_id):
    ministry = Ministry.query.get_or_404(ministry_id)

    is_leader = ministry.leader_id == current_user.id
    is_authorized = is_leader or can_manage_ministries()

    if not is_authorized:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.ministry_manage_members', ministry_id=ministry_id))

    member = User.query.get_or_404(user_id)
    if member in ministry.members:
        ministry.members.remove(member)
        db.session.commit()
        flash(f'{member.name} removido do ministério.', 'info')

    return redirect(url_for('members.ministry_manage_members', ministry_id=ministry_id))

@members_bp.route('/ministry/<int:ministry_id>/agenda')
@login_required
def ministry_agenda(ministry_id):
    ministry = Ministry.query.get_or_404(ministry_id)
    
    # Verifica se o usuário tem permissão (líder ou admin/gerente)
    is_leader = ministry.leader_id == current_user.id
    is_authorized = is_leader or current_user.can_manage_events or (
        current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']
    )
    
    if not is_authorized:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.my_led_ministries'))
    
    # Busca eventos futuros desse ministério
    events = Event.query.filter(
        Event.ministry_id == ministry_id,
        Event.start_time >= datetime.utcnow()
    ).order_by(Event.start_time.asc()).all()
    
    return render_template(
        'members/ministry_agenda.html',
        ministry=ministry,
        events=events
    )