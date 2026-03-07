# Arquivo completo: app/modules/admin/routes.py
# Consolidado com Gestão Global de Membros (filtros/totalizador) e Gestão de Cargos por Filial
# Atualizado para usar campo is_lead_pastor em vez de nome fixo 'Pastor Líder'
# + Nova rota para configuração do layout do cartão de membro

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app.core.models import Church, db, User, ChurchRole
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageOps
from io import BytesIO
from flask import send_file
import textwrap  # Para quebrar linhas longas se necessário
import uuid
import json

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
        flash('Congregação atualizada!', 'success')
        return redirect(url_for('admin.list_churches'))
    
    return render_template('admin/edit_church.html', church=church)

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

    try:
        User.query.filter_by(church_id=id).update({User.church_id: None})
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
            church.card_front_layout = data.get('front', {})
            church.card_back_layout = data.get('back', {})
            db.session.commit()
            return jsonify({'success': True, 'message': 'Layout do cartão salvo com sucesso!'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return render_template('admin/edit_card_layout.html', church=church)

# ==================== GESTÃO DE MEMBROS ====================

@admin_bp.route('/members')
@login_required
def list_members():
    if not is_global_admin():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    church_id = request.args.get('church_id', type=int)
    role_id = request.args.get('role_id', type=int)
    
    query = User.query
    selected_church = None
    selected_role = None
    
    if church_id:
        selected_church = Church.query.get(church_id)
        if selected_church:
            query = query.filter_by(church_id=church_id)
    
    if role_id:
        selected_role = ChurchRole.query.get(role_id)
        if selected_role:
            query = query.filter_by(church_role_id=role_id)
    
    members = query.order_by(User.name).all()
    total_members = len(members)
    
    churches = Church.query.order_by(Church.name).all()
    roles = ChurchRole.query.order_by(ChurchRole.name).all()
    
    return render_template(
        'admin/members.html',
        members=members,
        churches=churches,
        roles=roles,
        selected_church=selected_church,
        selected_role=selected_role,
        current_church_id=church_id,
        current_role_id=role_id,
        total_members=total_members
    )

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
        
        file = request.files.get('profile_photo')
        if file and file.filename:
            filename = secure_filename(file.filename)
            profiles_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles')
            os.makedirs(profiles_dir, exist_ok=True)
            full_path = os.path.join(profiles_dir, filename)
            file.save(full_path)
            member.profile_photo = f'uploads/profiles/{filename}'
        
        db.session.commit()
        flash('Membro atualizado com sucesso!', 'success')
        return redirect(url_for('admin.list_members'))
    
    return render_template('admin/edit_member.html', member=member, churches=churches, roles=roles)

@admin_bp.route('/member/card-preview/<int:id>')
@login_required
def member_card_preview(id):
    """Tela de pré-visualização e edição do cartão de membro"""
    member = User.query.get_or_404(id)
    
    is_global = is_global_admin()
    is_lead_pastor = (
        current_user.church_role 
        and current_user.church_role.is_lead_pastor 
        and current_user.church_role == member.church_role
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
    WIDTH, HEIGHT = 1200, 756  # Aumente para 2400, 1512 se quiser ainda mais qualidade
    
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
    
    if request.method == 'POST':
        role.name = request.form.get('name')
        role.description = request.form.get('description')
        role.order = int(request.form.get('order') or 0)
        role.is_active = 'is_active' in request.form
        role.is_lead_pastor = 'is_lead_pastor' in request.form
        db.session.commit()
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
    
    if request.method == 'POST':
        role.name = request.form.get('name')
        role.description = request.form.get('description')
        role.order = int(request.form.get('order') or 0)
        role.is_active = 'is_active' in request.form
        role.is_lead_pastor = 'is_lead_pastor' in request.form
        db.session.commit()
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
        and current_user.church_role == member.church_role
    )
    
    if not (is_global or is_lead_pastor):
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    church = member.church
    if not church:
        return jsonify({'success': False, 'message': 'Membro nao vinculado a nenhuma congregacao'}), 400
    
    WIDTH, HEIGHT = 1200, 756
    
    def generate_card_side_custom(background_path, layout, fields_data, custom_photo_path=None, photo_zoom=1.0, photo_offset_x=0, photo_offset_y=0, is_front=False):
        # Criar imagem base com background
        if background_path and os.path.exists(os.path.join(current_app.static_folder, background_path)):
            bg_path = os.path.join(current_app.static_folder, background_path)
            img = Image.open(bg_path).convert('RGBA')
            img = img.resize((WIDTH, HEIGHT), Image.LANCZOS)
        else:
            img = Image.new('RGBA', (WIDTH, HEIGHT), (255, 255, 255, 255))
        
        draw = ImageDraw.Draw(img)
        
        # Configurar fontes
        try:
            font_path = "fonts/DejaVuSans.ttf"
            font_normal = ImageFont.truetype(font_path, 20)
            font_bold = ImageFont.truetype(font_path, 25)
            font_small = ImageFont.truetype(font_path, 15)
        except:
            font_normal = ImageFont.load_default()
            font_bold = font_normal
            font_small = font_normal
        
        # Renderizar campos de texto
        for field, data in layout.items():
            if field not in fields_data or field == 'photo':
                continue
                
            x = int(data.get('x', 0) * (WIDTH / 856))
            y = int(data.get('y', 0) * (HEIGHT / 540))
            w = int(data.get('width', 200) * (WIDTH / 856))
            text = str(fields_data[field])
            
            if field in ['name', 'role', 'filiacao', 'signature']:
                font = font_bold
            elif field in ['disclaimer']:
                font = font_small
            else:
                font = font_normal
            
            lines = textwrap.wrap(text, width=int(w / 8))
            current_y = y + 5
            for line in lines:
                draw.text((x + 10, current_y), line, fill=(0, 0, 0), font=font)
                current_y += font.getbbox(line)[3] + 5
        
        # Renderizar foto (apenas na frente)
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
                    
                    # Ajustar foto para caber no espaço
                    photo_fitted = ImageOps.fit(photo, (photo_w, photo_h), Image.LANCZOS)
                    
                    # Aplicar zoom
                    if photo_zoom != 1.0:
                        zoomed_w = int(photo_fitted.width * photo_zoom)
                        zoomed_h = int(photo_fitted.height * photo_zoom)
                        photo_resized = photo_fitted.resize((zoomed_w, zoomed_h), Image.LANCZOS)
                    else:
                        photo_resized = photo_fitted
                    
                    # Calcular posição central
                    center_x = (photo_w - photo_resized.width) // 2
                    center_y = (photo_h - photo_resized.height) // 2
                    
                    # Aplicar offset do arrasto
                    final_x = center_x + int(photo_offset_x)
                    final_y = center_y + int(photo_offset_y)
                    
                    # Limitar para não sair completamente da área
                    final_x = max(-photo_resized.width + 20, min(final_x, photo_w - 20))
                    final_y = max(-photo_resized.height + 20, min(final_y, photo_h - 20))
                    
                    # Colar foto no cartão
                    temp_img = Image.new('RGBA', (photo_w, photo_h), (0, 0, 0, 0))
                    temp_img.paste(photo_resized, (final_x, final_y), photo_resized)
                    img.paste(temp_img, (photo_x, photo_y), temp_img)
        
        return img
    
    # Receber dados do frontend
    data = request.get_json()
    photo_zoom = float(data.get('photo_zoom', 1.0))
    photo_offset_x = float(data.get('photo_offset_x', 0))
    photo_offset_y = float(data.get('photo_offset_y', 0))
    custom_photo_path = data.get('custom_photo_path')
    
    # Preparar dados
    front_layout = church.card_front_layout or {}
    front_data = {
        'name': member.name or '',
        'role': member.church_role.name if member.church_role else 'Membro',
        'marital_status': member.marital_status or 'Não informado',
        'birth_date': member.birth_date.strftime('%d/%m/%Y') if member.birth_date else 'Não informado',
    }
    
    back_layout = church.card_back_layout or {}
    back_data = {
        'filiacao': church.name or 'Não informado',
        'document': member.tax_id or member.documents or 'Não informado',
        'conversion_date': member.conversion_date.strftime('%d/%m/%Y') if member.conversion_date else 'Não informado',
        'baptism_date': member.baptism_date.strftime('%d/%m/%Y') if member.baptism_date else 'Não informado',
        'disclaimer': 'Este documento tem validade enquanto o(a) titular permanecer em plena comunhão como membro da Assembleia de Deus IEAD Jesus para as Nações em Aveiro - Portugal.',
        'signature': 'Pr. Fernando Telles dos Santos\nPresidente da IEAD Jesus Para as Nações'
    }
    
    # Gerar imagens
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
    
    # Combinar frente e verso
    total_height = front_img.height + back_img.height + 60
    combined = Image.new('RGB', (max(front_img.width, back_img.width), total_height), (255, 255, 255))
    combined.paste(front_img, ((combined.width - front_img.width) // 2, 0))
    combined.paste(back_img, ((combined.width - back_img.width) // 2, front_img.height + 60))
    
    # Salvar e enviar
    img_io = BytesIO()
    combined.save(img_io, 'PNG', quality=95)
    img_io.seek(0)
    
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
    
@admin_bp.route('/logs')
@login_required
def view_logs():
    """Visualização de logs do sistema"""
    # Verificar permissão
    is_global = is_global_admin()
    is_pastor = current_user.church_role and current_user.church_role.is_lead_pastor
    
    if not (is_global or is_pastor):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    from app.core.models import SystemLog, Church
    
    # Filtros
    church_id = request.args.get('church_id', type=int)
    module = request.args.get('module')
    action = request.args.get('action')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    page = request.args.get('page', 1, type=int)
    
    # Query base
    query = SystemLog.query
    
    # Filtrar por igreja (pastor só vê sua igreja)
    if is_pastor and not is_global:
        query = query.filter_by(church_id=current_user.church_id)
    elif church_id:
        query = query.filter_by(church_id=church_id)
    
    # Aplicar filtros
    if module:
        query = query.filter_by(module=module)
    if action:
        query = query.filter_by(action=action)
    if start_date:
        query = query.filter(SystemLog.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(SystemLog.created_at <= datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))
    
    # Ordenar e paginar
    logs = query.order_by(SystemLog.created_at.desc()).paginate(page=page, per_page=50)
    
    # Lista de igrejas para filtro (apenas admin global)
    churches = Church.query.all() if is_global else []
    
    return render_template('admin/logs.html', logs=logs, churches=churches)

@admin_bp.route('/log-details/<int:log_id>')
@login_required
def log_details(log_id):
    """Retorna detalhes de um log específico (valores antigos/novos)"""
    from app.core.models import SystemLog
    
    log = SystemLog.query.get_or_404(log_id)
    
    # Verificar permissão
    is_global = is_global_admin()
    is_pastor = current_user.church_role and current_user.church_role.is_lead_pastor
    
    if not (is_global or is_pastor):
        return jsonify({'error': 'Acesso negado'}), 403
    
    # Pastor só vê logs da sua igreja
    if is_pastor and not is_global and log.church_id != current_user.church_id:
        return jsonify({'error': 'Acesso negado'}), 403
    
    return jsonify({
        'old_values': log.old_values,
        'new_values': log.new_values
    })
