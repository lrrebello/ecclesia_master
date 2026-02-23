# Arquivo completo: app/modules/members/routes.py (adicionando edição no profile, acesso a dados para líderes)
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user, logout_user
from app.core.models import User, Church, Ministry, Event, db, Devotional, Study, ChurchRole
from datetime import datetime, timedelta
from sqlalchemy import func
from werkzeug.utils import secure_filename
import os

members_bp = Blueprint('members', __name__)

def can_manage_members():
    return current_user.can_approve_members or (current_user.church_role and current_user.church_role.name == 'Administrador Global' or current_user.church_role.is_lead_pastor)

def can_manage_ministries():
    return current_user.can_manage_ministries or (current_user.church_role and current_user.church_role.name == 'Administrador Global' or current_user.church_role.is_lead_pastor)

@members_bp.route('/dashboard')
@login_required
def dashboard():
    # Data de hoje (usa hora local do servidor; em Portugal é WET/WEST)
    today = datetime.now().date()

    # Busca o devocional EXATAMENTE de hoje
    devotional = Devotional.query.filter_by(date=today).first()

    # Fallback: se não existir devocional para hoje, pega o mais recente
    # (você pode remover isso e deixar devotional=None se preferir mostrar o "Bem-vindo" sempre que faltar)
    if not devotional:
        devotional = Devotional.query.order_by(Devotional.date.desc()).first()

    recent_studies = Study.query.order_by(Study.created_at.desc()).limit(3).all()
    
    ministry_ids = [m.id for m in current_user.ministries]
    personal_agenda = Event.query.filter(
        (Event.church_id == current_user.church_id) & 
        ((Event.ministry_id == None) | (Event.ministry_id.in_(ministry_ids))) &
        (Event.start_time >= datetime.now())
    ).order_by(Event.start_time.asc()).limit(5).all()
    
    # Lógica de Permissões Centralizada (Mesma lógica do menu lateral)
    is_global_admin = current_user.church_role and current_user.church_role.name == 'Administrador Global'
    is_pastor = current_user.church_role and current_user.church_role and current_user.church_role.is_lead_pastor
    
    # Identifica se o usuário é líder de algum ministério (Lógica do menu lateral)
    led_ministries_list = [m for m in current_user.ministries if m.leader_id == current_user.id]
    is_ministry_leader = len(led_ministries_list) > 0
    
    is_authorized_for_alerts = is_global_admin or is_pastor or is_ministry_leader

    # Buscar solicitações pendentes
    pending_members = []
    if current_user.can_approve_members or is_global_admin or is_pastor:
        if is_global_admin:
            pending_members = User.query.filter_by(status='pending').all()
        else:
            from sqlalchemy import or_
            pending_members = User.query.filter(
                (User.status == 'pending') & 
                (or_(User.church_id == current_user.church_id, User.church_id == None))
            ).all()

    # Lógica de Aniversariantes para Líderes (Próximos 10 dias)
    birthday_alerts = []
    if is_authorized_for_alerts:
        today = datetime.now().date()
        future_limit = today + timedelta(days=10)
        
        # Determinar quais ministérios observar
        if is_global_admin or is_pastor:
            # Administradores e Pastores veem todos os ministérios da congregação
            target_ministries = Ministry.query.filter_by(church_id=current_user.church_id).all()
        else:
            # Líderes de ministério veem apenas os que lideram (usando a lista já filtrada)
            target_ministries = led_ministries_list
            
        if target_ministries:
            seen_members = set()
            for ministry in target_ministries:
                for member in ministry.members:
                    if member.birth_date and member.id not in seen_members:
                        try:
                            bday_this_year = member.birth_date.replace(year=today.year)
                        except ValueError:
                            bday_this_year = member.birth_date.replace(year=today.year, day=28)
                        
                        if bday_this_year < today:
                            try:
                                bday_this_year = bday_this_year.replace(year=today.year + 1)
                            except ValueError:
                                bday_this_year = bday_this_year.replace(year=today.year + 1, day=28)

                        if today <= bday_this_year <= future_limit:
                            days_until = (bday_this_year - today).days
                            birthday_alerts.append({
                                'name': member.name,
                                'day': member.birth_date.day,
                                'month': member.birth_date.strftime('%m'),
                                'ministry': ministry.name,
                                'is_today': days_until == 0,
                                'days_until': days_until
                            })
                            seen_members.add(member.id)
            birthday_alerts.sort(key=lambda x: x['days_until'])
        
    return render_template('members/dashboard.html', 
                           devotional=devotional,  # ← agora é o de hoje (ou fallback)
                           studies=recent_studies,
                           agenda=personal_agenda,
                           pending_members=pending_members,
                           birthday_alerts=birthday_alerts,
                           datetime=datetime)

@members_bp.route('/profile')
@login_required
def profile():
    return render_template('members/profile.html')

