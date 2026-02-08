from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app.core.models import Study, Devotional, KidsActivity, StudyQuestion, db, Media
import markdown
import os
from werkzeug.utils import secure_filename

edification_bp = Blueprint('edification', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@edification_bp.route('/studies')
@login_required
def list_studies():
    studies = Study.query.order_by(Study.created_at.desc()).all()
    return render_template('edification/studies.html', studies=studies)

@edification_bp.route('/study/<int:id>')
@login_required
def view_study(id):
    study = Study.query.get_or_404(id)
    content_html = markdown.markdown(study.content)
    return render_template('edification/view_study.html', study=study, content_html=content_html)

@edification_bp.route('/kids')
@login_required
def kids_corner():
    activities = KidsActivity.query.order_by(KidsActivity.created_at.desc()).all()
    return render_template('edification/kids.html', activities=activities)

@edification_bp.route('/admin/add_kids_activity', methods=['GET', 'POST'])
@login_required
def add_kids_activity():
    if not current_user.church_role or current_user.church_role.name not in ['Administrador Global', 'Pastor Líder', 'Líder de Mídia']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.kids_corner'))
        
    if request.method == 'POST':
        new_act = KidsActivity(
            title=request.form.get('title'),
            content=request.form.get('content'),
            age_group=request.form.get('age_group')
        )
        db.session.add(new_act)
        db.session.commit()
        flash('Atividade infantil publicada!', 'success')
        return redirect(url_for('edification.kids_corner'))
    return render_template('edification/add_kids.html')

@edification_bp.route('/study/add', methods=['GET', 'POST'])
@login_required
def add_study():
    if not current_user.church_role or current_user.church_role.name not in ['Administrador Global', 'Pastor Líder']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.list_studies'))
        
    if request.method == 'POST':
        new_study = Study(
            title=request.form.get('title'),
            content=request.form.get('content'),
            category=request.form.get('category'),
            author_id=current_user.id
        )
        db.session.add(new_study)
        db.session.commit()
        flash('Estudo bíblico publicado!', 'success')
        return redirect(url_for('edification.list_studies'))
    return render_template('edification/add_study.html')

@edification_bp.route('/gallery')
@login_required
def gallery():
    media_items = Media.query.filter_by(church_id=current_user.church_id).order_by(Media.created_at.desc()).all()
    return render_template('edification/gallery.html', media_items=media_items)

@edification_bp.route('/media/add', methods=['GET', 'POST'])
@login_required
def add_media():
    if not current_user.church_role or current_user.church_role.name not in ['Administrador Global', 'Pastor Líder', 'Líder de Mídia']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.gallery'))
        
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or file.filename == '':
            flash('Nenhum arquivo selecionado.', 'danger')
            return redirect(request.url)
        
        if not allowed_file(file.filename):
            flash('Tipo de arquivo não permitido. Use imagens (png, jpg, jpeg, gif) ou vídeos (mp4).', 'danger')
            return redirect(request.url)
        
        filename = secure_filename(file.filename)
        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'media')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        
        new_media = Media(
            title=request.form.get('title'),
            description=request.form.get('description'),
            file_path=filename,
            media_type='video' if filename.lower().endswith('.mp4') else 'image',
            event_name=request.form.get('event_name'),
            church_id=current_user.church_id
        )
        db.session.add(new_media)
        db.session.commit()
        
        flash('Mídia adicionada à galeria com sucesso!', 'success')
        return redirect(url_for('edification.gallery'))
    
    return render_template('edification/add_media.html')