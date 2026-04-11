# Arquivo completo: app/modules/admin/routes.py
# Consolidado com Gestão Global de Membros (filtros/totalizador) e Gestão de Cargos por Filial
# Atualizado para usar campo is_lead_pastor em vez de nome fixo 'Pastor Líder'
# + Nova rota para configuração do layout do cartão de membro
# + LOGS ADICIONADOS (sem alterar estrutura original)

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app.core.models import Church, db, User, ChurchRole, Transaction, StudyQuestion, Ministry, Study, StudyProgress, SystemLog, Event
from app.utils.logger import log_action  # <-- ÚNICA LINHA ADICIONADA
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageOps
from io import BytesIO
from flask import send_file
import textwrap  # Para quebrar linhas longas se necessário
import uuid
import json
from sqlalchemy import or_

admin_bp = Blueprint('admin', __name__)

def is_global_admin():
    return current_user.church_role and current_user.church_role.name == 'Administrador Global'

def can_edit_church(church):
    """Verifica se o usuário pode editar dados/layout da congregação"""
    if is_global_admin():
        return True
    if current_user.church_id == church.id and current_user.church_role and current_user.church_role.is_lead_pastor:
        return True
    return False

# Adicione esta função de permissão no início do arquivo (após as funções existentes)

def can_manage_word_emoji():
    """Verifica se o usuário pode gerenciar palavras e emojis (admin global, pastor líder ou líder do ministério Kids)"""
    if not current_user.is_authenticated:
        return False
    
    # Admin global ou pastor líder
    if current_user.church_role and (current_user.church_role.name == 'Administrador Global' or current_user.church_role.is_lead_pastor):
        return True
    
    # Líder do ministério Kids (principal, vice ou auxiliar)
    for ministry in current_user.ministries:
        if ministry.is_kids_ministry:
            if ministry.leader_id == current_user.id or ministry.vice_leader_id == current_user.id:
                return True
            if ministry.extra_leaders and current_user.id in ministry.extra_leaders:
                return True
    
    return False


# ==================== DASHBOARD ADMIN KPI ====================

@admin_bp.route('/dashboard')
@login_required
def admin_dashboard():
    """Dashboard administrativo com KPIs"""
    if not is_global_admin():
        flash('Acesso negado. Apenas administradores globais.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    # Importar modelos
    from app.core.models import User, Church, Study, StudyQuestion, Event, SystemLog, Transaction, Ministry, StudyProgress
    from sqlalchemy import func, extract
    from datetime import datetime, timedelta
    
    today = datetime.now().date()
    first_day_month = today.replace(day=1)
    last_month = today - timedelta(days=30)
    
    # ========== MEMBROS ==========
    total_members = User.query.count()
    active_members = User.query.filter_by(status='active').count()
    pending_members = User.query.filter_by(status='pending').count()
    new_members_month = User.query.filter(
        User.created_at >= first_day_month
    ).count()
    
    # Membros por igreja
    members_by_church = db.session.query(
        Church.name, func.count(User.id)
    ).outerjoin(User, Church.id == User.church_id).group_by(Church.id).all()
    
    # ========== FINANCEIRO ==========
    monthly_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.type == 'income',
        Transaction.date >= first_day_month
    ).scalar() or 0
    
    monthly_expense = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.type == 'expense',
        Transaction.date >= first_day_month
    ).scalar() or 0
    
    # Receitas por categoria
    income_by_category = db.session.query(
        Transaction.category_name, func.sum(Transaction.amount)
    ).filter(
        Transaction.type == 'income',
        Transaction.date >= last_month
    ).group_by(Transaction.category_name).order_by(func.sum(Transaction.amount).desc()).limit(5).all()
    
    expense_by_category = db.session.query(
        Transaction.category_name, func.sum(Transaction.amount)
    ).filter(
        Transaction.type == 'expense',
        Transaction.date >= last_month
    ).group_by(Transaction.category_name).order_by(func.sum(Transaction.amount).desc()).limit(5).all()
    
    # Evolução mensal
    monthly_evolution = []
    for i in range(5, -1, -1):
        month_date = today.replace(day=1) - timedelta(days=30*i)
        month_start = month_date.replace(day=1)
        if month_date.month == 12:
            month_end = month_date.replace(year=month_date.year+1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_date.replace(month=month_date.month+1, day=1) - timedelta(days=1)
        
        income = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.type == 'income',
            Transaction.date >= month_start,
            Transaction.date <= month_end
        ).scalar() or 0
        
        expense = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.type == 'expense',
            Transaction.date >= month_start,
            Transaction.date <= month_end
        ).scalar() or 0
        
        monthly_evolution.append({
            'month': month_start.strftime('%b/%Y'),
            'income': float(income),
            'expense': float(expense)
        })
    
    # ========== ESTUDOS ==========
    total_studies = Study.query.count()
    total_questions = StudyQuestion.query.filter_by(is_published=True).count()
    recent_studies = Study.query.order_by(Study.created_at.desc()).limit(5).all()
    
    most_accessed_studies = db.session.query(
        Study.title, func.count(StudyProgress.id).label('views')
    ).join(StudyProgress, Study.id == StudyProgress.study_id).group_by(Study.id).order_by(func.count(StudyProgress.id).desc()).limit(5).all()
    
    # ========== EVENTOS ==========
    upcoming_events = Event.query.filter(
        Event.start_time >= datetime.now()
    ).order_by(Event.start_time.asc()).limit(5).all()
    
    # ========== ATIVIDADES RECENTES ==========
    recent_activities = SystemLog.query.order_by(
        SystemLog.created_at.desc()
    ).limit(10).all()
    
    # ========== ESTATÍSTICAS DOS MINISTÉRIOS ==========
    ministries_stats = []
    for ministry in Ministry.query.all():
        ministries_stats.append({
            'name': ministry.name,
            'members_count': ministry.members.count(),
            'events_count': Event.query.filter_by(ministry_id=ministry.id).count()
        })
    
    # ========== CRESCIMENTO DE MEMBROS ==========
    member_growth = []
    for i in range(5, -1, -1):
        month_date = today.replace(day=1) - timedelta(days=30*i)
        month_start = month_date.replace(day=1)
        if month_date.month == 12:
            month_end = month_date.replace(year=month_date.year+1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_date.replace(month=month_date.month+1, day=1) - timedelta(days=1)
        
        count = User.query.filter(
            User.created_at >= month_start,
            User.created_at <= month_end
        ).count()
        
        member_growth.append({
            'month': month_start.strftime('%b/%Y'),
            'count': count
        })
    
    stats = {
        'total_members': total_members,
        'active_members': active_members,
        'pending_members': pending_members,
        'new_members_month': new_members_month,
        'monthly_income': float(monthly_income),
        'monthly_expense': float(monthly_expense),
        'balance': float(monthly_income - monthly_expense),
        'total_studies': total_studies,
        'total_questions': total_questions
    }
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         members_by_church=members_by_church,
                         income_by_category=income_by_category,
                         expense_by_category=expense_by_category,
                         monthly_evolution=monthly_evolution,
                         recent_studies=recent_studies,
                         most_accessed_studies=most_accessed_studies,
                         upcoming_events=upcoming_events,
                         recent_activities=recent_activities,
                         ministries_stats=ministries_stats,
                         member_growth=member_growth,
                         datetime=datetime)


@admin_bp.route('/church-dashboard')
@login_required
def church_dashboard():
    """Dashboard para pastor líder da filial"""
    if not current_user.church_role or not current_user.church_role.is_lead_pastor:
        flash('Acesso negado. Apenas pastores líderes.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    church = current_user.church
    if not church:
        flash('Você não está vinculado a nenhuma congregação.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    from datetime import datetime, timedelta
    from sqlalchemy import func
    
    today = datetime.now().date()
    first_day_month = today.replace(day=1)
    
    # ========== MEMBROS DA FILIAL ==========
    total_members = User.query.filter_by(church_id=church.id).count()
    active_members = User.query.filter_by(church_id=church.id, status='active').count()
    pending_members = User.query.filter_by(church_id=church.id, status='pending').count()
    new_members_month = User.query.filter(
        User.church_id == church.id,
        User.created_at >= first_day_month
    ).count()
    
    # ========== FINANCEIRO DA FILIAL ==========
    monthly_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.church_id == church.id,
        Transaction.type == 'income',
        Transaction.date >= first_day_month
    ).scalar() or 0
    
    monthly_expense = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.church_id == church.id,
        Transaction.type == 'expense',
        Transaction.date >= first_day_month
    ).scalar() or 0
    
    # Receitas por categoria
    income_by_category = db.session.query(
        Transaction.category_name, func.sum(Transaction.amount)
    ).filter(
        Transaction.church_id == church.id,
        Transaction.type == 'income',
        Transaction.date >= first_day_month
    ).group_by(Transaction.category_name).order_by(func.sum(Transaction.amount).desc()).limit(5).all()
    
    # ========== MINISTÉRIOS DA FILIAL ==========
    ministries = Ministry.query.filter_by(church_id=church.id).all()
    ministries_stats = []
    for ministry in ministries:
        ministries_stats.append({
            'id': ministry.id,
            'name': ministry.name,
            'members_count': ministry.members.count(),
            'events_count': Event.query.filter_by(ministry_id=ministry.id).count(),
            'balance': sum(t.amount for t in ministry.transactions if t.type == 'income') - 
                       sum(t.amount for t in ministry.transactions if t.type == 'expense')
        })
    
    # ========== PRÓXIMOS EVENTOS ==========
    upcoming_events = Event.query.filter(
        Event.church_id == church.id,
        Event.start_time >= datetime.now()
    ).order_by(Event.start_time.asc()).limit(5).all()
    
    stats = {
        'total_members': total_members,
        'active_members': active_members,
        'pending_members': pending_members,
        'new_members_month': new_members_month,
        'monthly_income': float(monthly_income),
        'monthly_expense': float(monthly_expense),
        'balance': float(monthly_income - monthly_expense),
        'ministries_count': len(ministries)
    }
    
    return render_template('admin/church_dashboard.html',
                         stats=stats,
                         church=church,
                         income_by_category=income_by_category,
                         ministries_stats=ministries_stats,
                         upcoming_events=upcoming_events,
                         datetime=datetime)

