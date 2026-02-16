# Arquivo completo: app/modules/edification/routes.py (baseado no TXT, com filtro de midias por ministério do user, HEIC mantido, novas rotas para edit/delete media)
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app.core.models import db, Devotional, Study, KidsActivity, StudyQuestion, Media, Ministry, Album, BibleStory, BibleQuiz
from datetime import datetime
from werkzeug.utils import secure_filename
import os
from PIL import Image
import pillow_heif

# Registra suporte a HEIC
pillow_heif.register_heif_opener()

edification_bp = Blueprint('edification', __name__)

def can_publish_content():
    return current_user.can_publish_devotionals or (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder'])

@edification_bp.route('/devotionals')
@login_required
def devotionals():
    devotionals = Devotional.query.order_by(Devotional.date.desc()).all()
    return render_template('edification/devotionals.html', devotionals=devotionals)

@edification_bp.route('/devotionals/manage')
@login_required
def list_devotionals():
    if not can_publish_content():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.devotionals'))
    devotionals = Devotional.query.order_by(Devotional.date.desc()).all()
    return render_template('edification/list_devotionals.html', devotionals=devotionals)

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
        return redirect(url_for('edification.list_devotionals'))
    
    return render_template('edification/add_devotional.html')

@edification_bp.route('/devotional/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_devotional(id):
    if not can_publish_content():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.devotionals'))
    
    dev = Devotional.query.get_or_404(id)
    if request.method == 'POST':
        dev.title = request.form.get('title')
        dev.content = request.form.get('content')
        dev.verse = request.form.get('verse')
        dev.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        db.session.commit()
        flash('Devocional atualizado!', 'success')
        return redirect(url_for('edification.list_devotionals'))
    
    return render_template('edification/edit_devotional.html', dev=dev)

@edification_bp.route('/devotional/<int:id>/delete')
@login_required
def delete_devotional(id):
    if not can_publish_content():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.devotionals'))
    
    dev = Devotional.query.get_or_404(id)
    db.session.delete(dev)
    db.session.commit()
    flash('Devocional excluído!', 'info')
    return redirect(url_for('edification.list_devotionals'))

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
    stories = BibleStory.query.order_by(BibleStory.order.asc()).all()
    
    return render_template('edification/kids.html', activities=activities, stories=stories)

@edification_bp.route('/kids/manage')
@login_required
def manage_kids():
    if not current_user.can_manage_kids and not (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.kids'))
    
    stories = BibleStory.query.order_by(BibleStory.order.asc()).all()
    activities = KidsActivity.query.order_by(KidsActivity.created_at.desc()).all()
    return render_template('edification/manage_kids.html', stories=stories, activities=activities)

@edification_bp.route('/kids/story/add', methods=['POST'])
@login_required
def add_bible_story():
    if not current_user.can_manage_kids: return redirect(url_for('edification.kids'))
    
    new_story = BibleStory(
        title=request.form.get('title'),
        content=request.form.get('content'),
        reference=request.form.get('reference'),
        image_path=request.form.get('image_path'),
        order=request.form.get('order', 0)
    )
    db.session.add(new_story)
    db.session.commit()
    flash('História adicionada!', 'success')
    return redirect(url_for('edification.manage_kids'))

@edification_bp.route('/kids/story/delete/<int:id>')
@login_required
def delete_bible_story(id):
    if not current_user.can_manage_kids: return redirect(url_for('edification.kids'))
    story = BibleStory.query.get_or_404(id)
    db.session.delete(story)
    db.session.commit()
    flash('História removida.', 'info')
    return redirect(url_for('edification.manage_kids'))

@edification_bp.route('/kids/quiz/add', methods=['POST'])
@login_required
def add_bible_quiz():
    if not current_user.can_manage_kids: return redirect(url_for('edification.kids'))
    
    new_quiz = BibleQuiz(
        story_id=request.form.get('story_id'),
        question=request.form.get('question'),
        option_a=request.form.get('option_a'),
        option_b=request.form.get('option_b'),
        option_c=request.form.get('option_c'),
        correct_option=request.form.get('correct_option'),
        explanation=request.form.get('explanation')
    )
    db.session.add(new_quiz)
    db.session.commit()
    flash('Quiz adicionado!', 'success')
    return redirect(url_for('edification.manage_kids'))

@edification_bp.route('/kids/memory-game')
@login_required
def memory_game():
    return render_template('edification/kids_memory_game.html')

@edification_bp.route('/kids/who-am-i')
@login_required
def who_am_i():
    return render_template('edification/kids_who_am_i.html')

@edification_bp.route('/kids/bible-story/<int:id>')
@login_required
def view_bible_story(id):
    story = BibleStory.query.get_or_404(id)
    return render_template('edification/view_bible_story.html', story=story)

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
    
    return render_template('edification/add_kids.html')

@edification_bp.route('/gallery')
@login_required
def gallery():
    # Se houver um album_id, mostra apenas as mídias desse álbum
    album_id = request.args.get('album_id')
    if album_id:
        album = Album.query.get_or_404(album_id)
        media_items = Media.query.filter_by(album_id=album_id).order_by(Media.created_at.desc()).all()
        return render_template('edification/gallery_album.html', album=album, media_items=media_items)

    # Caso contrário, mostra os álbuns e mídias avulsas
    query_albums = Album.query.filter_by(church_id=current_user.church_id)
    query_media = Media.query.filter_by(church_id=current_user.church_id, album_id=None)
    
    # Filtro para midias gerais ou dos ministérios do user
    ministry_ids = [m.id for m in current_user.ministries]
    query_albums = query_albums.filter((Album.ministry_id.is_(None)) | (Album.ministry_id.in_(ministry_ids)))
    query_media = query_media.filter((Media.ministry_id.is_(None)) | (Media.ministry_id.in_(ministry_ids)))
    
    ministry_id = request.args.get('ministry_id')
    if ministry_id:
        query_albums = query_albums.filter_by(ministry_id=ministry_id)
        query_media = query_media.filter_by(ministry_id=ministry_id)
    
    albums = query_albums.order_by(Album.created_at.desc()).all()
    media_items = query_media.order_by(Media.created_at.desc()).all()
    ministries = Ministry.query.filter_by(church_id=current_user.church_id).all()
    
    # Agrupar mídias avulsas por evento (mantendo a lógica que você já tinha para o que não for álbum)
    events_grouped = {}
    for item in media_items:
        evt = item.event_name or "Geral / Outros"
        if evt not in events_grouped:
            events_grouped[evt] = []
        events_grouped[evt].append(item)
    
    return render_template('edification/gallery.html', albums=albums, events_grouped=events_grouped, ministries=ministries)

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
        event_name = request.form.get('event_name')
        group_as_album = request.form.get('group_as_album') == 'on'
        files = request.files.getlist('file')
        
        if not files or not files[0].filename:
            flash('Nenhum arquivo selecionado.', 'danger')
            return redirect(request.url)
        
        album = None
        if group_as_album and len(files) > 0:
            album = Album(
                title=title,
                description=description,
                church_id=current_user.church_id,
                ministry_id=int(ministry_id) if ministry_id else None
            )
            db.session.add(album)
            db.session.flush() # Para pegar o ID do album
            
        count = 0
        for file in files:
            filename = secure_filename(file.filename)
            if not filename: continue
            
            file_ext = os.path.splitext(filename)[1].lower()
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{count}_{filename}"
            
            if file_ext == '.heic':
                try:
                    img = Image.open(file)
                    new_filename = unique_filename.replace('.heic', '.jpg', 1)
                    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'media', new_filename)
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    img.convert('RGB').save(full_path, 'JPEG', quality=95)
                    file_path = 'uploads/media/' + new_filename
                    media_type = 'image'
                except Exception as e:
                    continue
            else:
                full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'media', unique_filename)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                file.save(full_path)
                file_path = 'uploads/media/' + unique_filename
                
                if file_ext in ['.jpg', '.jpeg', '.png', '.gif']:
                    media_type = 'image'
                elif file_ext in ['.mp4', '.mov']:
                    media_type = 'video'
                elif file_ext == '.pdf':
                    media_type = 'pdf'
                else:
                    continue
            
            new_media = Media(
                title=title if not album else file.filename,
                description=description,
                file_path=file_path,
                media_type=media_type,
                event_name=event_name,
                church_id=current_user.church_id,
                ministry_id=int(ministry_id) if ministry_id else None,
                album_id=album.id if album else None
            )
            db.session.add(new_media)
            count += 1
            
        db.session.commit()
        flash(f'{count} mídias adicionadas com sucesso!', 'success')
        return redirect(url_for('edification.gallery'))
    
    return render_template('edification/add_media.html', ministries=ministries)

@edification_bp.route('/album/<int:id>/delete')
@login_required
def delete_album(id):
    album = Album.query.get_or_404(id)
    if not (current_user.can_manage_media or (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']) or (album.ministry and album.ministry.leader_id == current_user.id)):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.gallery'))
    
    for media in album.media_items:
        if media.file_path and os.path.exists(current_app.config['UPLOAD_FOLDER'] + '/' + media.file_path.replace('uploads/', '')):
            try: os.remove(current_app.config['UPLOAD_FOLDER'] + '/' + media.file_path.replace('uploads/', ''))
            except: pass
                
    db.session.delete(album)
    db.session.commit()
    flash('Álbum e todas as suas mídias foram excluídos.', 'info')
    return redirect(url_for('edification.gallery'))

# Nova rota para editar mídia
@edification_bp.route('/media/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_media(id):
    media = Media.query.get_or_404(id)
    
    # Permissão: dono, líder do ministério ou admin
    if not (current_user.can_manage_media or (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']) or (media.ministry and media.ministry.leader_id == current_user.id)):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.gallery'))
    
    ministries = Ministry.query.filter_by(church_id=current_user.church_id).all()
    
    if request.method == 'POST':
        media.title = request.form.get('title')
        media.description = request.form.get('description')
        media.ministry_id = int(request.form.get('ministry_id')) if request.form.get('ministry_id') else None
        
        file = request.files.get('file')
        if file:
            filename = secure_filename(file.filename)
            file_ext = os.path.splitext(filename)[1].lower()
            
            if file_ext == '.heic':
                img = Image.open(file)
                new_filename = filename.replace('.heic', '.jpg', 1)
                full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'media', new_filename)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                img.convert('RGB').save(full_path, 'JPEG', quality=95)
                media.file_path = 'uploads/media/' + new_filename
                media.media_type = 'image'
            else:
                full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'media', filename)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                file.save(full_path)
                media.file_path = 'uploads/media/' + filename
                
                if file_ext in ['.jpg', '.jpeg', '.png', '.gif']:
                    media.media_type = 'image'
                elif file_ext in ['.mp4', '.mov']:
                    media.media_type = 'video'
                elif file_ext == '.pdf':
                    media.media_type = 'pdf'
                else:
                    flash('Formato de arquivo não suportado.', 'danger')
                    return redirect(request.url)
        
        db.session.commit()
        flash('Mídia atualizada com sucesso!', 'success')
        return redirect(url_for('edification.gallery'))
    
    return render_template('edification/edit_media.html', media=media, ministries=ministries)

# Nova rota para excluir mídia
@edification_bp.route('/media/<int:id>/delete')
@login_required
def delete_media(id):
    media = Media.query.get_or_404(id)
    
    # Permissão: dono, líder ou admin
    if not (current_user.can_manage_media or (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']) or (media.ministry and media.ministry.leader_id == current_user.id)):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.gallery'))
    
    # Delete file from disk if exists
    if media.file_path and os.path.exists(current_app.config['UPLOAD_FOLDER'] + '/' + media.file_path.replace('uploads/', '')):
        os.remove(current_app.config['UPLOAD_FOLDER'] + '/' + media.file_path.replace('uploads/', ''))
    
    db.session.delete(media)
    db.session.commit()
    flash('Mídia excluída com sucesso!', 'info')
    return redirect(url_for('edification.gallery'))