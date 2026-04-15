from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify, send_file
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
from weasyprint import HTML
from io import BytesIO
import requests
import tempfile
from urllib.parse import urlparse
import fitz 

def extrair_melhor_imagem_do_pdf(caminho_pdf, largura_minima=200, altura_minima=200):
    """
    Extrai a melhor imagem de um PDF (prioriza a maior em resolução)
    Retorna os bytes da imagem e sua extensão, ou (None, None)
    """
    try:
        doc = fitz.open(caminho_pdf)
        melhor_imagem = None
        melhor_area = 0
        melhor_ext = "jpg"
        
        for pagina_num in range(len(doc)):
            pagina = doc.load_page(pagina_num)
            imagens = pagina.get_images(full=True)
            
            for img in imagens:
                xref = img[0]
                base_img = doc.extract_image(xref)
                imagem_bytes = base_img["image"]
                ext = base_img["ext"]  # jpg, png, etc.
                
                # Verificar tamanho da imagem (extraindo do bytes é mais complicado)
                # Então usamos a área em pixels que o PyMuPDF fornece
                largura = base_img.get("width", 0)
                altura = base_img.get("height", 0)
                area = largura * altura
                
                # Filtrar imagens muito pequenas (ícones, bordas)
                if largura >= largura_minima and altura >= altura_minima:
                    if area > melhor_area:
                        melhor_area = area
                        melhor_imagem = imagem_bytes
                        melhor_ext = ext
        
        doc.close()
        
        if melhor_imagem:
            return melhor_imagem, melhor_ext
        return None, None
        
    except Exception as e:
        print(f"Erro ao extrair imagem do PDF: {e}")
        return None, None
    
def validar_e_comprimir_pdf(caminho_arquivo, tamanho_maximo_mb=10):
    """
    Verifica o tamanho do PDF e comprime se necessário
    Retorna: (caminho_do_arquivo_processado, foi_comprimido)
    """
    tamanho_mb = os.path.getsize(caminho_arquivo) / (1024 * 1024)
    
    if tamanho_mb <= tamanho_maximo_mb:
        print(f"✅ PDF dentro do limite: {tamanho_mb:.2f} MB")
        return caminho_arquivo, False
    
    print(f"⚠️ PDF muito grande: {tamanho_mb:.2f} MB. Comprimindo...")
    
    try:
        from PyPDF2 import PdfReader, PdfWriter
        
        # Ler o PDF original
        leitor = PdfReader(caminho_arquivo)
        escritor = PdfWriter()
        
        # Copiar páginas sem compressão de imagem (PyPDF2 não comprime imagens)
        for pagina in leitor.pages:
            escritor.add_page(pagina)
        
        # Salvar em arquivo temporário
        caminho_comprimido = caminho_arquivo.replace('.pdf', '_comprimido.pdf')
        with open(caminho_comprimido, 'wb') as f:
            escritor.write(f)
        
        tamanho_novo_mb = os.path.getsize(caminho_comprimido) / (1024 * 1024)
        print(f"✅ PDF comprimido: {tamanho_novo_mb:.2f} MB (redução de {(1 - tamanho_novo_mb/tamanho_mb)*100:.1f}%)")
        
        # Substituir o arquivo original pelo comprimido
        os.replace(caminho_comprimido, caminho_arquivo)
        
        return caminho_arquivo, True
        
    except Exception as e:
        print(f"❌ Erro ao comprimir PDF: {str(e)}")
        return caminho_arquivo, False


def dividir_texto_para_ia(texto, tamanho_maximo=6000):
    """
    Divide um texto grande em partes menores para processamento pela IA
    Retorna uma lista de partes
    """
    if not texto:
        return []
    
    # Se o texto for menor que o limite, retorna como uma única parte
    if len(texto) <= tamanho_maximo:
        return [texto]
    
    # Divide por parágrafos
    paragrafos = texto.split('\n\n')
    partes = []
    parte_atual = ""
    
    for paragrafo in paragrafos:
        # Se adicionar este parágrafo ultrapassar o limite
        if len(parte_atual) + len(paragrafo) + 2 > tamanho_maximo:
            if parte_atual:
                partes.append(parte_atual.strip())
            parte_atual = paragrafo
        else:
            if parte_atual:
                parte_atual += "\n\n" + paragrafo
            else:
                parte_atual = paragrafo
    
    # Adiciona a última parte
    if parte_atual:
        partes.append(parte_atual.strip())
    
    return partes

def gerar_imagem_pollinations(prompt_descricao, width=1024, height=1024):
    """
    Gera imagem usando Pollinations.ai - 100% grátis, sem chave
    Retorna os bytes da imagem ou None em caso de erro
    """
    try:
        # Pollinations aceita prompt em texto puro na URL
        # Parâmetros: width, height, seed (opcional), model (flux ou turbo)
        url = f"https://image.pollinations.ai/prompt/{prompt_descricao}?width={width}&height={height}&model=flux"
        
        response = requests.get(url, timeout=60)
        
        if response.status_code == 200:
            return response.content  # bytes da imagem
        print(f"Erro Pollinations: status {response.status_code}")
        return None
    except requests.exceptions.Timeout:
        print("Timeout ao gerar imagem")
        return None
    except Exception as e:
        print(f"Erro ao gerar imagem: {e}")
        return None

