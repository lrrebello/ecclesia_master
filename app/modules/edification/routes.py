from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app.core.models import db, Devotional, Study, KidsActivity, StudyQuestion, Media, Ministry, Album, BibleStory, BibleQuiz
from datetime import datetime
from werkzeug.utils import secure_filename
import os
import json
from PIL import Image
import pillow_heif
from app.utils.text_extractor import extract_text
from app.utils.gemini_service import generate_questions

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
        title = request.form.get('title')
        content = request.form.get('content')
        category = request.form.get('category')
        
        file = request.files.get('study_file')
        file_path = None
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            try:
                extracted_text = extract_text(file_path)
                if not content:
                    content = extracted_text
            except Exception as e:
                flash(f'Erro ao extrair texto do arquivo: {str(e)}', 'warning')

        new_study = Study(
            title=title,
            content=content,
            category=category,
            author_id=current_user.id
        )
        db.session.add(new_study)
        db.session.commit()
        
        if request.form.get('generate_ai_questions'):
            try:
                if file_path:
                    ai_data = generate_questions(file_path, type='adult', count=10, is_file=True)
                elif content and len(content.strip()) >= 100:
                    ai_data = generate_questions(content, type='adult', count=10)
                else:
                    flash('Conteúdo insuficiente para gerar questões com IA.', 'warning')
                    ai_data = {}
                
                if "error" in ai_data:
                    flash(f'Erro na IA: {ai_data["error"]}', 'danger')
                elif "questions" in ai_data:
                    for q_data in ai_data["questions"]:
                        new_q = StudyQuestion(
                            study_id=new_study.id,
                            question_text=q_data["question"],
                            options=json.dumps(q_data["options"]),
                            correct_option=q_data["correct_option"],
                            explanation=q_data.get("explanation"),
                            is_published=False
                        )
                        db.session.add(new_q)
                    db.session.commit()
                    flash('Estudo adicionado e questões geradas pela IA aguardando revisão!', 'success')
                    return redirect(url_for('edification.review_study_questions', study_id=new_study.id))
            except Exception as e:
                flash(f'Erro ao gerar questões: {str(e)}', 'danger')
        
        flash('Estudo publicado com sucesso!', 'success')
        return redirect(url_for('edification.studies'))
    
    return render_template('edification/add_study.html')

@edification_bp.route('/study/<int:study_id>/review-questions', methods=['GET', 'POST'])
@login_required
def review_study_questions(study_id):
    if not can_publish_content():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.studies'))
    
    study = Study.query.get_or_404(study_id)
    questions = StudyQuestion.query.filter_by(study_id=study_id).all()
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'regenerate':
            StudyQuestion.query.filter_by(study_id=study_id, is_published=False).delete()
            ai_data = generate_questions(study.content, type='adult', count=10)
            if "questions" in ai_data:
                for q_data in ai_data["questions"]:
                    new_q = StudyQuestion(
                        study_id=study_id,
                        question_text=q_data["question"],
                        options=json.dumps(q_data["options"]),
                        correct_option=q_data["correct_option"],
                        explanation=q_data.get("explanation"),
                        is_published=False
                    )
                    db.session.add(new_q)
                db.session.commit()
                flash('Novas questões geradas!', 'success')
            return redirect(url_for('edification.review_study_questions', study_id=study_id))
        
        published_ids = request.form.getlist('publish_ids[]')
        for q in questions:
            q.question_text = request.form.get(f'question_{q.id}')
            q.correct_option = request.form.get(f'correct_{q.id}')
            q.is_published = str(q.id) in published_ids
        
        db.session.commit()
        flash('Questões revisadas e publicadas!', 'success')
        return redirect(url_for('edification.study_detail', id=study_id))
        
    return render_template('edification/review_questions.html', study=study, questions=questions)

