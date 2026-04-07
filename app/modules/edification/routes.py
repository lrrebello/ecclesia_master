from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app.core.models import (db, Devotional, Study, KidsActivity, StudyQuestion, 
                             Media, Ministry, Album, BibleStory, BibleQuiz, User,
                             StudyProgress, StudyHighlight, StudyNote)
from app.utils.logger import log_action
from datetime import datetime
from PIL import Image
from werkzeug.utils import secure_filename
from sqlalchemy import func
import os
import json
import pillow_heif
from app.utils.text_extractor import extract_text
from app.utils.gemini_service import generate_questions
import markdown
import bleach
import unicodedata

def remover_acentos(texto):
    """Remove acentos de uma string"""
    if not texto:
        return texto
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    return texto

# Lista de tags HTML permitidas (segurança)
ALLOWED_TAGS = [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'br', 'hr',
    'strong', 'b', 'em', 'i', 'u', 'mark',
    'ul', 'ol', 'li',
    'a', 'img',
    'blockquote', 'pre', 'code',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'div', 'span'
]

# Atributos permitidos
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'div': ['class'],
    'span': ['class'],
    'code': ['class'],
    'pre': ['class']
}

# Registra suporte a HEIC
pillow_heif.register_heif_opener()

edification_bp = Blueprint('edification', __name__)

# ============================================
# FUNÇÕES AUXILIARES DE PERMISSÃO (CORRIGIDAS - VERSÃO ROBUSTA)
# ============================================

def is_ministry_leader(ministry):
    """Verifica se o usuário atual é líder/vice ou está na lista extra"""
    if not current_user.is_authenticated or not ministry:
        return False
    
    # Verifica líder e vice
    if ministry.leader_id == current_user.id or ministry.vice_leader_id == current_user.id:
        return True
    
    # Verifica na lista extra
    if ministry.extra_leaders and current_user.id in ministry.extra_leaders:
        return True
    
    return False

def can_manage_media_globally():
    """Verifica se o usuário pode gerenciar mídia globalmente (admin, pastor, ou permissão específica)"""
    if not current_user.is_authenticated:
        return False
    
    return (
        current_user.can_manage_media or 
        (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder'])
    )

def can_manage_media_for_ministry(ministry):
    """Verifica se o usuário pode gerenciar mídia para um ministério específico"""
    if not current_user.is_authenticated:
        return False
    
    if can_manage_media_globally():
        return True
    return is_ministry_leader(ministry)

def get_user_managed_ministries():
    """Retorna lista de ministérios que o usuário pode gerenciar (para exibir no select)"""
    if not current_user.is_authenticated:
        return []
    
    if can_manage_media_globally():
        return Ministry.query.filter_by(church_id=current_user.church_id).all()
    
    # Filtra ministérios onde o usuário é líder (incluindo vice e extra)
    all_ministries = Ministry.query.filter_by(church_id=current_user.church_id).all()
    return [m for m in all_ministries if is_ministry_leader(m)]

def can_publish_content():
    """Verifica se pode publicar conteúdo (devocionais, estudos)"""
    if not current_user.is_authenticated:
        return False
    
    return (
        current_user.can_publish_devotionals or 
        (current_user.church_role and (
            current_user.church_role.name == 'Administrador Global' or
            current_user.church_role.is_lead_pastor
        ))
    )

def can_manage_kids():
    """Verifica se pode gerenciar conteúdo do Espaço Kids"""
    # 🔥 PRIMEIRA LINHA: usuário não autenticado NÃO pode gerenciar
    if not current_user.is_authenticated:
        return False
    
    # Usuário com permissão específica
    if current_user.can_manage_kids:
        return True
    
    # Admin global ou pastor líder
    if current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder']:
        return True
    
    # Verifica se é líder do ministério kids
    for m in current_user.ministries:
        if m.is_kids_ministry and is_ministry_leader(m):
            return True
    
    return False

def can_delete_album(album):
    """Verifica se pode deletar um álbum"""
    if not current_user.is_authenticated:
        return False
    
    if can_manage_media_globally():
        return True
    if album.ministry and is_ministry_leader(album.ministry):
        return True
    return False

def can_delete_media(media):
    """Verifica se pode deletar uma mídia"""
    if not current_user.is_authenticated:
        return False
    
    if can_manage_media_globally():
        return True
    if media.ministry and is_ministry_leader(media.ministry):
        return True
    return False

def can_edit_media(media):
    """Verifica se pode editar uma mídia"""
    if not current_user.is_authenticated:
        return False
    
    if can_manage_media_globally():
        return True
    if media.ministry and is_ministry_leader(media.ministry):
        return True
    return False

# ============================================
# FUNÇÃO DE COMPRESSÃO DE IMAGEM
# ============================================

def compress_and_resize_image(img):
    """Redimensiona (se maior que 1920px) e comprime imagem para web."""
    max_width = 1920
    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.LANCZOS)
    
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    
    return img