def gerar_prompt_para_imagem(historia):
    """
    Gera um prompt otimizado para criar imagem no estilo ilustração infantil fofa
    """
    titulo = historia.title
    referencia = historia.reference or ""
    conteudo = historia.content[:200] if historia.content else ""
    
    # 🔥 NOVO PROMPT - FOCO EM ESTILO FOFO E COLORIDO
    prompt = f"""Create a cute, colorful, friendly children's Bible story illustration:
Story: {titulo}
Scene: {conteudo}

Style requirements:
- Super cute, kawaii, chibi art style
- Bright, vibrant, warm colors (pastels, yellows, soft blues)
- Round faces, big sparkly eyes, friendly smiles
- Soft lighting, no shadows or darkness
- Simple, clean backgrounds
- Like a Pixar/DreamWorks children's book illustration
- Characters should look cuddly and approachable
- For kids aged 3-8

Art style: Digital painting, cartoon, storybook quality, high resolution, colorful, happy, magical feel."""
    
    return prompt.replace('\n', ' ').strip()
    
def download_pdf_from_url(url):
    """Baixa PDF de uma URL e retorna caminho do arquivo temporário"""
    try:
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        
        # Criar arquivo temporário
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                temp_file.write(chunk)
        temp_file.close()
        
        return temp_file.name
    except Exception as e:
        print(f"Erro ao baixar PDF: {str(e)}")
        return None

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