@admin_bp.route('/ministry-dashboard/<int:ministry_id>')
@login_required
def ministry_dashboard(ministry_id):
    """Dashboard para líderes de ministério"""
    ministry = Ministry.query.get_or_404(ministry_id)
    
    # Verificar permissão
    from app.modules.members.routes import is_ministry_leader
    is_leader = is_ministry_leader(ministry)
    is_global_admin = current_user.church_role and current_user.church_role.name == 'Administrador Global'
    is_pastor = current_user.church_role and current_user.church_role.is_lead_pastor
    
    if not (is_leader or is_global_admin or is_pastor):
        flash('Acesso negado. Você não é líder deste ministério.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    from datetime import datetime, timedelta
    from sqlalchemy import func
    
    today = datetime.now().date()
    first_day_month = today.replace(day=1)
    
    # ========== MEMBROS DO MINISTÉRIO ==========
    members = ministry.members.all()
    total_members = len(members)
    
    # Contagem por gênero
    male_count = sum(1 for m in members if m.gender == 'Masculino')
    female_count = sum(1 for m in members if m.gender == 'Feminino')
    
    # ========== FINANCEIRO DO MINISTÉRIO ==========
    from app.core.models import MinistryTransaction
    
    monthly_income = db.session.query(func.sum(MinistryTransaction.amount)).filter(
        MinistryTransaction.ministry_id == ministry.id,
        MinistryTransaction.type == 'income',
        MinistryTransaction.date >= first_day_month,
        MinistryTransaction.is_paid == True
    ).scalar() or 0
    
    monthly_expense = db.session.query(func.sum(MinistryTransaction.amount)).filter(
        MinistryTransaction.ministry_id == ministry.id,
        MinistryTransaction.type == 'expense',
        MinistryTransaction.date >= first_day_month
    ).scalar() or 0
    
    # Dívidas pendentes
    pending_debts = db.session.query(func.sum(MinistryTransaction.amount)).filter(
        MinistryTransaction.ministry_id == ministry.id,
        MinistryTransaction.is_debt == True,
        MinistryTransaction.is_paid == False
    ).scalar() or 0
    
    # Receitas por categoria
    income_by_category = db.session.query(
        MinistryTransaction.category_name, func.sum(MinistryTransaction.amount)
    ).filter(
        MinistryTransaction.ministry_id == ministry.id,
        MinistryTransaction.type == 'income',
        MinistryTransaction.date >= first_day_month
    ).group_by(MinistryTransaction.category_name).order_by(func.sum(MinistryTransaction.amount).desc()).limit(5).all()
    
    # ========== EVENTOS DO MINISTÉRIO ==========
    upcoming_events = Event.query.filter(
        Event.ministry_id == ministry.id,
        Event.start_time >= datetime.now()
    ).order_by(Event.start_time.asc()).limit(5).all()
    
    # ========== PRÓXIMOS ANIVERSARIANTES ==========
    birthday_alerts = []
    today_date = datetime.now().date()
    future_limit = today_date + timedelta(days=10)
    
    for member in members:
        if member.birth_date:
            try:
                bday_this_year = member.birth_date.replace(year=today_date.year)
            except ValueError:
                bday_this_year = member.birth_date.replace(year=today_date.year, day=28)
            
            if bday_this_year < today_date:
                try:
                    bday_this_year = bday_this_year.replace(year=today_date.year + 1)
                except ValueError:
                    bday_this_year = bday_this_year.replace(year=today_date.year + 1, day=28)
            
            if today_date <= bday_this_year <= future_limit:
                days_until = (bday_this_year - today_date).days
                birthday_alerts.append({
                    'name': member.name,
                    'day': member.birth_date.day,
                    'month': member.birth_date.strftime('%m'),
                    'is_today': days_until == 0,
                    'days_until': days_until
                })
    birthday_alerts.sort(key=lambda x: x['days_until'])
    
    stats = {
        'total_members': total_members,
        'male_count': male_count,
        'female_count': female_count,
        'monthly_income': float(monthly_income),
        'monthly_expense': float(monthly_expense),
        'balance': float(monthly_income - monthly_expense),
        'pending_debts': float(pending_debts),
        'events_count': Event.query.filter_by(ministry_id=ministry.id).count()
    }
    
    return render_template('admin/ministry_dashboard.html',
                         stats=stats,
                         ministry=ministry,
                         income_by_category=income_by_category,
                         upcoming_events=upcoming_events,
                         birthday_alerts=birthday_alerts,
                         members=members[:10],
                         datetime=datetime)

# ==================== GESTÃO DE PALAVRAS E EMOJIS ====================

@admin_bp.route('/word-emoji')
@login_required
def word_emoji_list():
    """Lista palavras e emojis associados"""
    if not can_manage_word_emoji():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    from app.core.models import EmojiWord
    
    emoji_words = EmojiWord.query.order_by(EmojiWord.id).all()
    total_words = sum(len(item.words or []) for item in emoji_words)
    total_emojis = len(emoji_words)
    
    return render_template('admin/word_emoji.html', 
                           emoji_words=emoji_words,
                           total_words=total_words,
                           total_emojis=total_emojis)


@admin_bp.route('/emoji-word/add', methods=['POST'])
@login_required
def emoji_word_add():
    """Adiciona novo emoji"""
    if not can_manage_word_emoji():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    from app.core.models import EmojiWord
    
    emoji = request.form.get('emoji')
    emoji_type = request.form.get('emoji_type', 'unicode')
    custom_icon = None
    
    print(f"📝 Recebido: emoji={emoji}, type={emoji_type}")
    
    if emoji_type == 'custom':
        file = request.files.get('custom_icon')
        if file and file.filename:
            filename = secure_filename(file.filename)
            emoji_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'emojis')
            os.makedirs(emoji_dir, exist_ok=True)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            full_path = os.path.join(emoji_dir, unique_filename)
            file.save(full_path)
            custom_icon = f'uploads/emojis/{unique_filename}'
            emoji = custom_icon
    
    new_emoji = EmojiWord(
        emoji=emoji,
        emoji_type=emoji_type,
        custom_icon=custom_icon,
        words=[]
    )
    
    db.session.add(new_emoji)
    db.session.commit()
    
    print(f"✅ Emoji criado: ID={new_emoji.id}, {emoji}")
    
    return jsonify({'success': True, 'id': new_emoji.id})

@admin_bp.route('/emoji-word/<int:id>/add-word', methods=['POST'])
@login_required
def emoji_word_add_word(id):
    """Adiciona palavra a um emoji"""
    if not can_manage_word_emoji():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    from app.core.models import EmojiWord
    import json
    from sqlalchemy import text
    
    # Buscar o emoji
    emoji_item = EmojiWord.query.get(id)
    if not emoji_item:
        return jsonify({'success': False, 'message': f'Emoji com ID {id} não encontrado.'}), 404
    
    data = request.get_json()
    word = data.get('word', '').upper().strip()
    
    if not word:
        return jsonify({'success': False, 'message': 'Palavra inválida.'}), 400
    
    # 🔥 USAR SQL DIRETO PARA GARANTIR
    current_words = emoji_item.words
    
    # Garantir que é uma lista
    if not current_words or current_words == '[]':
        current_words = []
    elif isinstance(current_words, str):
        try:
            current_words = json.loads(current_words)
        except:
            current_words = []
    elif not isinstance(current_words, list):
        current_words = []
    
    # Adicionar palavra
    if word not in current_words:
        current_words.append(word)
        
        # 🔥 ATUALIZAR DIRETO COM SQL
        db.session.execute(
            text("UPDATE emoji_words SET words = :words, updated_at = NOW() WHERE id = :id"),
            {'words': json.dumps(current_words), 'id': id}
        )
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Palavra "{word}" adicionada!',
            'words': current_words,
            'id': id
        })
    
    return jsonify({'success': False, 'message': f'Palavra "{word}" já existe.'}), 400

