# Arquivo completo: app/modules/members/routes.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user, logout_user
from app.core.models import User, Church, Ministry, Event, db, Devotional, Study, ChurchRole
from datetime import datetime, timedelta
from sqlalchemy import func
from werkzeug.utils import secure_filename
import os

members_bp = Blueprint('members', __name__)

def can_manage_members():
    return current_user.can_approve_members or (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder'])

def can_manage_ministries():
    return current_user.can_manage_ministries or (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder'])

@members_bp.route('/dashboard')
@login_required
def dashboard():
    latest_devotional = Devotional.query.order_by(Devotional.date.desc()).first()
    recent_studies = Study.query.order_by(Study.created_at.desc()).limit(3).all()
    
    ministry_ids = [m.id for m in current_user.ministries]
    personal_agenda = Event.query.filter(
        (Event.church_id == current_user.church_id) & 
        ((Event.ministry_id == None) | (Event.ministry_id.in_(ministry_ids))) &
        (Event.start_time >= datetime.now())
    ).order_by(Event.start_time.asc()).limit(5).all()
    
    is_global_admin = current_user.church_role and current_user.church_role.name == 'Administrador Global'
    is_pastor = current_user.church_role and current_user.church_role.name == 'Pastor Líder'
    led_ministries_list = [m for m in current_user.ministries if m.leader_id == current_user.id]
    is_ministry_leader = len(led_ministries_list) > 0
    is_authorized_for_alerts = is_global_admin or is_pastor or is_ministry_leader

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

    birthday_alerts = []
    if is_authorized_for_alerts:
        today = datetime.now().date()
        future_limit = today + timedelta(days=10)
        
        if is_global_admin or is_pastor:
            target_ministries = Ministry.query.filter_by(church_id=current_user.church_id).all()
        else:
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
                           devotional=latest_devotional, 
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
        current_user.gender = request.form.get('gender')
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
        db.session.commit()
        flash('Ministério atualizado!', 'success')
        return redirect(url_for('members.list_ministries'))

    potential_leaders = User.query.filter_by(church_id=current_user.church_id, status='active').all()
    return render_template('members/edit_ministry.html', ministry=ministry, leaders=potential_leaders)

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
            # Aproximação simples para mensal
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
    ministry = Ministry.query.get(id) if id else None
    
    is_authorized = current_user.can_manage_events or (
        current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']
    ) or (ministry and ministry.leader_id == current_user.id)

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

# Aliases para compatibilidade com templates antigos
@members_bp.route('/event/add_general')
def add_general_event():
    return redirect(url_for('members.add_event'))

@members_bp.route('/event/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(id):
    event = Event.query.get_or_404(id)
    is_authorized = (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']) or \
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
    is_authorized = (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']) or \
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

@members_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso.', 'info')
    return redirect(url_for('auth.login'))