@edification_bp.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Serve arquivos da pasta uploads (PDFs, imagens)"""
    try:
        # Verifica se o arquivo existe
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            return send_file(file_path)
        else:
            # Tenta na pasta media
            media_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'media', filename)
            if os.path.exists(media_path):
                return send_file(media_path)
            
            print(f"Arquivo não encontrado: {file_path}")
            abort(404)
    except Exception as e:
        print(f"Erro ao servir arquivo: {e}")
        abort(404)
        
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
    from app.core.models import StudyProgress
    from sqlalchemy import or_
    
    # Parâmetros de busca
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    page = request.args.get('page', 1, type=int)
    per_page = 9
    
    query = Study.query
    
    if search:
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
    
    # 🔥 ESTUDOS CONCLUÍDOS PELO USUÁRIO
    completed_study_ids = set()
    user_progress = StudyProgress.query.filter_by(
        user_id=current_user.id, 
        completed=True
    ).all()
    for p in user_progress:
        completed_study_ids.add(p.study_id)
    
    completed_count = len(completed_study_ids)
    
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
                         recent_count=recent_count,
                         completed_study_ids=completed_study_ids,
                         completed_count=completed_count)

@edification_bp.route('/study/<int:id>')
@login_required
def study_detail(id):
    study = Study.query.get_or_404(id)
    
    # Buscar estudos relacionados
    related_studies = Study.query.filter(
        Study.category == study.category,
        Study.id != study.id
    ).order_by(Study.created_at.desc()).limit(3).all()
    
    # Converter conteúdo de Markdown para HTML (apenas para exibição)
    if study.content:
        md = markdown.Markdown(extensions=['extra', 'fenced_code', 'tables', 'nl2br'])
        html_content = md.convert(study.content)
        content_html = bleach.clean(html_content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)
    else:
        content_html = '<p>Nenhum conteúdo disponível.</p>'
    
    # Verificar se o estudo já foi concluído
    progress = StudyProgress.query.filter_by(
        user_id=current_user.id,
        study_id=study.id
    ).first()
    is_completed = progress.completed if progress else False
    
    return render_template('edification/study_detail.html', 
                         study=study, 
                         content_html=content_html,  # Envia todo o conteúdo
                         related_studies=related_studies,
                         study_id=study.id,
                         is_completed=is_completed)

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
        
        # 🔥 SEMPRE redirecionar para revisão, com ou sem IA
        generate_ia = request.form.get('generate_ai_questions')
        questions_generated = False
        
        if generate_ia:
            question_count = 7
            try:
                # Verificar tamanho do conteúdo
                content_for_ai = content
                
                if content and len(content) > 8000:
                    flash(f'Conteúdo muito extenso ({len(content)} caracteres). A IA processará apenas os primeiros 6000 caracteres.', 'warning')
                
                if file_path:
                    ai_data = generate_questions(file_path, type='adult', count=question_count, is_file=True)
                elif content_for_ai and len(content_for_ai.strip()) >= 100:
                    ai_data = generate_questions(content_for_ai, type='adult', count=question_count)
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
                    questions_generated = True
                    
                    log_action(
                        action='GENERATE',
                        module='STUDY_QUESTIONS',
                        description=f"Questões geradas por IA para estudo: {new_study.title}",
                        new_values={'study_id': new_study.id, 'questions_count': len(ai_data["questions"])},
                        church_id=current_user.church_id
                    )
                    
                    flash(f'{len(ai_data["questions"])} questões geradas pela IA! Agora você pode revisar e editar.', 'success')
            except Exception as e:
                flash(f'Erro ao gerar questões com IA: {str(e)}', 'warning')
        
        if not questions_generated and generate_ia:
            flash('Não foi possível gerar questões com IA. Você pode adicionar questões manualmente na tela de revisão.', 'info')
        
        # 🔥 SEMPRE redirecionar para a tela de revisão
        return redirect(url_for('edification.review_study_questions', study_id=new_study.id))
    
    return render_template('edification/add_study.html')

@edification_bp.route('/study/<int:study_id>/save-questions', methods=['POST'])
@login_required
def save_study_questions(study_id):
    """Salvar questões do estudo"""
    if not can_publish_content():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.studies'))
    
    study = Study.query.get_or_404(study_id)
    
    # Remover questões existentes
    StudyQuestion.query.filter_by(study_id=study_id).delete()
    
    # Coletar dados do formulário
    question_texts = request.form.getlist('question_text[]')
    option_as = request.form.getlist('option_a[]')
    option_bs = request.form.getlist('option_b[]')
    option_cs = request.form.getlist('option_c[]')
    option_ds = request.form.getlist('option_d[]')
    correct_options = request.form.getlist('correct_option[]')
    explanations = request.form.getlist('explanation[]')
    is_published_list = request.form.getlist('is_published[]')
    
    saved_count = 0
    
    for i in range(len(question_texts)):
        if question_texts[i] and option_as[i] and option_bs[i] and option_cs[i]:
            options = {
                'A': option_as[i],
                'B': option_bs[i],
                'C': option_cs[i]
            }
            if i < len(option_ds) and option_ds[i]:
                options['D'] = option_ds[i]
            
            # Converter correct_option para letra
            correct = correct_options[i] if i < len(correct_options) else 'A'
            if correct in ['1', '2', '3', '4']:
                mapping = {'1': 'A', '2': 'B', '3': 'C', '4': 'D'}
                correct = mapping.get(correct, 'A')
            
            is_published = False
            if i < len(is_published_list):
                is_published = is_published_list[i] == '1'
            
            explanation = explanations[i] if i < len(explanations) else ''
            
            new_q = StudyQuestion(
                study_id=study_id,
                question_text=question_texts[i],
                options=json.dumps(options),
                correct_option=correct,
                explanation=explanation if explanation else None,
                is_published=is_published
            )
            db.session.add(new_q)
            saved_count += 1
    
    db.session.commit()
    
    log_action(
        action='UPDATE',
        module='STUDY_QUESTIONS',
        description=f"Questões atualizadas para estudo: {study.title}",
        church_id=current_user.church_id
    )
    
    flash(f'{saved_count} questões salvas com sucesso!', 'success')
    return redirect(url_for('edification.study_detail', id=study_id))

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
        
        # 🔥 REGENERAR COM IA
        if action == 'regenerate':
            old_questions = [{'id': q.id, 'text': q.question_text} for q in questions]
            
            # Deletar apenas as não publicadas ou todas? Vamos deletar todas e regenerar
            StudyQuestion.query.filter_by(study_id=study_id).delete()
            
            question_count = 7
            ai_data = generate_questions(study.content, type='adult', count=question_count)
            
            if "error" in ai_data:
                flash(f'Erro na IA: {ai_data["error"]}', 'danger')
            elif "questions" in ai_data:
                for q_data in ai_data["questions"]:
                    correct_letter = q_data["correct_option"].upper()
                    new_q = StudyQuestion(
                        study_id=study_id,
                        question_text=q_data["question"],
                        options=json.dumps(q_data["options"]),
                        correct_option=correct_letter,
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
                
                flash(f'{len(ai_data["questions"])} novas questões geradas pela IA! Revise e publique.', 'success')
            return redirect(url_for('edification.review_study_questions', study_id=study_id))
        
        # 🔥 SALVAR QUESTÕES (EDITADAS + NOVAS)
        elif action == 'save':
            try:
                # 1. Atualizar questões existentes
                for q in questions:
                    q.question_text = request.form.get(f'question_{q.id}')
                    q.correct_option = request.form.get(f'correct_{q.id}')
                    q.is_published = f'publish_{q.id}' in request.form
                    
                    # Atualizar opções (A, B, C, D)
                    options = {}
                    for opt in ['A', 'B', 'C', 'D']:
                        opt_value = request.form.get(f'option_{opt.lower()}_{q.id}')
                        if opt_value:
                            options[opt] = opt_value
                    q.options = json.dumps(options) if options else '{}'
                    q.explanation = request.form.get(f'explanation_{q.id}')
                
                # 2. Adicionar novas questões
                new_questions = request.form.getlist('new_question_text')
                for i, q_text in enumerate(new_questions):
                    if q_text and q_text.strip():
                        options = {}
                        for opt in ['A', 'B', 'C', 'D']:
                            opt_value = request.form.get(f'new_option_{opt.lower()}_{i}')
                            if opt_value:
                                options[opt] = opt_value
                        
                        new_q = StudyQuestion(
                            study_id=study_id,
                            question_text=q_text,
                            options=json.dumps(options) if options else '{}',
                            correct_option=request.form.get(f'new_correct_{i}', 'A'),
                            explanation=request.form.get(f'new_explanation_{i}', ''),
                            is_published=f'new_publish_{i}' in request.form
                        )
                        db.session.add(new_q)
                
                db.session.commit()
                
                log_action(
                    action='UPDATE',
                    module='STUDY_QUESTIONS',
                    description=f"Questões revisadas e salvas para estudo: {study.title}",
                    church_id=current_user.church_id
                )
                
                flash('Questões salvas com sucesso!', 'success')
                return redirect(url_for('edification.study_detail', id=study_id))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Erro ao salvar questões: {str(e)}', 'danger')
                return redirect(request.url)
        
        # 🔥 PUBLICAR QUESTÕES (comportamento original)
        elif action == 'publish':
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
    
    # GET - mostrar formulário
    return render_template('edification/review_questions.html', 
                         study=study, 
                         questions=questions,
                         study_id=study_id)


@edification_bp.route('/study/<int:id>/questions')
@login_required
def manage_study_questions(id):
    """Gerenciar questões do estudo"""
    if not can_publish_content():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.studies'))
    
    study = Study.query.get_or_404(id)
    questions = StudyQuestion.query.filter_by(study_id=id).all()

        # 🔥 Processar as opções de cada questão
    for q in questions:
        if q.options:
            try:
                q.options_dict = json.loads(q.options) if isinstance(q.options, str) else q.options
            except:
                q.options_dict = {'A': '', 'B': '', 'C': '', 'D': ''}
        else:
            q.options_dict = {'A': '', 'B': '', 'C': '', 'D': ''}
    
    return render_template('edification/manage_questions.html', 
                         study=study, 
                         questions=questions)


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
        
        # 🔥 Se marcou para regenerar, gerar novas questões
        if regenerate_questions:
            # Remover questões existentes
            StudyQuestion.query.filter_by(study_id=study.id).delete()
            db.session.commit()
            
            try:
                content_for_ai = study.content
                if content_for_ai and len(content_for_ai) > 8000:
                    flash(f'Conteúdo muito extenso ({len(content_for_ai)} caracteres). A IA processará apenas os primeiros 6000 caracteres.', 'warning')
                
                ai_data = generate_questions(content_for_ai, type='adult', count=7)
                
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
                    flash(f'{len(ai_data["questions"])} novas questões geradas pela IA!', 'success')
                else:
                    flash('IA não retornou questões válidas. Você pode adicionar manualmente.', 'warning')
                    
            except Exception as e:
                flash(f'Erro ao regenerar questões: {str(e)}', 'warning')
        
        # 🔥 SEMPRE redirecionar para a tela de revisão (com ou sem IA)
        return redirect(url_for('edification.review_study_questions', study_id=study.id))
    
    # GET - contar questões existentes
    questions_count = StudyQuestion.query.filter_by(study_id=study.id).count()
    
    return render_template('edification/edit_study.html', 
                         study=study,
                         questions_count=questions_count)

@edification_bp.route('/study/delete/<int:id>', methods=['POST'])
@login_required
def delete_study(id):
    if not can_publish_content():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.studies'))
    
    study = Study.query.get_or_404(id)
    study_data = {'id': study.id, 'title': study.title}
    
    # 🔥 IMPORTANTE: Deletar registros relacionados MANUALMENTE antes
    from app.core.models import StudyProgress, StudyHighlight, StudyNote
    
    # Deletar progresso
    StudyProgress.query.filter_by(study_id=id).delete()
    # Deletar highlights
    StudyHighlight.query.filter_by(study_id=id).delete()
    # Deletar anotações
    StudyNote.query.filter_by(study_id=id).delete()
    # Deletar questões
    StudyQuestion.query.filter_by(study_id=id).delete()
    
    # Agora sim, deletar o estudo
    db.session.delete(study)
    db.session.commit()
    
    log_action(
        action='DELETE',
        module='STUDY',
        description=f"Estudo excluído: {study_data['title']}",
        old_values=study_data,
        church_id=current_user.church_id
    )
    
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

@edification_bp.route('/study/<int:study_id>/uncomplete', methods=['POST'])
@login_required
def mark_study_uncompleted(study_id):
    """Desmarcar estudo como concluído"""
    progress = StudyProgress.query.filter_by(
        user_id=current_user.id,
        study_id=study_id
    ).first()
    
    if progress:
        progress.completed = False
        db.session.commit()
    
    return jsonify({'success': True})
@edification_bp.route('/study/<int:id>/download/<format>')
@login_required
def download_study(id, format):
    
    study = Study.query.get_or_404(id)
    
    # Buscar o autor (se existir)
    author_name = 'Admin'
    if study.author_id:
        author = User.query.get(study.author_id)
        if author:
            author_name = author.name
    
    # Converter conteúdo para HTML
    if study.content:
        md = markdown.Markdown(extensions=['extra', 'fenced_code', 'tables'])
        html_content = md.convert(study.content)
    else:
        html_content = '<p>Nenhum conteúdo disponível.</p>'
    
    # Template HTML para os downloads
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{study.title} - Ecclesia Master</title>
        <style>
            body {{
                font-family: 'Georgia', 'Times New Roman', serif;
                line-height: 1.6;
                max-width: 800px;
                margin: 0 auto;
                padding: 40px;
                color: #333;
            }}
            h1 {{
                color: #4f46e5;
                border-bottom: 2px solid #e2e8f0;
                padding-bottom: 10px;
            }}
            h2, h3 {{
                color: #1e293b;
                margin-top: 1.5em;
            }}
            .meta {{
                color: #64748b;
                font-size: 0.9em;
                margin-bottom: 30px;
                padding-bottom: 20px;
                border-bottom: 1px solid #e2e8f0;
            }}
            .category {{
                display: inline-block;
                background: #e2e8f0;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 0.8em;
                margin-bottom: 15px;
            }}
            blockquote {{
                border-left: 4px solid #4f46e5;
                margin: 20px 0;
                padding-left: 20px;
                color: #475569;
                font-style: italic;
            }}
            code {{
                background: #f1f5f9;
                padding: 2px 6px;
                border-radius: 4px;
                font-family: monospace;
            }}
            pre {{
                background: #1e293b;
                color: #e2e8f0;
                padding: 15px;
                border-radius: 8px;
                overflow-x: auto;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                border: 1px solid #e2e8f0;
                padding: 8px 12px;
                text-align: left;
            }}
            th {{
                background: #f8fafc;
            }}
            .footer {{
                margin-top: 50px;
                padding-top: 20px;
                border-top: 1px solid #e2e8f0;
                text-align: center;
                font-size: 0.8em;
                color: #94a3b8;
            }}
        </style>
    </head>
    <body>
        <div class="category">{study.category or 'Estudo Bíblico'}</div>
        <h1>{study.title}</h1>
        <div class="meta">
            <strong>Autor:</strong> {author_name} &nbsp;|&nbsp;
            <strong>Data:</strong> {study.created_at.strftime('%d/%m/%Y')}
        </div>
        <div class="content">
            {html_content}
        </div>
        <div class="footer">
            Gerado pelo Ecclesia Master - Estudo para edificação do corpo de Cristo
        </div>
    </body>
    </html>
    """
    
    if format == 'html':
        return send_file(
            BytesIO(html_template.encode('utf-8')),
            mimetype='text/html',
            as_attachment=True,
            download_name=f"{study.title.replace(' ', '_')}.html"
        )
    
    elif format == 'md':
        # Download como Markdown
        md_content = f"""# {study.title}

**Autor:** {author_name}  
**Data:** {study.created_at.strftime('%d/%m/%Y')}  
**Categoria:** {study.category or 'Estudo Bíblico'}

---

{study.content}

---

*Gerado pelo Ecclesia Master - Estudo para edificação do corpo de Cristo*
"""
        return send_file(
            BytesIO(md_content.encode('utf-8')),
            mimetype='text/markdown',
            as_attachment=True,
            download_name=f"{study.title.replace(' ', '_')}.md"
        )
    
    elif format == 'pdf':
        # Download como PDF
        try:
            from weasyprint import HTML
            pdf_file = HTML(string=html_template).write_pdf()
            return send_file(
                BytesIO(pdf_file),
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f"{study.title.replace(' ', '_')}.pdf"
            )
        except Exception as e:
            flash(f'Erro ao gerar PDF: {str(e)}', 'danger')
            return redirect(url_for('edification.study_detail', id=study.id))
    
    else:
        flash('Formato não suportado', 'danger')
        return redirect(url_for('edification.study_detail', id=study.id))
    
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
    image_url = request.form.get('image_path')
    generate_puzzle_image = request.form.get('generate_puzzle_image') == 'on'
    
    final_image_path = None  # Caminho da imagem/PDF para salvar no banco
    file_path = None         # Caminho do arquivo temporário para extração
    
    # ========================================
    # PROCESSAR UPLOAD DE ARQUIVO
    # ========================================
    file = request.files.get('story_file')
    
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        file_ext = os.path.splitext(filename)[1].lower()
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Validar tamanho do PDF
        if file_ext == '.pdf':
            tamanho_mb = os.path.getsize(file_path) / (1024 * 1024)
            if tamanho_mb > 15:
                flash(f'O PDF tem {tamanho_mb:.1f} MB. O sistema vai comprimi-lo.', 'warning')
                file_path, comprimido = validar_e_comprimir_pdf(file_path)
                if comprimido:
                    flash('PDF comprimido com sucesso!', 'success')
            elif tamanho_mb > 10:
                flash(f'O PDF tem {tamanho_mb:.1f} MB. O processamento pode ser lento.', 'info')
        
        # Extrair texto do arquivo
        try:
            extracted_text = extract_text(file_path)
            if extracted_text and extracted_text.strip():
                content = extracted_text
                flash(f'Texto extraído do arquivo {filename} com sucesso!', 'success')
            else:
                flash(f'O arquivo {filename} não continha texto extraível.', 'warning')
        except Exception as e:
            flash(f'Erro ao extrair texto: {str(e)}', 'warning')
        
        # 🔥 SALVAR PDF PERMANENTEMENTE para leitura posterior
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        media_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'media')
        os.makedirs(media_folder, exist_ok=True)
        final_path = os.path.join(media_folder, unique_filename)
        
        import shutil
        shutil.copy2(file_path, final_path)
        final_image_path = f'uploads/media/{unique_filename}'
        
        flash(f'PDF salvo permanentemente para leitura!', 'success')
        
        # ========================================
        # 🔥 NOVO: EXTRAIR IMAGEM DO PDF PARA O QUEBRA-CABEÇA
        # ========================================
        if generate_puzzle_image and file_ext == '.pdf':
            flash('Procurando ilustrações no PDF...', 'info')
            
            imagem_bytes, imagem_ext = extrair_melhor_imagem_do_pdf(final_path)
            
            if imagem_bytes:
                # Salvar a imagem extraída do PDF
                puzzle_filename = f"puzzle_{timestamp}_{title[:20]}_extraida.{imagem_ext}"
                puzzle_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'media', 'puzzles')
                os.makedirs(puzzle_folder, exist_ok=True)
                puzzle_path = os.path.join(puzzle_folder, puzzle_filename)
                
                with open(puzzle_path, 'wb') as f:
                    f.write(imagem_bytes)
                
                # Guardamos o caminho temporariamente (story ainda não tem ID)
                imagem_extraida_path = f'uploads/media/puzzles/{puzzle_filename}'
                flash('✨ Ilustração encontrada no PDF! Será usada no quebra-cabeça.', 'success')
            else:
                imagem_extraida_path = None
                flash('Nenhuma ilustração encontrada no PDF. Será gerada por IA se necessário.', 'warning')
    
    # ========================================
    # PROCESSAR URL (imagem ou PDF externo)
    # ========================================
    elif image_url and image_url.strip():
        final_image_path = image_url
        
        # Se for PDF, baixar e extrair texto
        if image_url.lower().endswith('.pdf'):
            flash('Detectado PDF na URL. Baixando para extrair texto...', 'info')
            temp_pdf = download_pdf_from_url(image_url)
            
            if temp_pdf:
                try:
                    extracted_text = extract_text(temp_pdf)
                    if extracted_text and extracted_text.strip():
                        content = extracted_text
                        flash('Texto extraído do PDF da URL com sucesso!', 'success')
                    else:
                        flash('O PDF não continha texto extraível.', 'warning')
                    
                    # 🔥 Tentar extrair imagem do PDF baixado
                    if generate_puzzle_image:
                        imagem_bytes, imagem_ext = extrair_melhor_imagem_do_pdf(temp_pdf)
                        if imagem_bytes:
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            puzzle_filename = f"puzzle_{timestamp}_{title[:20]}_extraida.{imagem_ext}"
                            puzzle_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'media', 'puzzles')
                            os.makedirs(puzzle_folder, exist_ok=True)
                            puzzle_path = os.path.join(puzzle_folder, puzzle_filename)
                            
                            with open(puzzle_path, 'wb') as f:
                                f.write(imagem_bytes)
                            
                            imagem_extraida_path = f'uploads/media/puzzles/{puzzle_filename}'
                            flash('✨ Ilustração encontrada no PDF da URL!', 'success')
                        else:
                            imagem_extraida_path = None
                            
                except Exception as e:
                    flash(f'Erro ao extrair texto do PDF: {str(e)}', 'warning')
                finally:
                    try:
                        if temp_pdf and os.path.exists(temp_pdf):
                            os.unlink(temp_pdf)
                    except:
                        pass
            else:
                flash('Não foi possível baixar o PDF da URL.', 'danger')
                imagem_extraida_path = None
        else:
            imagem_extraida_path = None
    
    # ========================================
    # VALIDAR CONTEÚDO
    # ========================================
    if not content or not content.strip():
        flash('Nenhum conteúdo foi fornecido ou extraído. A história precisa de texto.', 'danger')
        if file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except:
                pass
        return redirect(url_for('edification.manage_kids'))
    
    # ========================================
    # CRIAR A HISTÓRIA
    # ========================================
    new_story = BibleStory(
        title=title,
        content=content.strip(),
        reference=request.form.get('reference'),
        image_path=final_image_path,
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
    
    # ========================================
    # SALVAR IMAGEM EXTRAÍDA (se houver)
    # ========================================
    if generate_puzzle_image and 'imagem_extraida_path' in locals() and imagem_extraida_path:
        new_story.puzzle_image = imagem_extraida_path
        db.session.commit()
        flash('🧩 Imagem do PDF salva para o quebra-cabeça!', 'success')
    
    # ========================================
    # GERAR IMAGEM PARA O QUEBRA-CABEÇA (FALLBACK - IA)
    # ========================================
    elif generate_puzzle_image and (not hasattr(new_story, 'puzzle_image') or not new_story.puzzle_image):
        flash('Gerando imagem para o quebra-cabeça com IA...', 'info')
        try:
            prompt = f"Biblical children's story illustration: {new_story.title}. {new_story.content[:300]}"
            prompt = prompt.replace('\n', ' ').strip()
            
            imagem_bytes = gerar_imagem_pollinations(prompt)
            
            if imagem_bytes:
                puzzle_filename = f"puzzle_{new_story.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                puzzle_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'media', 'puzzles')
                os.makedirs(puzzle_folder, exist_ok=True)
                puzzle_path = os.path.join(puzzle_folder, puzzle_filename)
                
                with open(puzzle_path, 'wb') as f:
                    f.write(imagem_bytes)
                
                new_story.puzzle_image = f'uploads/media/puzzles/{puzzle_filename}'
                db.session.commit()
                flash('✨ Imagem para o quebra-cabeça gerada com IA!', 'success')
            else:
                flash('Não foi possível gerar a imagem para o quebra-cabeça.', 'warning')
        except Exception as e:
            flash(f'Erro ao gerar imagem: {str(e)}', 'warning')
    
    # ========================================
    # GERAR QUESTÕES COM IA
    # ========================================
    if request.form.get('generate_ai_questions'):
        try:
            if len(content.strip()) >= 100:
                partes_texto = dividir_texto_para_ia(content, tamanho_maximo=6000)
                
                if len(partes_texto) > 1:
                    flash(f'Conteúdo extenso ({len(content)} caracteres). Processando em {len(partes_texto)} partes.', 'info')
                
                todas_questoes = []
                dados_jogo = None
                
                for idx, parte in enumerate(partes_texto):
                    if len(parte.strip()) < 100:
                        continue
                    
                    ai_data = generate_questions(parte, type='kids', count=7)
                    
                    if "error" in ai_data:
                        flash(f'Erro na IA (parte {idx+1}): {ai_data["error"]}', 'danger')
                        continue
                    elif "questions" in ai_data and ai_data["questions"]:
                        todas_questoes.extend(ai_data["questions"])
                        if not dados_jogo and "game_words" in ai_data:
                            dados_jogo = ai_data["game_words"]
                
                if todas_questoes:
                    for q_data in todas_questoes[:21]:
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
                    
                    if dados_jogo:
                        new_story.game_data = json.dumps(dados_jogo)
                    
                    db.session.commit()
                    flash(f'{len(todas_questoes)} questões geradas pela IA!', 'success')
                    return redirect(url_for('edification.review_kids_questions', story_id=new_story.id))
                else:
                    flash('IA não retornou questões válidas.', 'warning')
            else:
                flash('Conteúdo insuficiente (mínimo 100 caracteres) para gerar questões.', 'warning')
        except Exception as e:
            flash(f'Erro ao gerar questões: {str(e)}', 'warning')
    
    # ========================================
    # LIMPAR ARQUIVO TEMPORÁRIO
    # ========================================
    if file_path and os.path.exists(file_path):
        try:
            os.unlink(file_path)
        except:
            pass
    
    flash('História adicionada com sucesso!', 'success')
    return redirect(url_for('edification.manage_kids'))



@edification_bp.route('/kids/story/edit/<int:story_id>', methods=['GET', 'POST'])
@login_required
def edit_bible_story(story_id):
    if not can_manage_kids():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.kids'))
    
    story = BibleStory.query.get_or_404(story_id)
    
    if request.method == 'POST':
        # Atualizar dados básicos
        story.title = request.form.get('title')
        story.reference = request.form.get('reference')
        story.order = request.form.get('order', 0)
        
        # Conteúdo - pode vir do textarea ou de arquivo
        content = request.form.get('content')
        file = request.files.get('story_file')
        
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            try:
                extracted_text = extract_text(file_path)
                if extracted_text and extracted_text.strip():
                    story.content = extracted_text
                    flash('Texto extraído do arquivo com sucesso!', 'success')
                else:
                    flash('O arquivo não continha texto extraível.', 'warning')
            except Exception as e:
                flash(f'Erro ao extrair texto: {str(e)}', 'warning')
            finally:
                if os.path.exists(file_path):
                    os.unlink(file_path)
        elif content and content.strip():
            story.content = content.strip()
        
        # 🔥 CORREÇÃO: Atualizar imagem SOMENTE se foi fornecida
        image_url = request.form.get('image_path')
        if image_url and image_url.strip():
            story.image_path = image_url.strip()
        # Se não forneceu URL, mantém a existente (não faz nada)
        
        db.session.commit()
        
        log_action(
            action='UPDATE',
            module='KIDS_STORY',
            description=f"História infantil editada: {story.title}",
            old_values={'id': story.id},
            new_values={'title': story.title},
            church_id=current_user.church_id
        )
        
        flash('História atualizada com sucesso!', 'success')
        
        # Ações pós-salvar
        if request.form.get('regenerate_questions') == 'on':
            return redirect(url_for('edification.regenerate_kids_questions', story_id=story.id))
        
        return redirect(url_for('edification.manage_kids'))
    
    return render_template('edification/edit_bible_story.html', story=story)

@edification_bp.route('/kids/story/<int:story_id>/regenerate-questions', methods=['GET', 'POST'])
@login_required
def regenerate_kids_questions(story_id):
    if not can_manage_kids():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.kids'))
    
    story = BibleStory.query.get_or_404(story_id)
    
    if request.method == 'POST':
        # Deletar questões existentes
        BibleQuiz.query.filter_by(story_id=story_id).delete()
        
        # Gerar novas questões
        try:
            texto_para_ia = story.content
            if len(texto_para_ia) > 6000:
                texto_para_ia = texto_para_ia[:6000]
                flash(f'Conteúdo extenso. Processando os primeiros 6000 caracteres.', 'info')
            
            ai_data = generate_questions(texto_para_ia, type='kids', count=7)
            
            if "error" in ai_data:
                flash(f'Erro na IA: {ai_data["error"]}', 'danger')
            elif "questions" in ai_data and ai_data["questions"]:
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
                flash(f'{len(ai_data["questions"])} novas questões geradas!', 'success')
            else:
                flash('IA não retornou questões válidas.', 'warning')
                
        except Exception as e:
            flash(f'Erro ao regenerar questões: {str(e)}', 'warning')
        
        return redirect(url_for('edification.review_kids_questions', story_id=story_id))
    
    return render_template('edification/regenerate_kids_questions.html', story=story)

@edification_bp.route('/kids/story/<int:story_id>/generate-puzzle-image', methods=['POST'])
@login_required
def generate_puzzle_image(story_id):
    """Gera uma imagem para o quebra-cabeça usando IA"""
    story = BibleStory.query.get_or_404(story_id)
    
    try:
        # Criar prompt baseado na história
        prompt = f"Biblical children's story illustration: {story.title}. {story.content[:300]}"
        prompt = prompt.replace('\n', ' ').strip()
        
        # Gerar imagem via Pollinations
        imagem_bytes = gerar_imagem_pollinations(prompt)
        
        if imagem_bytes:
            # Salvar a imagem
            puzzle_filename = f"puzzle_{story.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            puzzle_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'media', 'puzzles')
            os.makedirs(puzzle_folder, exist_ok=True)
            puzzle_path = os.path.join(puzzle_folder, puzzle_filename)
            
            with open(puzzle_path, 'wb') as f:
                f.write(imagem_bytes)
            
            # Atualizar o campo no banco
            story.puzzle_image = f'uploads/media/puzzles/{puzzle_filename}'
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'image_url': url_for('edification.get_puzzle_image', story_id=story.id),
                'message': 'Imagem gerada com sucesso!'
            })
        else:
            return jsonify({'success': False, 'message': 'Erro ao gerar imagem'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    
@edification_bp.route('/kids/story/<int:story_id>/regenerate-puzzle-image')
@edification_bp.route('/kids/story/<int:story_id>/regenerate-puzzle-image/<source>')
@login_required
def regenerate_puzzle_image(story_id, source=None):
    """Regenera a imagem do quebra-cabeça
    source: 'pdf' (extrai do PDF) ou 'ai' (gera com IA)
    """
    if not can_manage_kids():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('edification.kids'))
    
    story = BibleStory.query.get_or_404(story_id)
    
    # Se não especificou source, tenta PDF primeiro, depois IA (fallback)
    if source is None:
        # Tenta extrair do PDF primeiro
        if story.image_path and story.image_path.lower().endswith('.pdf'):
            source = 'pdf'
        else:
            source = 'ai'
    
    try:
        imagem_bytes = None
        imagem_ext = 'jpg'
        
        # ========================================
        # OPÇÃO 1: EXTRAIR DO PDF
        # ========================================
        if source == 'pdf':
            if not story.image_path or not story.image_path.lower().endswith('.pdf'):
                flash('❌ Esta história não tem um PDF associado para extrair imagens.', 'warning')
                return redirect(url_for('edification.edit_bible_story', story_id=story.id))
            
            flash('📄 Procurando ilustrações no PDF...', 'info')
            
            if story.image_path.startswith('http'):
                temp_pdf = download_pdf_from_url(story.image_path)
                if temp_pdf:
                    imagem_bytes, imagem_ext = extrair_melhor_imagem_do_pdf(temp_pdf)
                    if temp_pdf and os.path.exists(temp_pdf):
                        os.unlink(temp_pdf)
            else:
                pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 
                                       story.image_path.replace('uploads/', ''))
                if os.path.exists(pdf_path):
                    imagem_bytes, imagem_ext = extrair_melhor_imagem_do_pdf(pdf_path)
            
            if imagem_bytes:
                flash('✨ Ilustração encontrada no PDF!', 'success')
            else:
                flash('⚠️ Nenhuma imagem encontrada no PDF. Tente a opção com IA.', 'warning')
        
        # ========================================
        # OPÇÃO 2: GERAR COM IA
        # ========================================
        elif source == 'ai':
            flash('🎨 Gerando ilustração com IA... Isso pode levar alguns segundos.', 'info')
            
            prompt = f"Biblical children's story illustration: {story.title}. {story.content[:300]}"
            prompt = prompt.replace('\n', ' ').strip()
            
            imagem_bytes = gerar_imagem_pollinations(prompt)
            if imagem_bytes:
                imagem_ext = 'jpg'
                flash('✨ Imagem gerada com IA!', 'success')
        
        # ========================================
        # SALVAR IMAGEM
        # ========================================
        if imagem_bytes:
            puzzle_filename = f"puzzle_{story.id}_{source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{imagem_ext}"
            puzzle_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'media', 'puzzles')
            os.makedirs(puzzle_folder, exist_ok=True)
            puzzle_path = os.path.join(puzzle_folder, puzzle_filename)
            
            with open(puzzle_path, 'wb') as f:
                f.write(imagem_bytes)
            
            # Remover imagem antiga (opcional)
            if story.puzzle_image:
                old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 
                                       story.puzzle_image.replace('uploads/', ''))
                if os.path.exists(old_path):
                    try:
                        os.unlink(old_path)
                    except:
                        pass
            
            story.puzzle_image = f'uploads/media/puzzles/{puzzle_filename}'
            db.session.commit()
            
            flash('✅ Imagem do quebra-cabeça atualizada com sucesso!', 'success')
        else:
            flash('❌ Não foi possível gerar ou extrair imagem para o quebra-cabeça.', 'warning')
            
    except Exception as e:
        flash(f'❌ Erro ao regenerar imagem: {str(e)}', 'danger')
    
    return redirect(url_for('edification.edit_bible_story', story_id=story.id))
    
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
    story = None
    
    if story_id:
        # Caso 1: História específica
        story = BibleStory.query.get_or_404(int(story_id))
    else:
        # Caso 2: "Geral" - pegar uma história que JÁ TEM imagem gerada
        # Primeiro, tenta pegar histórias com puzzle_image (já gerada)
        story = BibleStory.query.filter(
            BibleStory.puzzle_image.isnot(None),
            BibleStory.puzzle_image != ''
        ).order_by(func.random()).first()
        
        # Se não tiver nenhuma com imagem gerada, pega qualquer uma
        if not story:
            story = BibleStory.query.order_by(func.random()).first()
    
    return render_template('edification/kids_puzzle.html', story=story)

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

@edification_bp.route('/kids/story/<int:story_id>/puzzle-image')
def get_puzzle_image(story_id):
    """Retorna a imagem do quebra-cabeça para uma história"""
    story = BibleStory.query.get_or_404(story_id)
    
    # Se tem imagem de puzzle salva
    if hasattr(story, 'puzzle_image') and story.puzzle_image:
        image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 
                                 story.puzzle_image.replace('uploads/', ''))
        if os.path.exists(image_path):
            return send_file(image_path, mimetype='image/jpeg')
    
    # Se não tem, tenta usar a imagem da história
    if story.image_path and not story.image_path.startswith('http'):
        image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 
                                 story.image_path.replace('uploads/', ''))
        if os.path.exists(image_path):
            return send_file(image_path, mimetype='image/jpeg')
    
    # Fallback para imagem padrão
    return send_file('static/img/kids_default.jpg', mimetype='image/jpeg')

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