# ============================================
# ROTAS DEVOCIONAIS
# ============================================

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
        
        log_action(
            action='CREATE',
            module='DEVOTIONAL',
            description=f"Novo devocional: {new_dev.title}",
            new_values={'id': new_dev.id, 'title': new_dev.title},
            church_id=current_user.church_id
        )
        
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
    old_values = {'title': dev.title, 'verse': dev.verse}
    
    if request.method == 'POST':
        dev.title = request.form.get('title')
        dev.content = request.form.get('content')
        dev.verse = request.form.get('verse')
        dev.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        db.session.commit()
        
        log_action(
            action='UPDATE',
            module='DEVOTIONAL',
            description=f"Devocional editado: {dev.title}",
            old_values=old_values,
            new_values={'title': dev.title, 'verse': dev.verse},
            church_id=current_user.church_id
        )
        
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
    dev_data = {'id': dev.id, 'title': dev.title}
    
    log_action(
        action='DELETE',
        module='DEVOTIONAL',
        description=f"Devocional excluído: {dev_data['title']}",
        old_values=dev_data,
        church_id=current_user.church_id
    )
    
    db.session.delete(dev)
    db.session.commit()
    flash('Devocional excluído!', 'info')
    return redirect(url_for('edification.list_devotionals'))

# ============================================
# ROTAS DE ESTUDOS
# ============================================

@edification_bp.route('/studies')
@login_required
def studies():
    # Parâmetros de busca
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    page = request.args.get('page', 1, type=int)
    per_page = 9
    
    query = Study.query
    
    if search:
        # 🔥 CORREÇÃO: Remover busca por autor que causa erro
        query = query.filter(
            or_(
                Study.title.ilike(f'%{search}%'),
                Study.content.ilike(f'%{search}%')
            )
        )
    
    if category:
        query = query.filter(Study.category == category)
    
    # Ordenar por data decrescente
    query = query.order_by(Study.created_at.desc())
    
    # Paginação
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    studies = pagination.items
    
    # Obter categorias únicas para o filtro
    categories = db.session.query(Study.category).distinct().filter(Study.category.isnot(None)).all()
    categories = [c[0] for c in categories if c[0]]
    
    # Estatísticas
    total_reads = 0  # Implementar se tiver contador de visualizações
    total_questions = StudyQuestion.query.filter_by(is_published=True).count()
    recent_count = Study.query.filter(
        Study.created_at >= datetime.now().replace(day=1)
    ).count()
    
    return render_template('edification/studies.html', 
                         studies=studies,
                         categories=categories,
                         pagination=pagination,
                         total_reads=total_reads,
                         total_questions=total_questions,
                         recent_count=recent_count)

