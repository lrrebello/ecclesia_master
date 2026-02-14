from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app.core.models import db, Devotional, Study, KidsActivity, StudyQuestion, Media, Ministry
from datetime import datetime
from werkzeug.utils import secure_filename
import os
from PIL import Image
import pillow_heif

# Registra suporte a HEIC (executa uma vez ao carregar o módulo)
pillow_heif.register_heif_opener()

edification_bp = Blueprint('edification', __name__)

def can_publish_content():
    return current_user.can_publish_devotionals or (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder'])

@edification_bp.route('/devotionals')
@login_required
def devotionals():
    devotionals = Devotional.query.order_by(Devotional.date.desc()).all()
    return render_template('edification/devotionals.html', devotionals=devotionals)

@edification_bp.route('/devotional/add', methods=['GET', 'POST'])
@login_required
def add_devotional():
    if not can_publish_content():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.devotionals'))
    
    if request.method == 'POST':
        new_dev = Devotional(
            title=request.form.get('title'),
            content=request.form.get('content'),
            verse=request.form.get('verse'),
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        )
        db.session.add(new_dev)
        db.session.commit()
        flash('Devocional publicado!', 'success')
        return redirect(url_for('edification.devotionals'))
    
    return render_template('edification/add_devotional.html')

@edification_bp.route('/studies')
@login_required
def studies():
    studies = Study.query.order_by(Study.created_at.desc()).all()
    return render_template('edification/studies.html', studies=studies)

@edification_bp.route('/study/<int:id>')
@login_required
def study_detail(id):
    study = Study.query.get_or_404(id)
    return render_template('edification/study_detail.html', study=study)

@edification_bp.route('/study/add', methods=['GET', 'POST'])
@login_required
def add_study():
    if not can_publish_content():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.studies'))
    
    if request.method == 'POST':
        new_study = Study(
            title=request.form.get('title'),
            content=request.form.get('content'),
            category=request.form.get('category'),
            author_id=current_user.id
        )
        db.session.add(new_study)
        db.session.commit()
        
        # Adicionar questões se fornecidas
        questions = request.form.getlist('questions[]')
        options = request.form.getlist('options[]')
        correct_options = request.form.getlist('correct_options[]')
        
        for q, opt, correct in zip(questions, options, correct_options):
            if q:
                new_q = StudyQuestion(
                    study_id=new_study.id,
                    question_text=q,
                    options=opt,
                    correct_option=int(correct) if correct else None
                )
                db.session.add(new_q)
        
        db.session.commit()
        flash('Estudo publicado com sucesso!', 'success')
        return redirect(url_for('edification.studies'))
    
    return render_template('edification/add_study.html')

@edification_bp.route('/kids')
@login_required
def kids():
    if not current_user.can_manage_kids and not (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    activities = KidsActivity.query.order_by(KidsActivity.created_at.desc()).all()
    return render_template('edification/kids.html', activities=activities)

@edification_bp.route('/kids/add', methods=['GET', 'POST'])
@login_required
def add_kids_activity():
    if not current_user.can_manage_kids and not (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.kids'))
    
    if request.method == 'POST':
        new_act = KidsActivity(
            title=request.form.get('title'),
            content=request.form.get('content'),
            age_group=request.form.get('age_group')
        )
        db.session.add(new_act)
        db.session.commit()
        flash('Atividade infantil adicionada!', 'success')
        return redirect(url_for('edification.kids'))
    
    return render_template('edification/add_kids_activity.html')

@edification_bp.route('/gallery')
@login_required
def gallery():
    query = Media.query.filter_by(church_id=current_user.church_id)
    
    ministry_id = request.args.get('ministry_id')
    if ministry_id:
        query = query.filter_by(ministry_id=ministry_id)
    
    media_type = request.args.get('media_type')
    if media_type:
        query = query.filter_by(media_type=media_type)
    
    media_items = query.order_by(Media.created_at.desc()).all()
    ministries = Ministry.query.filter_by(church_id=current_user.church_id).all()
    
    return render_template('edification/gallery.html', media_items=media_items, ministries=ministries)

@edification_bp.route('/upload_media', methods=['GET', 'POST'])
@login_required
def upload_media():
    if not current_user.can_manage_media and not (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']) and not any(m.leader_id == current_user.id for m in current_user.ministries):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.gallery'))
    
    ministries = Ministry.query.filter_by(church_id=current_user.church_id).all()
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        ministry_id = request.form.get('ministry_id')
        file = request.files.get('file')
        
        if not file:
            flash('Nenhum arquivo selecionado.', 'danger')
            return redirect(request.url)
        
        filename = secure_filename(file.filename)
        file_ext = os.path.splitext(filename)[1].lower()
        
        # Suporte a HEIC
        if file_ext == '.heic':
            try:
                img = Image.open(file)
                new_filename = filename.replace('.heic', '.jpg', 1)
                full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'media', new_filename)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                img.convert('RGB').save(full_path, 'JPEG', quality=95)
                file_path = 'uploads/media/' + new_filename
                media_type = 'image'
            except Exception as e:
                flash(f'Erro ao converter HEIC: {str(e)}', 'danger')
                return redirect(request.url)
        else:
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'media', filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            file.save(full_path)
            file_path = 'uploads/media/' + filename
            
            if file_ext in ['.jpg', '.jpeg', '.png', '.gif']:
                media_type = 'image'
            elif file_ext in ['.mp4', '.mov']:
                media_type = 'video'
            elif file_ext == '.pdf':
                media_type = 'pdf'
            else:
                flash('Formato de arquivo não suportado.', 'danger')
                return redirect(request.url)
        
        new_media = Media(
            title=title,
            description=description,
            file_path=file_path,
            media_type=media_type,
            church_id=current_user.church_id,
            ministry_id=int(ministry_id) if ministry_id else None
        )
        db.session.add(new_media)
        db.session.commit()
        flash('Mídia adicionada com sucesso!', 'success')
        return redirect(url_for('edification.gallery'))
    
    return render_template('edification/add_media.html', ministries=ministries)