@members_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.name = request.form.get('name')
        current_user.birth_date = datetime.strptime(request.form.get('birth_date'), '%Y-%m-%d').date() if request.form.get('birth_date') else current_user.birth_date
        current_user.baptism_date = datetime.strptime(request.form.get('baptism_date'), '%Y-%m-%d').date() if request.form.get('baptism_date') else current_user.baptism_date
        current_user.conversion_date = datetime.strptime(request.form.get('conversion_date'), '%Y-%m-%d').date() if request.form.get('conversion_date') else current_user.conversion_date
        current_user.gender = request.form.get('gender')
        current_user.marital_status = request.form.get('marital_status')
        current_user.spouse_name = request.form.get('spouse_name') if request.form.get('marital_status') == 'Casado(a)' else None
        current_user.documents = request.form.get('documents')
        current_user.address = request.form.get('address')
        current_user.phone = request.form.get('phone')
        
        file = request.files.get('profile_photo')
        if file:
            filename = secure_filename(file.filename)
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles', filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            file.save(full_path)
            current_user.profile_photo = 'uploads/profiles/' + filename
        
        db.session.commit()
        flash('Perfil atualizado com sucesso!', 'success')
        return redirect(url_for('members.profile'))
    
    return render_template('members/edit_profile.html')

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
    gender_count = db.session.query(User.gender, func.count(User.id)).filter(
        User.id.in_([m.id for m in current_members])
    ).group_by(User.gender).all()
    
    return render_template('members/ministry_manage_members.html',
                           ministry=ministry,
                           current_members=current_members,
                           available_members=available_members,
                           total_members=total_members,
                           gender_count=gender_count,
                           is_leader=is_leader)

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
            leader_id=int(leader_id) if leader_id else None,
            is_kids_ministry='is_kids_ministry' in request.form
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
        ministry.is_kids_ministry = 'is_kids_ministry' in request.form

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
    potential_leaders = User.query.filter_by(church_id=current_user.church_id, status='active').all()
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

@members_bp.route('/agenda')
@login_required
def agenda():
    ministry_ids = [m.id for m in current_user.ministries]
    events = Event.query.filter(
        (Event.church_id == current_user.church_id) & 
        ((Event.ministry_id == None) | (Event.ministry_id.in_(ministry_ids))) &
        (Event.start_time >= datetime.now() - timedelta(hours=24))
    ).order_by(Event.start_time.asc()).all()
    
    return render_template('members/agenda.html', events=events)

def create_recurring_events(base_event, recurrence_type, count=12):
    """Gera ocorrências futuras para um evento recorrente"""
    for i in range(1, count):
        if recurrence_type == 'weekly':
            new_time = base_event.start_time + timedelta(weeks=i)
        elif recurrence_type == 'monthly':
            new_time = base_event.start_time + timedelta(days=30*i)
        else:
            break
            
        new_event = Event(
            title=base_event.title,
            description=base_event.description,
            start_time=new_time,
            location=base_event.location,
            ministry_id=base_event.ministry_id,
            church_id=base_event.church_id,
            recurrence='none'
        )
        db.session.add(new_event)

@members_bp.route('/event/add', methods=['GET', 'POST'])
@members_bp.route('/ministry/<int:id>/event/add', methods=['GET', 'POST'])
@login_required
def add_event(id=None):
    # Suporta tanto criação geral quanto por ministério
    ministry = Ministry.query.get(id) if id else None
    
    is_authorized = current_user.can_manage_events or (
        current_user.church_role and current_user.church_role.name == 'Administrador Global' or current_user.church_role.is_lead_pastor    ) or (ministry and ministry.leader_id == current_user.id)

    if not is_authorized:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))

    if request.method == 'POST':
        start_time = datetime.strptime(request.form.get('start_time'), '%Y-%m-%dT%H:%M')
        recurrence = request.form.get('recurrence', 'none')
        
        new_event = Event(
            title=request.form.get('title'),
            description=request.form.get('description'),
            start_time=start_time,
            location=request.form.get('location'),
            ministry_id=ministry.id if ministry else None,
            church_id=current_user.church_id,
            recurrence=recurrence
        )
        db.session.add(new_event)
        
        if recurrence != 'none':
            create_recurring_events(new_event, recurrence)
            
        db.session.commit()
        flash('Evento(s) agendado(s) com sucesso!', 'success')
        return redirect(url_for('members.agenda'))

    return render_template('members/add_event.html', ministry=ministry)

# Aliases para compatibilidade
@members_bp.route('/ministry/<int:id>/event/add_legacy')
def add_ministry_event(id):
    return redirect(url_for('members.add_event', id=id))

@members_bp.route('/event/add_general')
def add_general_event():
    return redirect(url_for('members.add_event'))