@edification_bp.route('/study/<int:id>')
@login_required
def study_detail(id):
    study = Study.query.get_or_404(id)
    
    # Buscar estudos relacionados
    related_studies = Study.query.filter(
        Study.category == study.category,
        Study.id != study.id
    ).order_by(Study.created_at.desc()).limit(3).all()
    
    # 🔥 CONVERTER CONTEÚDO DE MARKDOWN PARA HTML
    if study.content:
        md = markdown.Markdown(extensions=[
            'extra',
            'fenced_code',
            'tables',
            'nl2br'
        ])
        html_content = md.convert(study.content)
        
        content_html = bleach.clean(
            html_content,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            strip=True
        )
    else:
        content_html = '<p>Nenhum conteúdo disponível.</p>'
    
    # 🔥 PAGINAÇÃO: Dividir o conteúdo por parágrafos
    # Dividir o HTML em parágrafos individuais
    import re
    paragraphs = re.split(r'(</p>)', content_html)
    # Reconstruir parágrafos completos
    full_paragraphs = []
    for i in range(0, len(paragraphs)-1, 2):
        if i+1 < len(paragraphs):
            full_paragraphs.append(paragraphs[i] + paragraphs[i+1])
    if len(paragraphs) % 2 == 1:
        full_paragraphs.append(paragraphs[-1])
    
    # Configuração de paginação
    items_per_page = 5  # Parágrafos por página
    total_pages = max(1, (len(full_paragraphs) + items_per_page - 1) // items_per_page)
    current_page = request.args.get('page', 1, type=int)
    current_page = max(1, min(current_page, total_pages))
    
    # Calcular índices
    start_idx = (current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_paragraphs = full_paragraphs[start_idx:end_idx]
    
    # Reconstruir o HTML da página atual
    page_content_html = ''.join(page_paragraphs)
    
    # Adicionar indicador de página (opcional)
    if total_pages > 1:
        page_indicator = f'<div class="alert alert-info text-center small py-1 mb-3"><i class="bi bi-bookmark me-1"></i> Página {current_page} de {total_pages}</div>'
        page_content_html = page_indicator + page_content_html
    
    return render_template('edification/study_detail.html', 
                         study=study, 
                         content_html=page_content_html,
                         related_studies=related_studies,
                         current_page=current_page,
                         total_pages=total_pages,
                         study_id=study.id)

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
        
        log_action(
            action='CREATE',
            module='STUDY',
            description=f"Novo estudo: {new_study.title}",
            new_values={'id': new_study.id, 'title': new_study.title},
            church_id=current_user.church_id
        )
        
        if request.form.get('generate_ai_questions'):
            question_count = 7
            try:
                if file_path:
                    ai_data = generate_questions(file_path, type='adult', count=question_count, is_file=True)
                elif content and len(content.strip()) >= 100:
                    ai_data = generate_questions(content, type='adult', count=question_count)
                else:
                    flash('Conteúdo insuficiente para gerar questões com IA.', 'warning')
                    ai_data = {}
                
                if "error" in ai_data:
                    flash(f'Erro na IA: {ai_data["error"]}', 'danger')
                elif "questions" in ai_data:
                    for q_data in ai_data["questions"]:
                        correct_letter = q_data["correct_option"].upper()
                        new_q = StudyQuestion(
                            study_id=new_study.id,
                            question_text=q_data["question"],
                            options=json.dumps(q_data["options"]),
                            correct_option=correct_letter,
                            explanation=q_data.get("explanation"),
                            is_published=False
                        )
                        db.session.add(new_q)
                    db.session.commit()
                    
                    log_action(
                        action='GENERATE',
                        module='STUDY_QUESTIONS',
                        description=f"Questões geradas por IA para estudo: {new_study.title}",
                        new_values={'study_id': new_study.id, 'questions_count': len(ai_data["questions"])},
                        church_id=current_user.church_id
                    )
                    
                    flash(f'{len(ai_data["questions"])} questões geradas pela IA aguardando revisão!', 'success')
                    return redirect(url_for('edification.review_study_questions', study_id=new_study.id))
            except Exception as e:
                flash(f'Erro ao gerar questões: {str(e)}', 'warning')
        
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
            old_questions = [{'id': q.id, 'text': q.question_text} for q in questions]
            
            StudyQuestion.query.filter_by(study_id=study_id, is_published=False).delete()
            question_count = 7
            ai_data = generate_questions(study.content, type='adult', count=question_count)
            if "questions" in ai_data:
                correct_map = {'A': 1, 'B': 2, 'C': 3, 'D': 4}
                for q_data in ai_data["questions"]:
                    correct_option = correct_map.get(q_data["correct_option"].upper(), 1)
                    new_q = StudyQuestion(
                        study_id=study_id,
                        question_text=q_data["question"],
                        options=json.dumps(q_data["options"]),
                        correct_option=correct_option,
                        explanation=q_data.get("explanation"),
                        is_published=False
                    )
                    db.session.add(new_q)
                db.session.commit()
                
                log_action(
                    action='REGENERATE',
                    module='STUDY_QUESTIONS',
                    description=f"Questões regeneradas para estudo: {study.title}",
                    old_values={'old_questions': old_questions},
                    new_values={'new_questions_count': len(ai_data["questions"])},
                    church_id=current_user.church_id
                )
                
                flash('Novas questões geradas com sucesso!', 'success')
            return redirect(url_for('edification.review_study_questions', study_id=study_id))
        
        published_ids = request.form.getlist('publish_ids[]')
        correct_map = {'A': 1, 'B': 2, 'C': 3, 'D': 4}
        for q in questions:
            old_text = q.question_text
            old_correct = q.correct_option
            
            q.question_text = request.form.get(f'question_{q.id}')
            q.correct_option = correct_map.get(request.form.get(f'correct_{q.id}'), 1)
            q.is_published = str(q.id) in published_ids
            
            if old_text != q.question_text or old_correct != q.correct_option:
                log_action(
                    action='UPDATE',
                    module='STUDY_QUESTIONS',
                    description="Questão de estudo editada",
                    old_values={'text': old_text, 'correct': old_correct},
                    new_values={'text': q.question_text, 'correct': q.correct_option},
                    church_id=current_user.church_id
                )
        
        db.session.commit()
        
        log_action(
            action='PUBLISH',
            module='STUDY_QUESTIONS',
            description=f"Questões publicadas para estudo: {study.title}",
            new_values={'published_count': len(published_ids)},
            church_id=current_user.church_id
        )
        
        flash('Questões revisadas e publicadas!', 'success')
        return redirect(url_for('edification.study_detail', id=study_id))
        
    return render_template('edification/review_questions.html', study=study, questions=questions)

@edification_bp.route('/study/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_study(id):
    if not can_publish_content():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.studies'))
    
    study = Study.query.get_or_404(id)
    old_values = {'title': study.title, 'category': study.category}
    
    if request.method == 'POST':
        study.title = request.form.get('title')
        study.content = request.form.get('content')
        study.category = request.form.get('category')
        
        regenerate_questions = 'regenerate_questions' in request.form
        
        db.session.commit()
        
        log_action(
            action='UPDATE',
            module='STUDY',
            description=f"Estudo editado: {study.title}",
            old_values=old_values,
            new_values={'title': study.title, 'category': study.category},
            church_id=current_user.church_id
        )
        
        flash('Estudo atualizado com sucesso!', 'success')
        
        if regenerate_questions:
            StudyQuestion.query.filter_by(study_id=study.id).delete()
            
            question_count = 7
            try:
                ai_data = generate_questions(study.content, type='adult', count=question_count)
                
                if "error" in ai_data:
                    flash(f'Erro na IA: {ai_data["error"]}', 'danger')
                elif "questions" in ai_data:
                    for q_data in ai_data["questions"]:
                        correct_letter = q_data["correct_option"].upper()
                        new_q = StudyQuestion(
                            study_id=study.id,
                            question_text=q_data["question"],
                            options=json.dumps(q_data["options"]),
                            correct_option=correct_letter,
                            explanation=q_data.get("explanation"),
                            is_published=False
                        )
                        db.session.add(new_q)
                    db.session.commit()
                    
                    log_action(
                        action='GENERATE',
                        module='STUDY_QUESTIONS',
                        description=f"Questões regeneradas para estudo: {study.title}",
                        new_values={'study_id': study.id, 'questions_count': len(ai_data["questions"])},
                        church_id=current_user.church_id
                    )
                    
                    flash(f'{len(ai_data["questions"])} novas questões geradas pela IA aguardando revisão!', 'success')
                    return redirect(url_for('edification.review_study_questions', study_id=study.id))
            except Exception as e:
                flash(f'Erro ao regenerar questões: {str(e)}', 'warning')
        
        return redirect(url_for('edification.studies'))
    
    return render_template('edification/edit_study.html', study=study)

@edification_bp.route('/study/delete/<int:id>', methods=['POST'])
@login_required
def delete_study(id):
    if not can_publish_content():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.studies'))
    
    study = Study.query.get_or_404(id)
    study_data = {'id': study.id, 'title': study.title}
    
    StudyQuestion.query.filter_by(study_id=id).delete()
    
    log_action(
        action='DELETE',
        module='STUDY',
        description=f"Estudo excluído: {study_data['title']}",
        old_values=study_data,
        church_id=current_user.church_id
    )
    
    db.session.delete(study)
    db.session.commit()
    
    flash('Estudo e suas questões excluídos com sucesso!', 'info')
    return redirect(url_for('edification.studies'))

# ============================================
# ROTAS PARA ANOTAÇÕES E MARCAÇÕES
# ============================================

@edification_bp.route('/study/<int:study_id>/notes', methods=['GET'])
@login_required
def get_study_notes(study_id):
    """Buscar anotações do usuário para este estudo"""
    notes = StudyNote.query.filter_by(
        user_id=current_user.id,
        study_id=study_id
    ).order_by(StudyNote.created_at.desc()).all()
    
    return jsonify([{
        'id': n.id,
        'text': n.text,
        'note': n.note,
        'created_at': n.created_at.strftime('%d/%m/%Y %H:%M')
    } for n in notes])


@edification_bp.route('/study/<int:study_id>/note', methods=['POST'])
@login_required
def add_study_note(study_id):
    """Adicionar uma anotação"""
    data = request.get_json()
    
    note = StudyNote(
        user_id=current_user.id,
        study_id=study_id,
        text=data.get('text', ''),
        note=data.get('note', ''),
        page=data.get('page', 1)
    )
    db.session.add(note)
    db.session.commit()
    
    return jsonify({'success': True, 'id': note.id})


@edification_bp.route('/study/note/<int:note_id>', methods=['DELETE'])
@login_required
def delete_study_note(note_id):
    """Excluir uma anotação"""
    note = StudyNote.query.get_or_404(note_id)
    
    if note.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    db.session.delete(note)
    db.session.commit()
    
    return jsonify({'success': True})


@edification_bp.route('/study/<int:study_id>/highlights', methods=['GET'])
@login_required
def get_study_highlights(study_id):
    """Buscar marcações do usuário"""
    highlights = StudyHighlight.query.filter_by(
        user_id=current_user.id,
        study_id=study_id
    ).all()
    
    return jsonify([{
        'id': h.id,
        'text': h.text,
        'note': h.note,
        'color': h.color
    } for h in highlights])


@edification_bp.route('/study/<int:study_id>/highlight', methods=['POST'])
@login_required
def add_study_highlight(study_id):
    """Adicionar uma marcação com anotação"""
    data = request.get_json()
    
    highlight = StudyHighlight(
        user_id=current_user.id,
        study_id=study_id,
        text=data.get('text', ''),
        note=data.get('note', ''),
        color=data.get('color', 'yellow')
    )
    db.session.add(highlight)
    db.session.commit()
    
    return jsonify({'success': True, 'id': highlight.id})


@edification_bp.route('/study/highlight/<int:highlight_id>', methods=['DELETE'])
@login_required
def delete_study_highlight(highlight_id):
    """Excluir uma marcação"""
    highlight = StudyHighlight.query.get_or_404(highlight_id)
    
    if highlight.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    db.session.delete(highlight)
    db.session.commit()
    
    return jsonify({'success': True})


@edification_bp.route('/study/<int:study_id>/progress', methods=['GET', 'POST'])
@login_required
def study_progress(study_id):
    """Salvar ou carregar progresso do usuário"""
    if request.method == 'POST':
        data = request.get_json()
        page = data.get('page', 1)
        
        progress = StudyProgress.query.filter_by(
            user_id=current_user.id,
            study_id=study_id
        ).first()
        
        if not progress:
            progress = StudyProgress(
                user_id=current_user.id,
                study_id=study_id,
                last_page=page
            )
            db.session.add(progress)
        else:
            progress.last_page = page
            progress.last_access = datetime.utcnow()
        
        db.session.commit()
        return jsonify({'success': True})
    
    else:
        progress = StudyProgress.query.filter_by(
            user_id=current_user.id,
            study_id=study_id
        ).first()
        
        return jsonify({
            'page': progress.last_page if progress else 1,
            'completed': progress.completed if progress else False
        })


@edification_bp.route('/study/<int:study_id>/complete', methods=['POST'])
@login_required
def mark_study_completed(study_id):
    """Marcar estudo como concluído"""
    progress = StudyProgress.query.filter_by(
        user_id=current_user.id,
        study_id=study_id
    ).first()
    
    if not progress:
        progress = StudyProgress(
            user_id=current_user.id,
            study_id=study_id,
            completed=True
        )
        db.session.add(progress)
    else:
        progress.completed = True
    
    db.session.commit()
    return jsonify({'success': True})

# ============================================
# ROTAS DA GALERIA E MÍDIAS
# ============================================

@edification_bp.route('/gallery')
@login_required
def gallery():
    album_id = request.args.get('album_id')
    if album_id:
        album = Album.query.get_or_404(album_id)
        media_items = Media.query.filter_by(album_id=album_id).order_by(Media.created_at.desc()).all()
        return render_template('edification/gallery_album.html', album=album, media_items=media_items)

    query_albums = Album.query.filter_by(church_id=current_user.church_id)
    query_media = Media.query.filter_by(church_id=current_user.church_id, album_id=None)
    
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
    
    events_grouped = {}
    for item in media_items:
        evt = item.event_name or "Geral / Outros"
        if evt not in events_grouped:
            events_grouped[evt] = []
        events_grouped[evt].append(item)
    
    return render_template('edification/gallery.html', albums=albums, events_grouped=events_grouped, ministries=ministries)

@edification_bp.route('/gallery/album/<int:id>')
@login_required
def gallery_album(id):
    album = Album.query.get_or_404(id)
    media_items = Media.query.filter_by(album_id=id).order_by(Media.created_at.desc()).all()
    return render_template('edification/gallery_album.html', album=album, media_items=media_items)

@edification_bp.route('/media/add', methods=['GET', 'POST'])
@login_required
def add_media():
    # VALIDAÇÃO DE PERMISSÃO usando as funções centralizadas
    if not can_manage_media_globally() and not get_user_managed_ministries():
        flash('Acesso negado. Você não tem permissão para adicionar mídias.', 'danger')
        return redirect(url_for('edification.gallery'))
    
    has_global_permission = can_manage_media_globally()
    ministries = get_user_managed_ministries()
    can_upload_to_general = has_global_permission
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        ministry_id = request.form.get('ministry_id')
        event_name = request.form.get('event_name')
        group_as_album = request.form.get('group_as_album') == 'on'
        files = request.files.getlist('file')
        
        # VALIDAÇÃO DO MINISTÉRIO SELECIONADO
        if ministry_id and ministry_id != '':
            ministry_id_int = int(ministry_id)
            selected_ministry = Ministry.query.get(ministry_id_int)
            
            if selected_ministry and not can_manage_media_for_ministry(selected_ministry):
                flash('Você não tem permissão para enviar mídia para este ministério.', 'danger')
                return redirect(url_for('edification.gallery'))
        else:
            if not can_upload_to_general:
                flash('Apenas administradores e pastores podem enviar mídia para o geral da igreja.', 'danger')
                return redirect(url_for('edification.gallery'))
            ministry_id_int = None
        
        if not files or not files[0].filename:
            flash('Nenhum arquivo selecionado.', 'danger')
            return redirect(request.url)
        
        album = None
        album_id = None
        if group_as_album and len(files) > 0:
            album = Album(
                title=title,
                description=description,
                church_id=current_user.church_id,
                ministry_id=ministry_id_int if ministry_id else None
            )
            db.session.add(album)
            db.session.flush()
            album_id = album.id
            
            log_action(
                action='CREATE',
                module='ALBUM',
                description=f"Novo álbum criado via upload: {album.title}",
                new_values={'id': album.id, 'title': album.title},
                church_id=current_user.church_id
            )
        
        count = 0
        for idx, file in enumerate(files):
            filename = secure_filename(file.filename)
            if not filename: continue
            
            file_ext = os.path.splitext(filename)[1].lower()
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{idx}_{filename}"
            
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'media', unique_filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            media_type = 'image'
            try:
                if file_ext == '.heic':
                    img = Image.open(file)
                    img = img.convert('RGB')
                    new_filename = unique_filename.rsplit('.', 1)[0] + '.jpg'
                    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'media', new_filename)
                    img = compress_and_resize_image(img)
                    img.save(full_path, 'JPEG', quality=80, optimize=True)
                    file_path = 'uploads/media/' + new_filename
                else:
                    file.save(full_path)
                    file_path = 'uploads/media/' + unique_filename
                    
                    if file_ext in ['.jpg', '.jpeg', '.png', '.gif']:
                        media_type = 'image'
                        try:
                            img = Image.open(full_path)
                            img = compress_and_resize_image(img)
                            img.save(full_path, 'JPEG', quality=80, optimize=True)
                        except Exception as e:
                            print(f"Erro ao comprimir {filename}: {e}")
                    elif file_ext in ['.mp4', '.mov', '.avi', '.mkv']:
                        media_type = 'video'
                    elif file_ext == '.pdf':
                        media_type = 'pdf'
                    else:
                        flash(f'Formato não suportado: {file_ext}', 'warning')
                        continue
                
                os.chmod(full_path, 0o644)
                
                new_media = Media(
                    title=title if not album else file.filename,
                    description=description,
                    file_path=file_path,
                    media_type=media_type,
                    event_name=event_name,
                    church_id=current_user.church_id,
                    ministry_id=ministry_id_int if ministry_id else None,
                    album_id=album_id
                )
                db.session.add(new_media)
                count += 1
                
            except Exception as e:
                flash(f'Erro ao processar arquivo {filename}: {str(e)}', 'warning')
                continue
            
        db.session.commit()
        
        log_action(
            action='CREATE',
            module='MEDIA',
            description=f"{count} mídia(s) adicionada(s)",
            new_values={'count': count, 'album_id': album_id},
            church_id=current_user.church_id
        )
        
        flash(f'{count} mídias adicionadas com sucesso!', 'success')
        
        if album_id:
            return redirect(url_for('edification.gallery_album', id=album_id))
        else:
            return redirect(url_for('edification.gallery'))
    
    return render_template('edification/add_media.html', 
                         ministries=ministries,
                         can_upload_to_general=can_upload_to_general)

@edification_bp.route('/album/<int:id>/delete')
@login_required
def delete_album(id):
    album = Album.query.get_or_404(id)
    if not can_delete_album(album):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.gallery'))
    
    album_data = {'id': album.id, 'title': album.title}
    
    for media in album.media_items:
        if media.file_path and os.path.exists(current_app.config['UPLOAD_FOLDER'] + '/' + media.file_path.replace('uploads/', '')):
            try:
                os.remove(current_app.config['UPLOAD_FOLDER'] + '/' + media.file_path.replace('uploads/', ''))
            except:
                pass
    
    log_action(
        action='DELETE',
        module='ALBUM',
        description=f"Álbum excluído: {album_data['title']}",
        old_values=album_data,
        church_id=current_user.church_id
    )
    
    db.session.delete(album)
    db.session.commit()
    flash('Álbum e todas as suas mídias foram excluídos.', 'info')
    return redirect(url_for('edification.gallery'))

@edification_bp.route('/media/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_media(id):
    media = Media.query.get_or_404(id)
    
    if not can_edit_media(media):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.gallery'))
    
    old_values = {
        'title': media.title,
        'description': media.description,
        'ministry_id': media.ministry_id
    }
    
    ministries = Ministry.query.filter_by(church_id=current_user.church_id).all()
    
    if request.method == 'POST':
        media.title = request.form.get('title')
        media.description = request.form.get('description')
        media.ministry_id = int(request.form.get('ministry_id')) if request.form.get('ministry_id') else None
        
        file = request.files.get('file')
        if file and file.filename:
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
        
        log_action(
            action='UPDATE',
            module='MEDIA',
            description=f"Mídia editada: {media.title}",
            old_values=old_values,
            new_values={'title': media.title, 'description': media.description},
            church_id=current_user.church_id
        )
        
        flash('Mídia atualizada com sucesso!', 'success')
        return redirect(url_for('edification.gallery'))
    
    return render_template('edification/edit_media.html', media=media, ministries=ministries)

@edification_bp.route('/media/<int:id>/delete')
@login_required
def delete_media(id):
    media = Media.query.get_or_404(id)
    
    if not can_delete_media(media):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.gallery'))
    
    media_data = {'id': media.id, 'title': media.title}
    
    if media.file_path and os.path.exists(current_app.config['UPLOAD_FOLDER'] + '/' + media.file_path.replace('uploads/', '')):
        try:
            os.remove(current_app.config['UPLOAD_FOLDER'] + '/' + media.file_path.replace('uploads/', ''))
        except:
            pass
    
    log_action(
        action='DELETE',
        module='MEDIA',
        description=f"Mídia excluída: {media_data['title']}",
        old_values=media_data,
        church_id=current_user.church_id
    )
    
    db.session.delete(media)
    db.session.commit()
    flash('Mídia excluída com sucesso!', 'info')
    return redirect(url_for('edification.gallery'))

# ============================================
# ROTAS DO ESPAÇO KIDS
# ============================================

@edification_bp.route('/kids')
def kids():
    stories = BibleStory.query.order_by(BibleStory.order.asc()).all()
    activities = KidsActivity.query.order_by(KidsActivity.created_at.desc()).all()
    
    show_admin_buttons = can_manage_kids()
    
    return render_template('edification/kids.html', 
                           stories=stories, 
                           activities=activities,
                           show_admin_buttons=show_admin_buttons)

@edification_bp.route('/kids/manage')
@login_required
def manage_kids():
    if not can_manage_kids():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.kids'))
    
    stories = BibleStory.query.order_by(BibleStory.order.asc()).all()
    activities = KidsActivity.query.order_by(KidsActivity.created_at.desc()).all()
    return render_template('edification/manage_kids.html', stories=stories, activities=activities)

@edification_bp.route('/kids/story/add', methods=['POST'])
@login_required
def add_bible_story():
    if not can_manage_kids():
        flash('Acesso negado.', 'danger')
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
    
    log_action(
        action='CREATE',
        module='KIDS_STORY',
        description=f"Nova história infantil: {new_story.title}",
        new_values={'id': new_story.id, 'title': new_story.title},
        church_id=current_user.church_id
    )

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
                
                log_action(
                    action='GENERATE',
                    module='KIDS_QUESTIONS',
                    description=f"Questões geradas para história: {new_story.title}",
                    new_values={'story_id': new_story.id, 'questions_count': len(ai_data["questions"])},
                    church_id=current_user.church_id
                )
                
                flash('História adicionada e questões geradas pela IA aguardando revisão!', 'success')
                return redirect(url_for('edification.review_kids_questions', story_id=new_story.id))
        except Exception as e:
            flash(f'Erro ao gerar questões: {str(e)}', 'danger')

    flash('História adicionada!', 'success')
    return redirect(url_for('edification.manage_kids'))

@edification_bp.route('/kids/story/<int:story_id>/review-questions', methods=['GET', 'POST'])
@login_required
def review_kids_questions(story_id):
    if not can_manage_kids():
        return redirect(url_for('edification.kids'))
    
    story = BibleStory.query.get_or_404(story_id)
    questions = BibleQuiz.query.filter_by(story_id=story_id).all()
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'regenerate':
            old_questions = [{'id': q.id, 'question': q.question} for q in questions]
            
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
                
                if "game_words" in ai_data:
                    story.game_data = json.dumps(ai_data["game_words"])
                    
                db.session.commit()
                
                log_action(
                    action='REGENERATE',
                    module='KIDS_QUESTIONS',
                    description=f"Questões regeneradas para história: {story.title}",
                    old_values={'old_questions': old_questions},
                    new_values={'new_questions_count': len(ai_data["questions"])},
                    church_id=current_user.church_id
                )
                
                flash('Novas questões geradas!', 'success')
            return redirect(url_for('edification.review_kids_questions', story_id=story_id))
        
        published_ids = request.form.getlist('publish_ids[]')
        for q in questions:
            old_question = q.question
            old_correct = q.correct_option
            
            q.question = request.form.get(f'question_{q.id}')
            q.correct_option = request.form.get(f'correct_{q.id}')
            q.is_published = str(q.id) in published_ids
            
            if old_question != q.question or old_correct != q.correct_option:
                log_action(
                    action='UPDATE',
                    module='KIDS_QUESTIONS',
                    description="Questão infantil editada",
                    old_values={'question': old_question, 'correct': old_correct},
                    new_values={'question': q.question, 'correct': q.correct_option},
                    church_id=current_user.church_id
                )
        
        db.session.commit()
        
        log_action(
            action='PUBLISH',
            module='KIDS_QUESTIONS',
            description=f"Questões publicadas para história: {story.title}",
            new_values={'published_count': len(published_ids)},
            church_id=current_user.church_id
        )
        
        flash('Questões infantis revisadas e publicadas!', 'success')
        return redirect(url_for('edification.manage_kids'))
        
    return render_template('edification/review_kids_questions.html', story=story, questions=questions)

@edification_bp.route('/kids/story/delete/<int:id>')
@login_required
def delete_bible_story(id):
    if not can_manage_kids():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.kids'))
    
    story = BibleStory.query.get_or_404(id)
    story_data = {'id': story.id, 'title': story.title}
    
    log_action(
        action='DELETE',
        module='KIDS_STORY',
        description=f"História infantil excluída: {story_data['title']}",
        old_values=story_data,
        church_id=current_user.church_id
    )
    
    db.session.delete(story)
    db.session.commit()
    flash('História removida.', 'info')
    return redirect(url_for('edification.manage_kids'))

@edification_bp.route('/kids/activity/add', methods=['GET', 'POST'])
@login_required
def add_kids_activity():
    if not can_manage_kids():
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
        
        log_action(
            action='CREATE',
            module='KIDS_ACTIVITY',
            description=f"Nova atividade infantil: {new_act.title}",
            new_values={'id': new_act.id, 'title': new_act.title},
            church_id=current_user.church_id
        )
        
        flash('Atividade adicionada!', 'success')
        return redirect(url_for('edification.manage_kids'))
    
    return render_template('edification/add_kids.html')

@edification_bp.route('/kids/story/<int:id>')
def view_bible_story(id):
    story = BibleStory.query.get_or_404(id)
    return render_template('edification/view_bible_story.html', story=story)

@edification_bp.route('/kids/memory-game')
def memory_game():
    story_id = request.args.get('story_id')
    game_data = []
    story = None
    
    if story_id:
        story = BibleStory.query.get_or_404(int(story_id))
        game_data = json.loads(story.game_data) if story.game_data else []
        # Remover acentos das palavras
        if game_data and isinstance(game_data, list):
            if len(game_data) > 0 and isinstance(game_data[0], dict) and 'word' in game_data[0]:
                for item in game_data:
                    if 'word' in item:
                        item['word'] = remover_acentos(item['word'].upper())
            elif isinstance(game_data[0], str):
                game_data = [remover_acentos(w.upper()) for w in game_data]
    else:
        story = BibleStory.query.order_by(func.random()).first()
        if story:
            game_data = json.loads(story.game_data) if story.game_data else []
            if game_data and isinstance(game_data, list):
                if len(game_data) > 0 and isinstance(game_data[0], dict) and 'word' in game_data[0]:
                    for item in game_data:
                        if 'word' in item:
                            item['word'] = remover_acentos(item['word'].upper())
                elif isinstance(game_data[0], str):
                    game_data = [remover_acentos(w.upper()) for w in game_data]
    
    return render_template('edification/kids_memory_game.html', 
                         game_data=game_data, 
                         story=story)

@edification_bp.route('/kids/who-am-i')
def who_am_i():
    story_id = request.args.get('story_id')
    game_data = []
    story = None
    
    if story_id:
        story = BibleStory.query.get_or_404(int(story_id))
        game_data = json.loads(story.game_data) if story.game_data else []
        # Remover acentos das palavras
        if game_data and isinstance(game_data, list):
            if len(game_data) > 0 and isinstance(game_data[0], dict) and 'word' in game_data[0]:
                for item in game_data:
                    if 'word' in item:
                        item['word'] = remover_acentos(item['word'].upper())
            elif isinstance(game_data[0], str):
                game_data = [remover_acentos(w.upper()) for w in game_data]
    else:
        story = BibleStory.query.order_by(func.random()).first()
        if story:
            game_data = json.loads(story.game_data) if story.game_data else []
            if game_data and isinstance(game_data, list):
                if len(game_data) > 0 and isinstance(game_data[0], dict) and 'word' in game_data[0]:
                    for item in game_data:
                        if 'word' in item:
                            item['word'] = remover_acentos(item['word'].upper())
                elif isinstance(game_data[0], str):
                    game_data = [remover_acentos(w.upper()) for w in game_data]
    
    return render_template('edification/kids_who_am_i.html', 
                         game_data=game_data, 
                         story=story)

@edification_bp.route('/kids/puzzle')
def puzzle_game():
    story_id = request.args.get('story_id')
    if story_id:
        story = BibleStory.query.get_or_404(story_id)
        image_url = story.image_path or url_for('static', filename='img/kids_default.jpg')
    else:
        image_url = url_for('static', filename='img/kids_default.jpg')
    
    return render_template('edification/kids_puzzle.html', image_url=image_url)

@edification_bp.route('/kids/word-search')
def word_search():
    story_id = request.args.get('story_id')
    story = None
    game_data = []
    
    if story_id:
        story = BibleStory.query.get_or_404(int(story_id))
        if story.game_data:
            try:
                data = json.loads(story.game_data) if isinstance(story.game_data, str) else story.game_data
                if data and isinstance(data, list):
                    if len(data) > 0 and isinstance(data[0], dict) and 'word' in data[0]:
                        game_data = [{
                            'word': remover_acentos(item['word'].upper()),
                            'hint': item.get('hint', '')
                        } for item in data if item.get('word')]
                    elif isinstance(data[0], str):
                        game_data = [{
                            'word': remover_acentos(w.upper()),
                            'hint': ''
                        } for w in data]
            except Exception:
                pass
    else:
        story = BibleStory.query.order_by(func.random()).first()
        if story and story.game_data:
            try:
                data = json.loads(story.game_data) if isinstance(story.game_data, str) else story.game_data
                if data and isinstance(data, list):
                    if len(data) > 0 and isinstance(data[0], dict) and 'word' in data[0]:
                        game_data = [{
                            'word': remover_acentos(item['word'].upper()),
                            'hint': item.get('hint', '')
                        } for item in data if item.get('word')]
                    elif isinstance(data[0], str):
                        game_data = [{
                            'word': remover_acentos(w.upper()),
                            'hint': ''
                        } for w in data]
            except Exception:
                pass
    
    return render_template('edification/kids_word_search.html', 
                         story=story, 
                         game_data=game_data)

@edification_bp.route('/kids/crossword')
def crossword():
    story_id = request.args.get('story_id')
    story = None
    if story_id:
        story = BibleStory.query.get_or_404(story_id)
    
    return render_template('edification/kids_crossword.html', story=story)

@edification_bp.route('/kids/hangman')
def hangman():
    from sqlalchemy import func
    import json
    
    story_id = request.args.get('story_id')
    story = None
    game_data = []
    hints_data = {}  # Dicionário de palavra -> dica
    
    if story_id:
        story = BibleStory.query.get_or_404(int(story_id))
        if story.game_data:
            try:
                data = json.loads(story.game_data) if isinstance(story.game_data, str) else story.game_data
                if data and isinstance(data, list):
                    if len(data) > 0 and isinstance(data[0], dict) and 'word' in data[0]:
                        # Formato com hint
                        game_data = [remover_acentos(item['word'].upper()) for item in data if item.get('word')]
                        hints_data = {remover_acentos(item['word'].upper()): item.get('hint', '') for item in data if item.get('word')}
                    elif isinstance(data[0], str):
                        # Formato simples
                        game_data = [remover_acentos(w.upper()) for w in data]
            except Exception:
                pass
    else:
        story = BibleStory.query.order_by(func.random()).first()
        if story and story.game_data:
            try:
                data = json.loads(story.game_data) if isinstance(story.game_data, str) else story.game_data
                if data and isinstance(data, list):
                    if len(data) > 0 and isinstance(data[0], dict) and 'word' in data[0]:
                        game_data = [remover_acentos(item['word'].upper()) for item in data if item.get('word')]
                        hints_data = {remover_acentos(item['word'].upper()): item.get('hint', '') for item in data if item.get('word')}
                    elif isinstance(data[0], str):
                        game_data = [remover_acentos(w.upper()) for w in data]
            except Exception:
                pass
    
    return render_template('edification/kids_hangman.html', 
                         story=story, 
                         game_data=game_data,
                         hints_data=hints_data)

# ============================================
# API ROTAS
# ============================================

@edification_bp.route('/api/emoji-for-word/<word>')
def get_emoji_for_word(word):
    from app.core.models import EmojiWord
    import unicodedata
    
    word_normalized = word.upper().strip()
    word_normalized = unicodedata.normalize('NFKD', word_normalized).encode('ASCII', 'ignore').decode('ASCII')
    
    all_emojis = EmojiWord.query.all()
    
    for emoji_item in all_emojis:
        words = emoji_item.words or []
        for stored_word in words:
            stored_normalized = unicodedata.normalize('NFKD', stored_word.upper()).encode('ASCII', 'ignore').decode('ASCII')
            if word_normalized == stored_normalized:
                return jsonify({'success': True, 'emoji': emoji_item.emoji, 'type': emoji_item.emoji_type, 'custom_icon': emoji_item.custom_icon})
    
    for emoji_item in all_emojis:
        words = emoji_item.words or []
        for stored_word in words:
            stored_normalized = unicodedata.normalize('NFKD', stored_word.upper()).encode('ASCII', 'ignore').decode('ASCII')
            if stored_normalized in word_normalized or word_normalized in stored_normalized:
                return jsonify({'success': True, 'emoji': emoji_item.emoji, 'type': emoji_item.emoji_type, 'custom_icon': emoji_item.custom_icon})
    
    return jsonify({'success': True, 'emoji': word[0].upper() if word else '📖', 'type': 'text'})