@admin_bp.route('/emoji-word/<int:id>/remove-word', methods=['POST'])
@login_required
def emoji_word_remove_word(id):
    """Remove palavra de um emoji"""
    if not can_manage_word_emoji():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    from app.core.models import EmojiWord
    import json
    from sqlalchemy import text
    
    emoji_item = EmojiWord.query.get(id)
    if not emoji_item:
        return jsonify({'success': False, 'message': f'Emoji com ID {id} não encontrado.'}), 404
    
    data = request.get_json()
    word = data.get('word', '').upper().strip()
    
    if not word:
        return jsonify({'success': False, 'message': 'Palavra inválida.'}), 400
    
    # 🔥 USAR SQL DIRETO PARA GARANTIR
    current_words = emoji_item.words
    
    # Garantir que é uma lista
    if not current_words or current_words == '[]':
        current_words = []
    elif isinstance(current_words, str):
        try:
            current_words = json.loads(current_words)
        except:
            current_words = []
    elif not isinstance(current_words, list):
        current_words = []
    
    # Remover palavra se existir
    if word in current_words:
        current_words.remove(word)
        
        # 🔥 ATUALIZAR DIRETO COM SQL
        db.session.execute(
            text("UPDATE emoji_words SET words = :words, updated_at = NOW() WHERE id = :id"),
            {'words': json.dumps(current_words), 'id': id}
        )
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Palavra "{word}" removida!',
            'words': current_words,
            'id': id
        })
    
    return jsonify({'success': False, 'message': f'Palavra "{word}" não encontrada.'}), 404

@admin_bp.route('/emoji-word/delete/<int:id>', methods=['POST'])
@login_required
def emoji_word_delete(id):
    """Exclui emoji"""
    if not can_manage_word_emoji():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    from app.core.models import EmojiWord
    
    emoji_item = EmojiWord.query.get_or_404(id)
    
    # Remover imagem customizada
    if emoji_item.custom_icon and os.path.exists(os.path.join(current_app.config['UPLOAD_FOLDER'], emoji_item.custom_icon.replace('uploads/', ''))):
        try:
            os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], emoji_item.custom_icon.replace('uploads/', '')))
        except:
            pass
    
    db.session.delete(emoji_item)
    db.session.commit()
    
    return jsonify({'success': True})

# ==================== GESTÃO DE CONGREGAÇÕES ====================

@admin_bp.route('/churches')
@login_required
def list_churches():
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    churches = Church.query.all()
    return render_template('admin/churches.html', churches=churches)

@admin_bp.route('/church/add', methods=['GET', 'POST'])
@login_required
def add_church():
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    if request.method == 'POST':
        country = request.form.get('country', '')
        euro_countries = ['Portugal', 'Espanha', 'França', 'Alemanha', 'Itália', 'Bélgica', 'Holanda', 'Luxemburgo', 'Irlanda', 'Grécia', 'Áustria', 'Finlândia']
        currency = '€' if country in euro_countries else 'R$'
        
        new_church = Church(
            name=request.form.get('name'),
            address=request.form.get('address'),
            city=request.form.get('city'),
            country=country,
            nif=request.form.get('nif'),
            email=request.form.get('email'),
            currency_symbol=currency,
            is_main=bool(request.form.get('is_main')),
            postal_code=request.form.get('postal_code'),
            concelho=request.form.get('concelho'),
            localidade=request.form.get('localidade')
        )

        file = request.files.get('logo')
        if file and file.filename:
            filename = secure_filename(file.filename)
            logos_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'churches', 'logos')
            os.makedirs(logos_dir, exist_ok=True)
            full_path = os.path.join(logos_dir, filename)
            file.save(full_path)
            new_church.logo_path = f'uploads/churches/logos/{filename}'

        db.session.add(new_church)
        db.session.commit()
        
        # === LOG ADICIONADO ===
        log_action(
            action='CREATE',
            module='CHURCH',
            description=f"Nova congregação criada: {new_church.name}",
            new_values={'id': new_church.id, 'name': new_church.name},
            church_id=new_church.id
        )
        # ======================
        
        flash('Congregação cadastrada com sucesso!', 'success')
        return redirect(url_for('admin.list_churches'))
        
    return render_template('admin/add_church.html')

@admin_bp.route('/church/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_church(id):
    church = Church.query.get_or_404(id)
    if not can_edit_church(church):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('admin.list_churches'))
    
    old_values = {'name': church.name, 'address': church.address, 'city': church.city}
    
    if request.method == 'POST':
        country = request.form.get('country', '')
        euro_countries = ['Portugal', 'Espanha', 'França', 'Alemanha', 'Itália', 'Bélgica', 'Holanda', 'Luxemburgo', 'Irlanda', 'Grécia', 'Áustria', 'Finlândia']
        church.currency_symbol = '€' if country in euro_countries else 'R$'
        
        church.name = request.form.get('name')
        church.address = request.form.get('address')
        church.city = request.form.get('city')
        church.country = country
        church.nif = request.form.get('nif')
        church.email = request.form.get('email')
        church.is_main = bool(request.form.get('is_main'))
        church.postal_code = request.form.get('postal_code')
        church.concelho = request.form.get('concelho')
        church.localidade = request.form.get('localidade')
        
        # 🔥 CONFIGURAÇÕES SMTP
        church.smtp_server = request.form.get('smtp_server') or None
        church.smtp_port = int(request.form.get('smtp_port')) if request.form.get('smtp_port') else 587
        church.smtp_user = request.form.get('smtp_user') or None
        # Só atualiza a senha se foi fornecida (não sobrescrever com vazio)
        if request.form.get('smtp_password'):
            church.smtp_password = request.form.get('smtp_password')
        church.smtp_use_tls = request.form.get('smtp_use_tls') == 'true'
        church.email_from = request.form.get('email_from') or None
        church.email_from_name = request.form.get('email_from_name') or 'Ecclesia Master'
        
        # 🔥 CHAVE API GEMINI
        if request.form.get('gemini_api_key'):
            church.gemini_api_key = request.form.get('gemini_api_key')
        
        # 🔥 MODO MANUTENÇÃO
        church.maintenance_mode = 'maintenance_mode' in request.form

        # Upload de logo
        file = request.files.get('logo')
        if file and file.filename:
            filename = secure_filename(file.filename)
            logos_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'churches', 'logos')
            os.makedirs(logos_dir, exist_ok=True)
            full_path = os.path.join(logos_dir, filename)
            file.save(full_path)
            # Remover logo antigo se existir
            if church.logo_path:
                old_logo = os.path.join(current_app.config['UPLOAD_FOLDER'], church.logo_path.replace('uploads/', ''))
                if os.path.exists(old_logo):
                    try:
                        os.remove(old_logo)
                    except:
                        pass
            church.logo_path = f'uploads/churches/logos/{filename}'
        
        # Upload de cartão frente/verso
        card_front = request.files.get('member_card_front')
        if card_front and card_front.filename:
            filename = secure_filename(card_front.filename)
            cards_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'churches', 'member_cards')
            os.makedirs(cards_dir, exist_ok=True)
            full_path = os.path.join(cards_dir, f'front_{church.id}_{filename}')
            card_front.save(full_path)
            church.member_card_front = f'uploads/churches/member_cards/front_{church.id}_{filename}'
        
        card_back = request.files.get('member_card_back')
        if card_back and card_back.filename:
            filename = secure_filename(card_back.filename)
            cards_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'churches', 'member_cards')
            os.makedirs(cards_dir, exist_ok=True)
            full_path = os.path.join(cards_dir, f'back_{church.id}_{filename}')
            card_back.save(full_path)
            church.member_card_back = f'uploads/churches/member_cards/back_{church.id}_{filename}'

        db.session.commit()
        
        log_action(
            action='UPDATE',
            module='CHURCH',
            description=f"Congregação editada: {church.name}",
            old_values=old_values,
            new_values={'name': church.name, 'address': church.address},
            church_id=church.id
        )
        
        flash('Congregação atualizada!', 'success')
        return redirect(url_for('admin.list_churches'))
    
    return render_template('admin/edit_church.html', church=church)

