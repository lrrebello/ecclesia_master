from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.core.models import User, Church, Ministry, Event, db, Devotional, Study

members_bp = Blueprint('members', __name__)

@members_bp.route('/dashboard')
@login_required
def dashboard():
    latest_devotional = Devotional.query.order_by(Devotional.date.desc()).first()
    recent_studies = Study.query.order_by(Study.created_at.desc()).limit(3).all()
    
    # Agenda Personalizada: Eventos Gerais + Eventos dos Ministérios do Membro
    ministry_ids = [m.id for m in current_user.ministries]
    personal_agenda = Event.query.filter(
        (Event.church_id == current_user.church_id) & 
        ((Event.ministry_id == None) | (Event.ministry_id.in_(ministry_ids)))
    ).order_by(Event.start_time.asc()).all()
    
    # Se for Pastor Líder, ver solicitações pendentes da sua filial
    pending_members = []
    if current_user.role in ['admin', 'pastor_leader']:
        pending_members = User.query.filter_by(church_id=current_user.church_id, status='pending').all()
        
    return render_template('members/dashboard.html', 
                           devotional=latest_devotional, 
                           studies=recent_studies,
                           agenda=personal_agenda,
                           pending_members=pending_members)

@members_bp.route('/profile')
@login_required
def profile():
    return render_template('members/profile.html')

@members_bp.route('/ministries')
@login_required
def list_ministries():
    # Pastor Líder vê todos da sua filial, Membro vê os seus
    if current_user.role in ['admin', 'pastor_leader']:
        ministries = Ministry.query.filter_by(church_id=current_user.church_id).all()
    else:
        ministries = current_user.ministries
    return render_template('members/ministries.html', ministries=ministries)

@members_bp.route('/ministry/add', methods=['GET', 'POST'])
@login_required
def add_ministry():
    if current_user.role not in ['admin', 'pastor_leader']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.list_ministries'))
        
    if request.method == 'POST':
        new_min = Ministry(
            name=request.form.get('name'),
            description=request.form.get('description'),
            church_id=current_user.church_id,
            leader_id=request.form.get('leader_id')
        )
        db.session.add(new_min)
        db.session.commit()
        flash('Ministério criado com sucesso!', 'success')
        return redirect(url_for('members.list_ministries'))
        
    potential_leaders = User.query.filter_by(church_id=current_user.church_id, status='active').all()
    return render_template('members/add_ministry.html', leaders=potential_leaders)

@members_bp.route('/ministry/<int:id>/event/add', methods=['GET', 'POST'])
@login_required
def add_ministry_event(id):
    ministry = Ministry.query.get_or_404(id)
    # Apenas Admin, Pastor Líder ou o Líder do Ministério podem criar eventos
    if current_user.role not in ['admin', 'pastor_leader'] and ministry.leader_id != current_user.id:
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