@members_bp.route('/event/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(id):
    event = Event.query.get_or_404(id)
    is_authorized = (current_user.church_role and current_user.church_role.name == 'Administrador Global' or current_user.church_role.is_lead_pastor) or \
                    (event.ministry and event.ministry.leader_id == current_user.id) or \
                    current_user.can_manage_events
    
    if not is_authorized:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.agenda'))
    
    if request.method == 'POST':
        event.title = request.form.get('title')
        event.description = request.form.get('description')
        event.start_time = datetime.strptime(request.form.get('start_time'), '%Y-%m-%dT%H:%M')
        event.location = request.form.get('location')
        event.recurrence = request.form.get('recurrence', 'none')
        
        db.session.commit()
        flash('Evento atualizado!', 'success')
        return redirect(url_for('members.agenda'))
    
    return render_template('members/edit_event.html', event=event)

@members_bp.route('/event/<int:id>/delete', methods=['POST'])
@login_required
def delete_event(id):
    event = Event.query.get_or_404(id)
    is_authorized = (current_user.church_role and current_user.church_role.name == 'Administrador Global' or current_user.church_role.is_lead_pastor) or \
                    (event.ministry and event.ministry.leader_id == current_user.id) or \
                    current_user.can_manage_events
    
    if not is_authorized:
        flash('Acesso negado.', 'danger')
    else:
        db.session.delete(event)
        db.session.commit()
        flash('Evento excluído!', 'success')
    return redirect(url_for('members.agenda'))

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
        member.can_manage_kids = 'can_manage_kids' in request.form

        db.session.commit()
        flash(f'Cargo e permissões de {member.name} atualizados!', 'success')
        return redirect(url_for('members.church_members'))

    roles = ChurchRole.query.filter_by(
        church_id=member.church_id
    ).order_by(ChurchRole.order, ChurchRole.name).all()
    return render_template('members/promote_member.html', member=member, roles=roles)

@members_bp.route('/member/<int:id>/delete', methods=['POST'])
@login_required
def delete_member(id):
    if not can_manage_members():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.church_members'))
    member = User.query.get_or_404(id)
    if member.id == current_user.id:
        flash('Você não pode excluir sua própria conta.', 'warning')
        return redirect(url_for('members.church_members'))
    member.ministries = []
    db.session.delete(member)
    db.session.commit()
    flash(f'Membro {member.name} excluído!', 'success')
    return redirect(url_for('members.church_members'))

@members_bp.route('/ministries/led-by-me')
@login_required
def my_led_ministries():
    led_ministries = Ministry.query.filter_by(leader_id=current_user.id).all()
    return render_template('members/my_led_ministries.html', led_ministries=led_ministries)

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
    
    is_leader = ministry.leader_id == current_user.id
    is_authorized = is_leader or current_user.can_manage_events or (
        current_user.church_role and current_user.church_role.name == 'Administrador Global' or current_user.church_role.is_lead_pastor    )
    
    if not is_authorized:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.my_led_ministries'))
    
    events = Event.query.filter(
        Event.ministry_id == ministry_id,
        Event.start_time >= datetime.utcnow()
    ).order_by(Event.start_time.asc()).all()
    
    return render_template(
        'members/ministry_agenda.html',
        ministry=ministry,
        events=events
    )

@members_bp.route('/birthdays')
@members_bp.route('/ministry/<int:ministry_id>/birthdays')
@login_required
def birthday_agenda(ministry_id=None):
    is_global_admin = current_user.church_role and current_user.church_role.name == 'Administrador Global'
    is_pastor = current_user.church_role and current_user.church_role and current_user.church_role.is_lead_pastor
    
    ministry = None
    if ministry_id:
        ministry = Ministry.query.get_or_404(ministry_id)
        is_leader = ministry.leader_id == current_user.id
        if not (is_leader or is_global_admin or is_pastor):
            flash('Acesso negado.', 'danger')
            return redirect(url_for('members.dashboard'))
        members = ministry.members.all()
        title = f"Aniversariantes - {ministry.name}"
    else:
        if not (is_global_admin or is_pastor):
            flash('Acesso negado.', 'danger')
            return redirect(url_for('members.dashboard'))
        members = User.query.filter_by(church_id=current_user.church_id, status='active').all()
        title = "Agenda Anual de Aniversariantes"

    # Organizar por mês
    agenda = {i: [] for i in range(1, 13)}
    for member in members:
        if member.birth_date:
            month = member.birth_date.month
            agenda[month].append({
                'name': member.name,
                'day': member.birth_date.day,
                'phone': member.phone
            })
    
    # Ordenar cada mês por dia
    for month in agenda:
        agenda[month].sort(key=lambda x: x['day'])

    month_names = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
        5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
        9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }

    return render_template('members/birthday_agenda.html', 
                           agenda=agenda, 
                           month_names=month_names, 
                           title=title,
                           ministry=ministry)

@members_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso.', 'info')
    return redirect(url_for('auth.login'))