@edification_bp.route('/kids')
@login_required
def kids():
    is_kids_ministry_member = any(m.is_kids_ministry for m in current_user.ministries)
    has_permission = current_user.can_manage_kids or (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder'])
    
    if not has_permission and not is_kids_ministry_member:
        flash('Acesso negado. Espaço restrito ao Ministério Kids.', 'danger')
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
    if not current_user.can_manage_kids and not (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']): 
        return redirect(url_for('edification.kids'))
    
    title = request.form.get('title')
    content = request.form.get('content')
    image_path = request.form.get('image_path')
    
    file = request.files.get('story_file')
    file_path = None
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        try:
            extracted_text = extract_text(file_path)
            if not content:
                content = extracted_text
        except Exception as e:
            flash(f'Erro ao extrair texto do arquivo: {str(e)}', 'warning')

    new_story = BibleStory(
        title=title,
        content=content,
        reference=request.form.get('reference'),
        image_path=image_path,
        order=request.form.get('order', 0)
    )
    db.session.add(new_story)
    db.session.commit()

    if request.form.get('generate_ai_questions'):
        try:
            if file_path:
                ai_data = generate_questions(file_path, type='kids', count=7, is_file=True)
            elif content and len(content.strip()) >= 100:
                ai_data = generate_questions(content, type='kids', count=7)
            else:
                flash('Conteúdo insuficiente para gerar questões com IA.', 'warning')
                ai_data = {}

            if "error" in ai_data:
                flash(f'Erro na IA: {ai_data["error"]}', 'danger')
            elif "questions" in ai_data:
                for q_data in ai_data["questions"]:
                    new_q = BibleQuiz(
                        story_id=new_story.id,
                        question=q_data["question"],
                        option_a=q_data["options"].get("A"),
                        option_b=q_data["options"].get("B"),
                        option_c=q_data["options"].get("C"),
                        option_d=q_data["options"].get("D"),
                        correct_option=q_data["correct_option"],
                        explanation=q_data.get("explanation"),
                        is_published=False
                    )
                    db.session.add(new_q)
                
                if "game_words" in ai_data:
                    new_story.game_data = json.dumps(ai_data["game_words"])
                
                db.session.commit()
                flash('História adicionada e questões geradas pela IA aguardando revisão!', 'success')
                return redirect(url_for('edification.review_kids_questions', story_id=new_story.id))
        except Exception as e:
            flash(f'Erro ao gerar questões: {str(e)}', 'danger')

    flash('História adicionada!', 'success')
    return redirect(url_for('edification.manage_kids'))

@edification_bp.route('/kids/story/<int:story_id>/review-questions', methods=['GET', 'POST'])
@login_required
def review_kids_questions(story_id):
    if not current_user.can_manage_kids and not (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']): 
        return redirect(url_for('edification.kids'))
    
    story = BibleStory.query.get_or_404(story_id)
    questions = BibleQuiz.query.filter_by(story_id=story_id).all()
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'regenerate':
            BibleQuiz.query.filter_by(story_id=story_id, is_published=False).delete()
            ai_data = generate_questions(story.content, type='kids', count=7)
            if "questions" in ai_data:
                for q_data in ai_data["questions"]:
                    new_q = BibleQuiz(
                        story_id=story_id,
                        question=q_data["question"],
                        option_a=q_data["options"].get("A"),
                        option_b=q_data["options"].get("B"),
                        option_c=q_data["options"].get("C"),
                        option_d=q_data["options"].get("D"),
                        correct_option=q_data["correct_option"],
                        explanation=q_data.get("explanation"),
                        is_published=False
                    )
                    db.session.add(new_q)
                db.session.commit()
                flash('Novas questões geradas!', 'success')
            return redirect(url_for('edification.review_kids_questions', story_id=story_id))
        
        published_ids = request.form.getlist('publish_ids[]')
        for q in questions:
            q.question = request.form.get(f'question_{q.id}')
            q.correct_option = request.form.get(f'correct_{q.id}')
            q.is_published = str(q.id) in published_ids
        
        db.session.commit()
        flash('Questões infantis revisadas e publicadas!', 'success')
        return redirect(url_for('edification.manage_kids'))
        
    return render_template('edification/review_kids_questions.html', story=story, questions=questions)

@edification_bp.route('/kids/story/delete/<int:id>')
@login_required
def delete_bible_story(id):
    if not current_user.can_manage_kids and not (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']): 
        return redirect(url_for('edification.kids'))
    story = BibleStory.query.get_or_404(id)
    db.session.delete(story)
    db.session.commit()
    flash('História removida.', 'info')
    return redirect(url_for('edification.manage_kids'))

@edification_bp.route('/kids/activity/add', methods=['GET', 'POST'])
@login_required
def add_kids_activity():
    if not current_user.can_manage_kids and not (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.kids'))
    
    if request.method == 'POST':
        new_act = KidsActivity(
            title=request.form.get('title'),
            description=request.form.get('description'),
            age_group=request.form.get('age_group')
        )
        db.session.add(new_act)
        db.session.commit()
        flash('Atividade adicionada!', 'success')
        return redirect(url_for('edification.manage_kids'))
    
    return render_template('edification/add_kids.html')

@edification_bp.route('/kids/memory-game')
@login_required
def memory_game():
    return render_template('edification/kids_memory_game.html')

@edification_bp.route('/kids/who-am-i')
@login_required
def who_am_i():
    return render_template('edification/kids_who_am_i.html')

@edification_bp.route('/kids/puzzle')
@login_required
def puzzle_game():
    story_id = request.args.get('story_id')
    if story_id:
        story = BibleStory.query.get_or_404(story_id)
        image_url = story.image_path or url_for('static', filename='img/kids_default.jpg')
    else:
        image_url = url_for('static', filename='img/kids_default.jpg')
    
    return render_template('edification/kids_puzzle.html', image_url=image_url)

@edification_bp.route('/kids/word-search')
@login_required
def word_search():
    story_id = request.args.get('story_id')
    if story_id:
        story = BibleStory.query.get_or_404(story_id)
        game_data = json.loads(story.game_data) if story.game_data else []
    else:
        game_data = []
    
    return render_template('edification/kids_word_search.html', game_data=game_data)

@edification_bp.route('/kids/crossword')
@login_required
def crossword():
    story_id = request.args.get('story_id')
    if story_id:
        story = BibleStory.query.get_or_404(story_id)
        game_data = json.loads(story.game_data) if story.game_data else []
    else:
        game_data = []
    
    return render_template('edification/kids_crossword.html', game_data=game_data)

@edification_bp.route('/kids/story/<int:id>')
@login_required
def view_bible_story(id):
    story = BibleStory.query.get_or_404(id)
    return render_template('edification/view_bible_story.html', story=story)

@edification_bp.route('/gallery')
@login_required
def gallery():
    albums = Album.query.order_by(Album.created_at.desc()).all()
    return render_template('edification/gallery.html', albums=albums)

@edification_bp.route('/gallery/album/<int:id>')
@login_required
def gallery_album(id):
    album = Album.query.get_or_404(id)
    return render_template('edification/gallery_album.html', album=album)

@edification_bp.route('/media/add', methods=['GET', 'POST'])
@login_required
def add_media():
    if not can_publish_content():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.gallery'))
    
    if request.method == 'POST':
        album_id = request.form.get('album_id')
        files = request.files.getlist('media_files')
        
        for file in files:
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                new_media = Media(
                    title=request.form.get('title') or filename,
                    file_path=filename,
                    media_type='image',
                    album_id=album_id
                )
                db.session.add(new_media)
        
        db.session.commit()
        flash('Mídia adicionada!', 'success')
        return redirect(url_for('edification.gallery_album', id=album_id))
    
    albums = Album.query.all()
    return render_template('edification/add_media.html', albums=albums)