@admin_bp.route('/church/<int:id>/test-email', methods=['POST'])
@login_required
def test_church_email(id):
    """Testar configuração de email da congregação"""
    from flask import current_app
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    church = Church.query.get_or_404(id)
    
    if not can_edit_church(church):
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    data = request.get_json()
    test_email = data.get('test_email') if data else None
    
    if not test_email:
        return jsonify({'success': False, 'message': 'Email de teste não informado'}), 400
    
    # Verificar se as configurações existem
    if not church.smtp_server:
        return jsonify({'success': False, 'message': 'Servidor SMTP não configurado. Salve as configurações primeiro.'}), 400
    
    try:
        # Criar mensagem
        msg = MIMEMultipart()
        msg['From'] = church.email_from
        msg['To'] = test_email
        msg['Subject'] = f'Teste de Email - {church.name}'
        
        body = f"""
        Este é um email de teste do Ecclesia Master para a congregação {church.name}.
        
        Configurações utilizadas:
        - Servidor SMTP: {church.smtp_server}
        - Porta: {church.smtp_port}
        - TLS: {'Sim' if church.smtp_use_tls else 'Não'}
        - Usuário: {church.smtp_user}
        - Email remetente: {church.email_from}
        
        Se você recebeu este email, as configurações estão corretas!
        
        Data e hora do teste: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Conectar e enviar
        if church.smtp_use_tls:
            server = smtplib.SMTP(church.smtp_server, church.smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(church.smtp_server, church.smtp_port)
        
        server.login(church.smtp_user, church.smtp_password)
        server.send_message(msg)
        server.quit()
        
        return jsonify({'success': True, 'message': 'Email enviado com sucesso!'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/church/delete/<int:id>', methods=['POST'])
@login_required
def delete_church(id):
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    church = Church.query.get_or_404(id)
    
    if church.is_main and Church.query.filter_by(is_main=True).count() <= 1:
        if Church.query.count() <= 1:
            flash('Não é possível excluir a única congregação do sistema.', 'warning')
            return redirect(url_for('admin.list_churches'))

    church_data = {'id': church.id, 'name': church.name}
    
    
    try:
        User.query.filter_by(church_id=id).update({User.church_id: None})
        
        # === LOG ADICIONADO ===
        log_action(
            action='DELETE',
            module='CHURCH',
            description=f"Congregação excluída: {church.name}",
            old_values=church_data,
            church_id=church.id
        )
        # ======================
        db.session.delete(church)
        db.session.commit()
        
        
        
        flash(f'Congregação {church.name} excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir congregação: {str(e)}', 'danger')
        
    return redirect(url_for('admin.list_churches'))

@admin_bp.route('/my-church', methods=['GET', 'POST'])
@login_required
def edit_my_church():
    church = current_user.church
    if not church or not can_edit_church(church):
        flash('Acesso negado ou você não está vinculado a nenhuma congregação.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    old_values = {'name': church.name, 'address': church.address}
    
    if request.method == 'POST':
        country = request.form.get('country', '')
        euro_countries = ['Portugal', 'Espanha', 'França', 'Alemanha', 'Itália', 'Bélgica', 'Holanda', 'Luxemburgo', 'Irlanda', 'Grécia', 'Áustria', 'Finlândia']
        church.currency_symbol = '€' if country in euro_countries else 'R$'
        
        church.name = request.form.get('name')
        church.address = request.form.get('address')
        church.city = request.form.get('city')
        church.country = country
        church.nif = request.form.get('nif')
        church.email = request.form.get('email')
        church.postal_code = request.form.get('postal_code')
        church.concelho = request.form.get('concelho')
        church.localidade = request.form.get('localidade')

        file = request.files.get('logo')
        if file and file.filename:
            filename = secure_filename(file.filename)
            logos_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'churches', 'logos')
            os.makedirs(logos_dir, exist_ok=True)
            full_path = os.path.join(logos_dir, filename)
            file.save(full_path)
            church.logo_path = f'uploads/churches/logos/{filename}'
        
        card_front = request.files.get('member_card_front')
        if card_front and card_front.filename:
            filename = secure_filename(card_front.filename)
            cards_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'churches', 'member_cards')
            os.makedirs(cards_dir, exist_ok=True)
            full_path = os.path.join(cards_dir, f'front_{church.id}_{filename}')
            card_front.save(full_path)
            church.member_card_front = f'uploads/churches/member_cards/front_{church.id}_{filename}'
        
        card_back = request.files.get('member_card_back')
        if card_back and card_back.filename:
            filename = secure_filename(card_back.filename)
            cards_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'churches', 'member_cards')
            os.makedirs(cards_dir, exist_ok=True)
            full_path = os.path.join(cards_dir, f'back_{church.id}_{filename}')
            card_back.save(full_path)
            church.member_card_back = f'uploads/churches/member_cards/back_{church.id}_{filename}'

        db.session.commit()
        
        # === LOG ADICIONADO ===
        log_action(
            action='UPDATE',
            module='CHURCH',
            description=f"Dados da congregação atualizados por pastor líder: {church.name}",
            old_values=old_values,
            new_values={'name': church.name},
            church_id=church.id
        )
        # ======================
        
        flash('Dados da congregação atualizados com sucesso!', 'success')
        return redirect(url_for('admin.edit_my_church'))
    
    return render_template('admin/edit_my_church.html', church=church)

# ==================== CONFIGURAÇÃO DO LAYOUT DO CARTÃO DE MEMBRO ====================

@admin_bp.route('/church/<int:church_id>/card-layout', methods=['GET', 'POST'])
@login_required
def edit_card_layout(church_id):
    church = Church.query.get_or_404(church_id)
    
    if not can_edit_church(church):
        flash('Acesso negado. Apenas administradores globais ou pastores líderes desta congregação podem configurar o layout do cartão.', 'danger')
        return redirect(url_for('admin.list_churches'))
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            old_front = church.card_front_layout
            old_back = church.card_back_layout
            
            church.card_front_layout = data.get('front', {})
            church.card_back_layout = data.get('back', {})
            db.session.commit()
            
            # === LOG ADICIONADO ===
            log_action(
                action='UPDATE',
                module='CARD_LAYOUT',
                description=f"Layout do cartão de membro atualizado para {church.name}",
                old_values={'front': old_front, 'back': old_back},
                new_values={'front': church.card_front_layout, 'back': church.card_back_layout},
                church_id=church.id
            )
            # ======================
            
            return jsonify({'success': True, 'message': 'Layout do cartão salvo com sucesso!'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return render_template('admin/edit_card_layout.html', church=church)

# ==================== CONFIGURAÇÕES DO SISTEMA ====================

@admin_bp.route('/system-settings', methods=['GET'])
@login_required
def system_settings():
    """Página de configurações do sistema (chaves de API, email, etc.)"""
    if not is_global_admin():
        flash('Acesso negado. Apenas administradores globais.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    from app.core.models import SystemSetting
    
    settings = SystemSetting.query.all()
    settings_dict = {s.key: s.value for s in settings}
    
    return render_template('admin/system_settings.html', settings=settings_dict)


@admin_bp.route('/system-settings/save', methods=['POST'])
@login_required
def save_system_settings():
    """Salvar configurações do sistema"""
    if not is_global_admin():
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    from app.core.models import SystemSetting
    
    # Salvar configurações de email
    email_keys = ['smtp_server', 'smtp_port', 'smtp_user', 'smtp_password', 
                  'smtp_use_tls', 'email_from', 'email_from_name']
    
    for key in email_keys:
        value = request.form.get(key, '')
        SystemSetting.set(key, value)
    
    # Salvar chave da API Gemini
    gemini_key = request.form.get('gemini_api_key', '')
    if gemini_key:
        SystemSetting.set('gemini_api_key', gemini_key, is_encrypted=True)
    
    # Salvar configurações gerais
    SystemSetting.set('site_name', request.form.get('site_name', 'Ecclesia Master'))
    SystemSetting.set('site_logo', request.form.get('site_logo', ''))
    SystemSetting.set('timezone', request.form.get('timezone', 'America/Sao_Paulo'))
    SystemSetting.set('maintenance_mode', request.form.get('maintenance_mode', 'false'))
    
    log_action(
        action='UPDATE',
        module='ADMIN',
        description="Configurações do sistema atualizadas",
        church_id=current_user.church_id
    )
    
    return jsonify({'success': True})


@admin_bp.route('/system-settings/test-email', methods=['POST'])
@login_required
def test_email():
    """Testar configuração de email"""
    if not is_global_admin():
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    from flask_mail import Mail, Message
    from app import mail
    from app.core.models import SystemSetting
    
    test_email = request.form.get('test_email')
    if not test_email:
        return jsonify({'success': False, 'message': 'Email de teste não informado'}), 400
    
    # Recarregar configurações do banco
    app.config['MAIL_SERVER'] = SystemSetting.get('smtp_server', '')
    app.config['MAIL_PORT'] = int(SystemSetting.get('smtp_port', 587))
    app.config['MAIL_USE_TLS'] = SystemSetting.get('smtp_use_tls', 'true') == 'true'
    app.config['MAIL_USERNAME'] = SystemSetting.get('smtp_user', '')
    app.config['MAIL_PASSWORD'] = SystemSetting.get('smtp_password', '')
    app.config['MAIL_DEFAULT_SENDER'] = SystemSetting.get('email_from', '')
    
    mail = Mail(app)
    
    try:
        msg = Message(
            subject='Teste de Configuração de Email - Ecclesia Master',
            recipients=[test_email],
            body=f"""
            Este é um email de teste do Ecclesia Master.
            
            Se você recebeu este email, as configurações SMTP estão corretas!
            
            Data e hora do teste: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
            """
        )
        mail.send(msg)
        return jsonify({'success': True, 'message': 'Email enviado com sucesso!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ==================== GESTÃO DE MEMBROS ====================

@admin_bp.route('/members')
@login_required
def list_members():
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    # ========== ESTATÍSTICAS GLOBAIS ==========
    stats = {
        'total': User.query.count(),
        'active': User.query.filter_by(status='active').count(),
        'pending': User.query.filter_by(status='pending').count(),
        'churches': Church.query.count()
    }
    
    # ========== FILTROS ==========
    search = request.args.get('search', '').strip()
    church_id = request.args.get('church_id', type=int)
    role_id = request.args.get('role_id', type=int)
    status_filter = request.args.get('status')
    sort_by = request.args.get('sort', 'name')
    sort_order = request.args.get('order', 'asc')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Query base
    query = User.query
    
    # Aplicar filtros (mantendo compatibilidade com os antigos)
    if church_id:
        query = query.filter(User.church_id == church_id)
    
    if role_id:
        query = query.filter(User.church_role_id == role_id)
    
    if search:
        query = query.filter(or_(
            User.name.ilike(f'%{search}%'),
            User.email.ilike(f'%{search}%'),
            User.phone.ilike(f'%{search}%')
        ))
    
    if status_filter:
        query = query.filter(User.status == status_filter)
    
    # Ordenação
    if sort_by == 'name':
        order_column = User.name
    elif sort_by == 'church':
        order_column = User.church_id
    elif sort_by == 'status':
        order_column = User.status
    else:
        order_column = User.name
    
    if sort_order == 'desc':
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())
    
    # Paginação
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    members = pagination.items
    
    # Buscar dados para os filtros
    churches = Church.query.order_by(Church.name).all()
    roles = ChurchRole.query.filter_by(is_active=True).order_by(ChurchRole.name).all()
    
    # Variáveis para compatibilidade com o template antigo (se necessário)
    selected_church = Church.query.get(church_id) if church_id else None
    selected_role = ChurchRole.query.get(role_id) if role_id else None
    
    return render_template('admin/members.html',
                           members=members,
                           churches=churches,
                           roles=roles,
                           stats=stats,
                           pagination=pagination,
                           # Variáveis de compatibilidade (caso o template antigo as use)
                           selected_church=selected_church,
                           selected_role=selected_role,
                           current_church_id=church_id,
                           current_role_id=role_id,
                           total_members=query.count())

@admin_bp.route('/member/add', methods=['GET', 'POST'])
@login_required
def add_member():
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('admin.list_members'))

    churches = Church.query.all()
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        birth_date_str = request.form.get('birth_date')
        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None
        
        new_user = User(
            name=name,
            email=email,
            birth_date=birth_date,
            documents=request.form.get('documents'),
            address=request.form.get('address'),
            phone=request.form.get('phone'),
            gender=request.form.get('gender'),
            church_id=int(request.form.get('church_id')) if request.form.get('church_id') else None,
            status=request.form.get('status', 'active'),
            postal_code=request.form.get('postal_code'),
            concelho=request.form.get('concelho'),
            localidade=request.form.get('localidade'),
            education_level=request.form.get('education_level')
        )
        new_user.set_password(request.form.get('password'))
        db.session.add(new_user)
        db.session.commit()
        
        # === LOG ADICIONADO ===
        log_action(
            action='CREATE',
            module='MEMBERS',
            description=f"Novo membro adicionado: {new_user.name}",
            new_values={'id': new_user.id, 'name': new_user.name, 'email': new_user.email},
            church_id=new_user.church_id
        )
        # ======================
        
        flash('Membro criado com sucesso!', 'success')
        return redirect(url_for('admin.list_members'))
    
    return render_template('admin/add_member.html', churches=churches)

@admin_bp.route('/member/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_member(id):
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('admin.list_members'))

    member = User.query.get_or_404(id)
    churches = Church.query.all()
    roles = ChurchRole.query.filter_by(church_id=member.church_id).order_by(ChurchRole.order, ChurchRole.name).all() if member.church_id else []

    old_values = {'name': member.name, 'email': member.email, 'status': member.status}

    if request.method == 'POST':
        member.name = request.form.get('name')
        member.email = request.form.get('email')
        birth_date_str = request.form.get('birth_date')
        member.birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None
        member.gender = request.form.get('gender')
        member.documents = request.form.get('documents')
        member.tax_id = request.form.get('tax_id')
        member.address = request.form.get('address')
        member.phone = request.form.get('phone')
        member.church_id = int(request.form.get('church_id')) if request.form.get('church_id') else None
        member.church_role_id = int(request.form.get('church_role_id')) if request.form.get('church_role_id') else None
        member.status = request.form.get('status', 'active')
        
        member.postal_code = request.form.get('postal_code')
        member.concelho = request.form.get('concelho')
        member.localidade = request.form.get('localidade')
        member.education_level = request.form.get('education_level')
        
                # ===== ADICIONE ESTA LINHA =====
        if member.church_role_id:
            new_role = ChurchRole.query.get(member.church_role_id)
            member.is_lead_pastor = new_role.is_lead_pastor if new_role else False
        else:
            member.is_lead_pastor = False
        # ================================

        file = request.files.get('profile_photo')
        if file and file.filename:
            filename = secure_filename(file.filename)
            profiles_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles')
            os.makedirs(profiles_dir, exist_ok=True)
            full_path = os.path.join(profiles_dir, filename)
            file.save(full_path)
            member.profile_photo = f'uploads/profiles/{filename}'
        
        db.session.commit()
        
        # === LOG ADICIONADO ===
        log_action(
            action='UPDATE',
            module='MEMBERS',
            description=f"Membro editado: {member.name}",
            old_values=old_values,
            new_values={'name': member.name, 'email': member.email, 'status': member.status},
            church_id=member.church_id
        )
        # ======================
        
        flash('Membro atualizado com sucesso!', 'success')
        return redirect(url_for('admin.list_members'))
    
    return render_template('admin/edit_member.html', member=member, churches=churches, roles=roles)

@admin_bp.route('/member/card-preview/<int:id>')
@login_required
def member_card_preview(id):
    """Tela de pré-visualização e edição do cartão de membro"""
    member = User.query.get_or_404(id)
    
    is_global = is_global_admin()
    # Pastor líder pode gerar cartão para QUALQUER membro da sua igreja
    is_lead_pastor = (
        current_user.church_role 
        and current_user.church_role.is_lead_pastor
        and current_user.church_id == member.church_id  # ← CORRIGIDO!
    )
    
    if not (is_global or is_lead_pastor):
        flash('Acesso negado. Você não tem permissão para gerar o cartão deste membro.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    church = member.church
    if not church:
        flash('Membro não vinculado a nenhuma congregação.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    return render_template('admin/member_card_preview.html', member=member, church=church)


@admin_bp.route('/member/card/<int:id>')
@login_required
def member_card(id):
    member = User.query.get_or_404(id)
    
    is_global = is_global_admin()
    is_lead_pastor = (
        current_user.church_role 
        and current_user.church_role.is_lead_pastor 
        and current_user.church_id == member.church_id
    )
    
    if not (is_global or is_lead_pastor):
        flash('Acesso negado. Você não tem permissão para gerar o cartão deste membro.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    church = member.church
    if not church:
        flash('Membro não vinculado a nenhuma congregação.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    # Tamanho final da imagem (alta resolução para impressão nítida)
    WIDTH, HEIGHT = 1200, 756
    
    def generate_card_side(background_path, layout, fields_data, is_front=False):
        # Cria imagem base
        if background_path and os.path.exists(os.path.join(current_app.static_folder, background_path)):
            bg_path = os.path.join(current_app.static_folder, background_path)
            img = Image.open(bg_path).convert('RGBA')
            img = img.resize((WIDTH, HEIGHT), Image.LANCZOS)
        else:
            img = Image.new('RGBA', (WIDTH, HEIGHT), (255, 255, 255, 255))
        
        draw = ImageDraw.Draw(img)
        
        # Fontes maiores e com suporte a acentos (use uma font com UTF-8 no servidor)
        try:
            font_path = "fonts/DejaVuSans.ttf"  # Ou "times.ttf" se preferir serifada
            font_normal = ImageFont.truetype(font_path, 20)   # Aumentado
            font_bold = ImageFont.truetype(font_path, 25)     # Aumentado para nome/títulos
            font_small = ImageFont.truetype(font_path, 15)    # Aumentado para textos menores
        except:
            font_normal = ImageFont.load_default()
            font_bold = font_normal
            font_small = font_normal
        
        # Desenha cada campo
        for field, data in layout.items():
            if field not in fields_data:
                continue
            x = int(data.get('x', 0) * (WIDTH / 856))
            y = int(data.get('y', 0) * (HEIGHT / 540))
            w = int(data.get('width', 200) * (WIDTH / 856))
            h = int(data.get('height', 40) * (HEIGHT / 540))
            text = str(fields_data[field])
            
            # Sem fundo branco (já que a arte tem blanks) — se quiser, descomente:
            # draw.rectangle((x, y, x + w, y + h), fill=(255, 255, 255, 220))
            
            # Escolhe fonte baseada no campo
            font = font_bold if field in ['name', 'role', 'filiacao', 'signature'] else font_small if field in ['disclaimer'] else font_normal
            
            # Quebra linha para textos longos
            lines = textwrap.wrap(text, width=int(w / 8))  # Ajuste width para caber melhor (menor número = mais quebras)
            current_y = y + 5
            for line in lines:
                draw.text((x + 10, current_y), line, fill=(0, 0, 0), font=font)
                current_y += font.getbbox(line)[3] + 5  # Altura + espaçamento
        
        # Foto de perfil (apenas na frente)
        if is_front and member.profile_photo and 'photo' in layout:
            photo_data = layout['photo']
            photo_x = int(photo_data.get('x', 40) * (WIDTH / 856))
            photo_y = int(photo_data.get('y', 140) * (HEIGHT / 540))
            photo_w = int(photo_data.get('width', 220) * (WIDTH / 856))
            photo_h = int(photo_data.get('height', 280) * (HEIGHT / 540))
            
            photo_path = os.path.join(current_app.static_folder, member.profile_photo)
            if os.path.exists(photo_path):
                photo = Image.open(photo_path).convert('RGBA')
                # Redimensiona usando o size exato do layout, com fit e crop
                photo = ImageOps.fit(photo, (photo_w, photo_h), Image.LANCZOS)
                img.paste(photo, (photo_x, photo_y), photo)
        
        return img

    # Dados para frente
    front_layout = church.card_front_layout or {}
    front_data = {
        'name': member.name or '',
        'role': member.church_role.name if member.church_role else 'Membro',
        'marital_status': member.marital_status or 'Não informado',
        'birth_date': member.birth_date.strftime('%d/%m/%Y') if member.birth_date else 'Não informado',
    }
    
    # Dados para verso
    back_layout = church.card_back_layout or {}
    back_data = {
        'filiacao': church.name or 'Não informado',
        'document': member.tax_id or member.documents or 'Não informado',
        'conversion_date': member.conversion_date.strftime('%d/%m/%Y') if member.conversion_date else 'Não informado',
        'baptism_date': member.baptism_date.strftime('%d/%m/%Y') if member.baptism_date else 'Não informado',
        'disclaimer': 'Este documento tem validade enquanto o(a) titular permanecer em plena comunhão como membro da Assembleia de Deus IEAD Jesus para as Nações em Aveiro - Portugal.',
        'signature': 'Pr. Fernando Telles dos Santos\nPresidente da IEAD Jesus Para as Nações'
    }
    
    # Gera as imagens
    front_img = generate_card_side(church.member_card_front, front_layout, front_data, is_front=True)
    back_img = generate_card_side(church.member_card_back, back_layout, back_data, is_front=False)
    
    # Junta frente + verso verticalmente com espaço
    total_height = front_img.height + back_img.height + 60
    combined = Image.new('RGB', (max(front_img.width, back_img.width), total_height), (255, 255, 255))
    combined.paste(front_img, ((combined.width - front_img.width) // 2, 0))
    combined.paste(back_img, ((combined.width - back_img.width) // 2, front_img.height + 60))
    
    # Salva em memória e envia como PNG
    img_io = BytesIO()
    combined.save(img_io, 'PNG', quality=95)
    img_io.seek(0)
    
    return send_file(
        img_io,
        mimetype='image/png',
        as_attachment=True,
        download_name=f'cartao_membro_{member.name.replace(" ", "_")}.png'
    )


# ==================== GESTÃO DE CARGOS LOCAIS (Pastor Líder) ====================

@admin_bp.route('/roles')
@login_required
def list_roles():
    if not current_user.church_role or (
        not is_global_admin() and not current_user.church_role.is_lead_pastor
    ):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    roles = ChurchRole.query.filter_by(church_id=current_user.church_id)\
                   .order_by(ChurchRole.order, ChurchRole.name).all()
    return render_template('admin/list_roles.html', roles=roles)


@admin_bp.route('/role/add', methods=['GET', 'POST'])
@login_required
def add_role():
    if not current_user.church_role or (
        not is_global_admin() and not current_user.church_role.is_lead_pastor
    ):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('admin.list_roles'))
    
    if request.method == 'POST':
        new_role = ChurchRole(
            name=request.form.get('name'),
            description=request.form.get('description'),
            order=int(request.form.get('order') or 0),
            church_id=current_user.church_id,
            is_lead_pastor='is_lead_pastor' in request.form,
            is_active=True
        )
        db.session.add(new_role)
        db.session.commit()
        
        # === LOG ADICIONADO ===
        log_action(
            action='CREATE',
            module='ROLE',
            description=f"Novo cargo criado: {new_role.name}",
            new_values={'id': new_role.id, 'name': new_role.name},
            church_id=current_user.church_id
        )
        # ======================
        
        flash('Cargo criado com sucesso!', 'success')
        return redirect(url_for('admin.list_roles'))
    
    return render_template('admin/add_role.html')


@admin_bp.route('/role/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_role(id):
    role = ChurchRole.query.get_or_404(id)
    
    if not current_user.church_role or (
        not is_global_admin() 
        and (not current_user.church_role.is_lead_pastor or role.church_id != current_user.church_id)
    ):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('admin.list_roles'))
    
    old_values = {'name': role.name, 'description': role.description}
    
    if request.method == 'POST':
        role.name = request.form.get('name')
        role.description = request.form.get('description')
        role.order = int(request.form.get('order') or 0)
        role.is_active = 'is_active' in request.form
        role.is_lead_pastor = 'is_lead_pastor' in request.form
        db.session.commit()
        
        # === LOG ADICIONADO ===
        log_action(
            action='UPDATE',
            module='ROLE',
            description=f"Cargo editado: {role.name}",
            old_values=old_values,
            new_values={'name': role.name, 'is_active': role.is_active},
            church_id=role.church_id
        )
        # ======================
        
        flash('Cargo atualizado!', 'success')
        return redirect(url_for('admin.list_roles'))
    
    return render_template('admin/edit_role.html', role=role)


@admin_bp.route('/role/delete/<int:id>')
@login_required
def delete_role(id):
    role = ChurchRole.query.get_or_404(id)
    
    if not current_user.church_role or (
        not is_global_admin() 
        and (not current_user.church_role.is_lead_pastor or role.church_id != current_user.church_id)
    ):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('admin.list_roles'))
    
    role_data = {'id': role.id, 'name': role.name}
    # === LOG ADICIONADO ===
    log_action(
        action='DELETE',
        module='ROLE',
        description=f"Cargo excluído: {role_data['name']}",
        old_values=role_data,
        church_id=role.church_id
    )
    # ======================    
    db.session.delete(role)
    db.session.commit()
    

    
    flash('Cargo excluído com sucesso!', 'success')
    return redirect(url_for('admin.list_roles'))

# ==================== GESTÃO DE CARGOS POR FILIAL (ADMIN GLOBAL) ====================

@admin_bp.route('/church-roles')
@login_required
def list_church_roles():
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    churches = Church.query.order_by(Church.name).all()
    return render_template('admin/church_roles_select.html', churches=churches)


@admin_bp.route('/church-roles/<int:church_id>')
@login_required
def list_church_roles_by_id(church_id):
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    church = Church.query.get_or_404(church_id)
    roles = ChurchRole.query.filter_by(church_id=church_id)\
                   .order_by(ChurchRole.order, ChurchRole.name).all()
    
    return render_template('admin/church_roles_list.html', church=church, roles=roles)


@admin_bp.route('/church-roles/<int:church_id>/add', methods=['GET', 'POST'])
@login_required
def add_church_role(church_id):
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    church = Church.query.get_or_404(church_id)
    
    if request.method == 'POST':
        new_role = ChurchRole(
            name=request.form.get('name'),
            description=request.form.get('description'),
            order=int(request.form.get('order') or 0),
            church_id=church_id,
            is_lead_pastor='is_lead_pastor' in request.form,
            is_active=True
        )
        db.session.add(new_role)
        db.session.commit()
        
        # === LOG ADICIONADO ===
        log_action(
            action='CREATE',
            module='ROLE',
            description=f"Novo cargo criado por admin global para {church.name}: {new_role.name}",
            new_values={'id': new_role.id, 'name': new_role.name},
            church_id=church_id
        )
        # ======================
        
        flash('Cargo criado com sucesso!', 'success')
        return redirect(url_for('admin.list_church_roles_by_id', church_id=church_id))
    
    return render_template('admin/add_church_role.html', church=church)


@admin_bp.route('/church-roles/<int:church_id>/edit/<int:role_id>', methods=['GET', 'POST'])
@login_required
def edit_church_role(church_id, role_id):
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    church = Church.query.get_or_404(church_id)
    role = ChurchRole.query.get_or_404(role_id)
    
    if role.church_id != church_id:
        flash('Cargo não encontrado nesta congregação.', 'danger')
        return redirect(url_for('admin.list_church_roles_by_id', church_id=church_id))
    
    old_values = {'name': role.name, 'description': role.description}
    
    if request.method == 'POST':
        role.name = request.form.get('name')
        role.description = request.form.get('description')
        role.order = int(request.form.get('order') or 0)
        role.is_active = 'is_active' in request.form
        role.is_lead_pastor = 'is_lead_pastor' in request.form
        db.session.commit()
        
        # === LOG ADICIONADO ===
        log_action(
            action='UPDATE',
            module='ROLE',
            description=f"Cargo editado por admin global em {church.name}: {role.name}",
            old_values=old_values,
            new_values={'name': role.name, 'is_active': role.is_active},
            church_id=church_id
        )
        # ======================
        
        flash('Cargo atualizado!', 'success')
        return redirect(url_for('admin.list_church_roles_by_id', church_id=church_id))
    
    return render_template('admin/edit_church_role.html', church=church, role=role)


@admin_bp.route('/church-roles/<int:church_id>/delete/<int:role_id>')
@login_required
def delete_church_role(church_id, role_id):
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    church = Church.query.get_or_404(church_id)
    role = ChurchRole.query.get_or_404(role_id)
    
    if role.church_id != church_id:
        flash('Cargo não encontrado nesta congregação.', 'danger')
        return redirect(url_for('admin.list_church_roles_by_id', church_id=church_id))
    
    role_data = {'id': role.id, 'name': role.name}
    # === LOG ADICIONADO ===
    log_action(
        action='DELETE',
        module='ROLE',
        description=f"Cargo excluído por admin global em {church.name}: {role_data['name']}",
        old_values=role_data,
        church_id=church_id
    )
    # ======================    
    db.session.delete(role)
    db.session.commit()
    

    
    flash('Cargo excluído com sucesso!', 'success')
    return redirect(url_for('admin.list_church_roles_by_id', church_id=church_id))

@admin_bp.route('/member/card-generate/<int:id>', methods=['POST'])
@login_required
def member_card_generate(id):
    """Gera o cartao PNG com foto customizada e zoom"""
    member = User.query.get_or_404(id)
    
    is_global = is_global_admin()
    is_lead_pastor = (
        current_user.church_role 
        and current_user.church_role.is_lead_pastor
        and current_user.church_id == member.church_id  # ← CORRIGIDO!
    )
    
    if not (is_global or is_lead_pastor):
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    church = member.church
    if not church:
        return jsonify({'success': False, 'message': 'Membro nao vinculado a nenhuma congregacao'}), 400
    
    WIDTH, HEIGHT = 1200, 756
    
    def generate_card_side_custom(background_path, layout, fields_data, custom_photo_path=None, photo_zoom=1.0, photo_offset_x=0, photo_offset_y=0, is_front=False):
        # Cria imagem base
        if background_path and os.path.exists(os.path.join(current_app.static_folder, background_path)):
            bg_path = os.path.join(current_app.static_folder, background_path)
            img = Image.open(bg_path).convert('RGBA')
            img = img.resize((WIDTH, HEIGHT), Image.LANCZOS)
        else:
            img = Image.new('RGBA', (WIDTH, HEIGHT), (255, 255, 255, 255))
        
        draw = ImageDraw.Draw(img)
        
        try:
            font_path = "fonts/DejaVuSans.ttf"
            font_normal = ImageFont.truetype(font_path, 20)
            font_bold = ImageFont.truetype(font_path, 25)
            font_small = ImageFont.truetype(font_path, 15)
        except:
            font_normal = ImageFont.load_default()
            font_bold = font_normal
            font_small = font_normal
        
        for field, data in layout.items():
            if field not in fields_data:
                continue
            x = int(data.get('x', 0) * (WIDTH / 856))
            y = int(data.get('y', 0) * (HEIGHT / 540))
            w = int(data.get('width', 200) * (WIDTH / 856))
            h = int(data.get('height', 40) * (HEIGHT / 540))
            text = str(fields_data[field])
            
            font = font_bold if field in ['name', 'role', 'filiacao', 'signature'] else font_small if field in ['disclaimer'] else font_normal
            
            lines = textwrap.wrap(text, width=int(w / 8))
            current_y = y + 5
            for line in lines:
                draw.text((x + 10, current_y), line, fill=(0, 0, 0), font=font)
                current_y += font.getbbox(line)[3] + 5
        
        if is_front and 'photo' in layout:
            photo_data = layout['photo']
            photo_x = int(photo_data.get('x', 40) * (WIDTH / 856))
            photo_y = int(photo_data.get('y', 140) * (HEIGHT / 540))
            photo_w = int(photo_data.get('width', 220) * (WIDTH / 856))
            photo_h = int(photo_data.get('height', 280) * (HEIGHT / 540))
            
            photo_path_to_use = custom_photo_path if custom_photo_path else member.profile_photo
            
            if photo_path_to_use:
                if custom_photo_path and custom_photo_path.startswith('/'):
                    photo_file_path = custom_photo_path
                else:
                    photo_file_path = os.path.join(current_app.static_folder, photo_path_to_use)
                
                if os.path.exists(photo_file_path):
                    photo = Image.open(photo_file_path).convert('RGBA')
                    photo_resized = ImageOps.fit(photo, (photo_w, photo_h), Image.LANCZOS)
                    if photo_zoom != 1.0:
                        zoomed_w = int(photo_resized.width * photo_zoom)
                        zoomed_h = int(photo_resized.height * photo_zoom)
                        photo_resized = photo_resized.resize((zoomed_w, zoomed_h), Image.LANCZOS)
                    center_x = (photo_w - photo_resized.width) // 2
                    center_y = (photo_h - photo_resized.height) // 2
                    scale_factor = (WIDTH / 856)
                    scaled_offset_x = int(photo_offset_x * scale_factor)
                    scaled_offset_y = int(photo_offset_y * scale_factor)
                    final_x = center_x + scaled_offset_x
                    final_y = center_y + scaled_offset_y
                    final_x = max(0, min(final_x, photo_w - photo_resized.width))
                    final_y = max(0, min(final_y, photo_h - photo_resized.height))
                    temp_img = Image.new('RGBA', (photo_w, photo_h), (0, 0, 0, 0))
                    temp_img.paste(photo_resized, (final_x, final_y), photo_resized)
                    img.paste(temp_img, (photo_x, photo_y), temp_img)
        
        return img
    
    data = request.get_json()
    photo_zoom = float(data.get('photo_zoom', 1.0))
    photo_offset_x = float(data.get('photo_offset_x', 0))
    photo_offset_y = float(data.get('photo_offset_y', 0))
    custom_photo_path = data.get('custom_photo_path')
    
    front_layout = church.card_front_layout or {}
    front_data = {
        'name': member.name or '',
        'role': member.church_role.name if member.church_role else 'Membro',
        'marital_status': member.marital_status or 'Nao informado',
        'birth_date': member.birth_date.strftime('%d/%m/%Y') if member.birth_date else 'Nao informado',
    }
    
    back_layout = church.card_back_layout or {}
    back_data = {
        'filiacao': church.name or 'Nao informado',
        'document': member.tax_id or member.documents or 'Nao informado',
        'conversion_date': member.conversion_date.strftime('%d/%m/%Y') if member.conversion_date else 'Nao informado',
        'baptism_date': member.baptism_date.strftime('%d/%m/%Y') if member.baptism_date else 'Nao informado',
        'disclaimer': 'Este documento tem validade enquanto o(a) titular permanecer em plena comunhao como membro da Assembleia de Deus IEAD Jesus para as Nacoes em Aveiro - Portugal.',
        'signature': 'Pr. Fernando Telles dos Santos\nPresidente da IEAD Jesus Para as Nacoes'
    }
    
    front_img = generate_card_side_custom(
        church.member_card_front, 
        front_layout, 
        front_data, 
        custom_photo_path=custom_photo_path,
        photo_zoom=photo_zoom,
        photo_offset_x=photo_offset_x,
        photo_offset_y=photo_offset_y,
        is_front=True
    )
    back_img = generate_card_side_custom(
        church.member_card_back, 
        back_layout, 
        back_data, 
        is_front=False
    )
    
    total_height = front_img.height + back_img.height + 60
    combined = Image.new('RGB', (max(front_img.width, back_img.width), total_height), (255, 255, 255))
    combined.paste(front_img, ((combined.width - front_img.width) // 2, 0))
    combined.paste(back_img, ((combined.width - back_img.width) // 2, front_img.height + 60))
    
    img_io = BytesIO()
    combined.save(img_io, 'PNG', quality=95)
    img_io.seek(0)
    
    # === LOG ADICIONADO ===
    log_action(
        action='GENERATE',
        module='CARD',
        description=f"Cartão de membro gerado para: {member.name}",
        new_values={'member_id': member.id},
        church_id=member.church_id
    )
    # ======================
    
    return send_file(
        img_io,
        mimetype='image/png',
        as_attachment=True,
        download_name=f'cartao_membro_{member.name.replace(" ", "_")}.png'
    )


@admin_bp.route('/member/card-upload-temp/<int:id>', methods=['POST'])
@login_required
def member_card_upload_temp(id):
    """Upload temporario de foto para pre-visualizacao"""
    member = User.query.get_or_404(id)
    
    is_global = is_global_admin()
    is_lead_pastor = (
        current_user.church_role 
        and current_user.church_role.is_lead_pastor 
        and current_user.church_role == member.church_role
    )
    
    if not (is_global or is_lead_pastor):
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    file = request.files.get('photo')
    if not file or not file.filename:
        return jsonify({'success': False, 'message': 'Nenhum arquivo enviado'}), 400
    
    try:
        filename = secure_filename(file.filename)
        temp_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'temp_card_photos')
        os.makedirs(temp_dir, exist_ok=True)
        
        unique_filename = f"{uuid.uuid4()}_{filename}"
        full_path = os.path.join(temp_dir, unique_filename)
        file.save(full_path)
        
        return jsonify({
            'success': True,
            'photo_path': full_path,
            'photo_url': f"/static/uploads/temp_card_photos/{unique_filename}"
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ==================== LOGS DO SISTEMA ====================

@admin_bp.route('/logs')
@login_required
def view_logs():
    """Visualização de logs do sistema"""
    from app.core.models import SystemLog, Church
    
    is_global = is_global_admin()
    is_pastor = current_user.church_role and current_user.church_role.is_lead_pastor
    
    if not (is_global or is_pastor):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    church_id = request.args.get('church_id', type=int)
    page = request.args.get('page', 1, type=int)
    
    query = SystemLog.query
    
    if is_pastor and not is_global:
        query = query.filter_by(church_id=current_user.church_id)
    elif church_id:
        query = query.filter_by(church_id=church_id)
    
    logs = query.order_by(SystemLog.created_at.desc()).paginate(page=page, per_page=50)
    churches = Church.query.all() if is_global else []
    
    return render_template('admin/logs.html', logs=logs, churches=churches)


@admin_bp.route('/log-details/<int:log_id>')
@login_required
def log_details(log_id):
    """Retorna detalhes de um log específico"""
    from app.core.models import SystemLog
    
    log = SystemLog.query.get_or_404(log_id)
    
    is_global = is_global_admin()
    is_pastor = current_user.church_role and current_user.church_role.is_lead_pastor
    
    if not (is_global or is_pastor):
        return jsonify({'error': 'Acesso negado'}), 403
    
    if is_pastor and not is_global and log.church_id != current_user.church_id:
        return jsonify({'error': 'Acesso negado'}), 403
    
    return jsonify({
        'old_values': log.old_values,
        'new_values': log.new_values
    })

# ==================== TEMAS PERSONALIZADOS ====================

@admin_bp.route('/church/<int:church_id>/theme', methods=['GET', 'POST'])
@login_required
def edit_church_theme(church_id):
    """Configurar tema personalizado da igreja"""
    from app.core.models import ChurchTheme
    import os
    
    church = Church.query.get_or_404(church_id)
    if not can_edit_church(church):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('admin.list_churches'))
    
    # Buscar ou criar tema (sempre existe, nunca é deletado)
    theme = ChurchTheme.query.filter_by(church_id=church.id).first()
    if not theme:
        theme = ChurchTheme(church_id=church.id)
        db.session.add(theme)
        db.session.commit()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'reset':
            # RESTAURAR PADRÃO
            theme.is_custom = False
            
            # Limpar logos
            theme.logo_light = None
            theme.logo_dark = None
            
            for logo_type in ['light', 'dark']:
                logo_attr = f'logo_{logo_type}'
                old_logo = getattr(theme, logo_attr, None)
                if old_logo:
                    full_path = os.path.join(
                        current_app.config['UPLOAD_FOLDER'],
                        'churches',
                        'themes',
                        os.path.basename(old_logo)
                    )
                    if os.path.exists(full_path):
                        try:
                            os.remove(full_path)
                        except Exception as e:
                            current_app.logger.warning(f"Não foi possível remover o logo {logo_type}: {e}")
            
            db.session.commit()
            
            log_action(
                action='RESET',
                module='THEME',
                description=f"Tema restaurado para o padrão para {church.name} (logos removidos)",
                church_id=church.id
            )
            
            flash('Tema restaurado para o padrão! Logos removidos. Você pode personalizar novamente quando quiser.', 'success')
            return redirect(url_for('admin.edit_church_theme', church_id=church.id))
        
        # SALVAR TEMA PERSONALIZADO
        theme.is_custom = True
        
        # Cores do tema claro
        theme.light_primary = request.form.get('light_primary', '#4f46e5')
        theme.light_primary_hover = request.form.get('light_primary_hover', '#4338ca')
        theme.light_secondary = request.form.get('light_secondary', '#64748b')
        theme.light_success = request.form.get('light_success', '#10b981')
        theme.light_danger = request.form.get('light_danger', '#ef4444')
        theme.light_warning = request.form.get('light_warning', '#f59e0b')
        theme.light_info = request.form.get('light_info', '#06b6d4')
        theme.light_bg_main = request.form.get('light_bg_main', '#f8fafc')
        theme.light_bg_card = request.form.get('light_bg_card', '#ffffff')
        theme.light_text_main = request.form.get('light_text_main', '#1e293b')
        theme.light_text_muted = request.form.get('light_text_muted', '#64748b')
        theme.light_border = request.form.get('light_border', '#e2e8f0')
        theme.light_sidebar_bg = request.form.get('light_sidebar_bg', '#1e293b')
        theme.light_sidebar_text = request.form.get('light_sidebar_text', '#f8fafc')
        theme.light_input_bg = request.form.get('light_input_bg', '#ffffff')
        
        # 🔥 NOVOS CAMPOS DE TABELA (TEMA CLARO)
        theme.light_table_header_bg = request.form.get('light_table_header_bg', '#f8fafc')
        theme.light_table_header_text = request.form.get('light_table_header_text', '#1e293b')
        theme.light_table_row_bg = request.form.get('light_table_row_bg', '#ffffff')
        theme.light_table_row_hover = request.form.get('light_table_row_hover', '#f1f5f9')
        theme.light_table_border = request.form.get('light_table_border', '#e2e8f0')
        
        # Cores do tema escuro
        theme.dark_primary = request.form.get('dark_primary', '#6366f1')
        theme.dark_primary_hover = request.form.get('dark_primary_hover', '#818cf8')
        theme.dark_secondary = request.form.get('dark_secondary', '#94a3b8')
        theme.dark_success = request.form.get('dark_success', '#34d399')
        theme.dark_danger = request.form.get('dark_danger', '#f87171')
        theme.dark_warning = request.form.get('dark_warning', '#fbbf24')
        theme.dark_info = request.form.get('dark_info', '#22d3ee')
        theme.dark_bg_main = request.form.get('dark_bg_main', '#0f172a')
        theme.dark_bg_card = request.form.get('dark_bg_card', '#1e293b')
        theme.dark_text_main = request.form.get('dark_text_main', '#f1f5f9')
        theme.dark_text_muted = request.form.get('dark_text_muted', '#94a3b8')
        theme.dark_border = request.form.get('dark_border', '#334155')
        theme.dark_sidebar_bg = request.form.get('dark_sidebar_bg', '#020617')
        theme.dark_sidebar_text = request.form.get('dark_sidebar_text', '#f1f5f9')
        theme.dark_input_bg = request.form.get('dark_input_bg', '#1e293b')
        
        # 🔥 NOVOS CAMPOS DE TABELA (TEMA ESCURO)
        theme.dark_table_header_bg = request.form.get('dark_table_header_bg', '#1e293b')
        theme.dark_table_header_text = request.form.get('dark_table_header_text', '#f1f5f9')
        theme.dark_table_row_bg = request.form.get('dark_table_row_bg', '#0f172a')
        theme.dark_table_row_hover = request.form.get('dark_table_row_hover', '#1e293b')
        theme.dark_table_border = request.form.get('dark_table_border', '#334155')
        
        # CAMPOS DO DEVOCIONAL
        theme.devotional_gradient_start = request.form.get('devotional_gradient_start', '#4f46e5')
        theme.devotional_gradient_end = request.form.get('devotional_gradient_end', '#06b6d4')
        theme.devotional_text_color = request.form.get('devotional_text_color', '#ffffff')
        theme.devotional_badge_bg = request.form.get('devotional_badge_bg', '#ffffff')
        theme.devotional_badge_text = request.form.get('devotional_badge_text', '#4f46e5')
        theme.devotional_icon_color = request.form.get('devotional_icon_color', '#ffffff')
        
        # Overlays (vêm como rgba dos campos hidden)
        theme.devotional_overlay_light = request.form.get('devotional_overlay_light', 'rgba(0,0,0,0.4)')
        theme.devotional_overlay_dark = request.form.get('devotional_overlay_dark', 'rgba(0,0,0,0.6)')
        
        # CSS personalizado
        theme.custom_css = request.form.get('custom_css')
        
        # Upload de logos
        for logo_type in ['light', 'dark']:
            file = request.files.get(f'logo_{logo_type}')
            if file and file.filename:
                filename = secure_filename(file.filename)
                new_filename = f"{church.id}_{logo_type}_{filename}"
                relative_path = f'uploads/churches/themes/{new_filename}'
                full_path = os.path.join(
                    current_app.config['UPLOAD_FOLDER'], 
                    'churches', 
                    'themes', 
                    new_filename
                )
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                file.save(full_path)
                setattr(theme, f'logo_{logo_type}', relative_path)
        
        db.session.commit()
        
        log_action(
            action='UPDATE',
            module='THEME',
            description=f"Tema personalizado para {church.name}",
            church_id=church.id
        )
        
        flash('Tema personalizado salvo com sucesso!', 'success')
        return redirect(url_for('admin.edit_church_theme', church_id=church.id))
    
    return render_template('admin/church_theme.html', church=church, theme=theme)