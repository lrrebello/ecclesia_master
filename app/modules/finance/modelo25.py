from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, current_app, jsonify, send_file
from flask_login import login_required, current_user
from app.core.models import Transaction, User, Church, db
from datetime import datetime
from sqlalchemy import func
import os
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors

# Se você estiver usando fill_modelo25_pdf de outro arquivo:
from app.utils.pdf_modelo25 import fill_modelo25_pdf

modelo25_bp = Blueprint('modelo25', __name__, url_prefix='/finance/modelo25')

def can_manage_finance():
    return current_user.can_manage_finance or (
        current_user.church_role and (
            current_user.church_role.name == 'Administrador Global' or
            current_user.church_role.is_lead_pastor or
            current_user.church_role.name == 'Tesoureiro'
        )
    )

def validate_tax_id(tax_id, country='Portugal'):
    if not tax_id: return False
    clean_id = ''.join(filter(str.isdigit, str(tax_id)))
    if country.lower() == 'portugal':
        if len(clean_id) != 9: return False
        check_digit = int(clean_id[8])
        sum_val = sum(int(clean_id[i]) * (9 - i) for i in range(8))
        mod = sum_val % 11
        expected = 0 if mod in [0, 1] else (11 - mod)
        return check_digit == expected
    return len(clean_id) > 0

def get_modelo25_data(church_id, year):
    start_date, end_date = datetime(year, 1, 1), datetime(year, 12, 31, 23, 59, 59)
    donations = db.session.query(
        User.id, User.name, User.tax_id, User.address,
        func.sum(Transaction.amount).label('total_amount'),
        func.count(Transaction.id).label('num_donations')
    ).join(Transaction, Transaction.user_id == User.id).filter(
        Transaction.church_id == church_id,
        Transaction.type == 'income',
        Transaction.date >= start_date,
        Transaction.date <= end_date,
        Transaction.user_id.isnot(None)
    ).group_by(User.id, User.name, User.tax_id, User.address).order_by(User.name).all()
    
    return [{
        'user_id': d.id, 'name': d.name, 'tax_id': d.tax_id, 'address': d.address,
        'total_amount': float(d.total_amount), 'num_donations': d.num_donations
    } for d in donations]

@modelo25_bp.route('/')
@login_required
def index():
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
    current_year = datetime.now().year
    available_years = list(range(current_year - 5, current_year + 1))[::-1]
    return render_template('finance/modelo25_index.html', available_years=available_years, current_year=current_year - 1)

@modelo25_bp.route('/preview/<int:year>')
@login_required
def preview(year):
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
    church = Church.query.get(current_user.church_id)
    donations = get_modelo25_data(current_user.church_id, year)
    valid_donations = [d for d in donations if d['tax_id'] and validate_tax_id(d['tax_id'], church.country)]
    invalid_donations = [d for d in donations if not d['tax_id'] or not validate_tax_id(d['tax_id'], church.country)]
    
    stats = {
        'total_donors': len(valid_donations),
        'total_amount': sum(d['total_amount'] for d in valid_donations),
        'total_donations': sum(d['num_donations'] for d in valid_donations),
        'excluded_donors': len(invalid_donations),
        'excluded_amount': sum(d['total_amount'] for d in invalid_donations)
    }
    return render_template('finance/modelo25_preview.html', church=church, year=year, donations=valid_donations, invalid_donations=invalid_donations, stats=stats, errors=[], warnings=[])

@modelo25_bp.route('/generate/<int:year>')
@login_required
def generate(year):
    church = Church.query.get(current_user.church_id)
    donations = get_modelo25_data(current_user.church_id, year)
    valid_donations = [d for d in donations if d['tax_id'] and validate_tax_id(d['tax_id'], church.country)]
    
    filename = f"Modelo25_{church.nif}_{year}.xlsx"
    filepath = os.path.join(current_app.root_path, 'static', 'uploads', 'receipts', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    wb = Workbook()
    ws = wb.active
    ws.append(['NIF Doador', 'Código', 'Valor Total (€)'])
    for d in valid_donations:
        ws.append([d['tax_id'], '01', d['total_amount']])
    wb.save(filepath)
    return send_file(filepath, as_attachment=True, download_name=filename)

@modelo25_bp.route('/generate-pdf/<int:year>')
@login_required
def generate_pdf(year):
    church = Church.query.get(current_user.church_id)
    donations = get_modelo25_data(current_user.church_id, year)
    valid_donations = [d for d in donations if d['tax_id'] and validate_tax_id(d['tax_id'], church.country)]
    
    data = {
        'nif_declarante': church.nif or '',
        'nome_declarante': church.name or '',
        'ano': year,
        'operacoes': [
            {
                'nif': d['tax_id'],
                'nome': d['name'],
                'codigo': '01',  # Donativos em dinheiro ou espécie
                'valor': d['total_amount']
            } for d in valid_donations
        ]
    }
    
    pdf_path = fill_modelo25_pdf(data)
    if pdf_path:
        filename = os.path.basename(pdf_path)
        return send_from_directory(os.path.dirname(pdf_path), filename, as_attachment=True)
    else:
        flash('Erro ao gerar PDF oficial do Modelo 25.', 'danger')
        return redirect(url_for('modelo25.preview', year=year))
    

@modelo25_bp.route('/report_pdf/<int:year>')
@login_required
def report_pdf(year):
    church = Church.query.get(current_user.church_id)
    donations = get_modelo25_data(current_user.church_id, year)
    valid_donations = [d for d in donations if d['tax_id'] and validate_tax_id(d['tax_id'], church.country)]
    
    filename = f"Modelo25_Oficial_{year}.pdf"
    filepath = os.path.join(current_app.root_path, 'static', 'uploads', 'receipts', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    generate_official_pdf(church, valid_donations, year, filepath)
    return send_file(filepath, as_attachment=True, download_name=filename)

def draw_box(c, x, y, w, h, text="", align="left", bold=False):
    c.rect(x, y, w, h)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", 8)
    if align == "center":
        c.drawCentredString(x + w/2, y + h/2 - 2, text)
    else:
        c.drawString(x + 5, y + h/2 - 2, text)

def generate_official_pdf(church, donations, year, output_path):
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    
    def draw_header():
        # Cabeçalho Superior
        c.setFont("Helvetica-Bold", 10)
        c.drawString(2*cm, height - 1.5*cm, "MINISTÉRIO DAS FINANÇAS")
        c.setFont("Helvetica", 8)
        c.drawString(2*cm, height - 1.9*cm, "AUTORIDADE TRIBUTÁRIA E ADUANEIRA")
        
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width/2, height - 2.5*cm, "DONATIVOS RECEBIDOS")
        
        c.setFont("Helvetica-Bold", 12)
        c.drawString(width - 5*cm, height - 1.5*cm, "IRS - IRC")
        c.setFont("Helvetica-Bold", 16)
        c.drawString(width - 5*cm, height - 2.5*cm, "MODELO 25")
        
        # Quadros de Identificação
        y = height - 4*cm
        draw_box(c, 2*cm, y, 6*cm, 1*cm, "1 - NIF DO DECLARANTE", bold=True)
        draw_box(c, 2*cm, y-0.6*cm, 6*cm, 0.6*cm, str(church.nif), align="center")
        
        draw_box(c, 8.5*cm, y, 3*cm, 1*cm, "2 - ANO", bold=True)
        draw_box(c, 8.5*cm, y-0.6*cm, 3*cm, 0.6*cm, str(year), align="center")
        
        draw_box(c, 12*cm, y, 7*cm, 1*cm, "4 - TIPO DE DECLARAÇÃO", bold=True)
        c.setFont("Helvetica", 8)
        c.drawString(12.5*cm, y-0.4*cm, "[X] Primeira")
        c.drawString(15.5*cm, y-0.4*cm, "[ ] Substituição")
        
        return y - 2*cm

    y = draw_header()
    
    # Tabela de Donativos
    c.setFont("Helvetica-Bold", 9)
    c.drawString(2*cm, y, "5 - RELAÇÃO DAS ENTIDADES DOADORAS E DOS DONATIVOS")
    y -= 0.5*cm
    
    # Cabeçalho da Tabela
    c.rect(2*cm, y-0.6*cm, 17*cm, 0.6*cm)
    c.drawString(2.5*cm, y-0.4*cm, "NIF DOADOR")
    c.drawString(8*cm, y-0.4*cm, "CÓDIGO")
    c.drawString(14*cm, y-0.4*cm, "VALOR DO DONATIVO")
    
    y -= 0.6*cm
    c.setFont("Helvetica", 9)
    total = 0
    
    for d in donations:
        if y < 4*cm:
            c.showPage()
            y = draw_header()
            y -= 1.1*cm # Ajuste para tabela na nova página
            
        c.rect(2*cm, y-0.6*cm, 17*cm, 0.6*cm)
        c.drawString(2.5*cm, y-0.4*cm, str(d['tax_id']))
        c.drawString(8.5*cm, y-0.4*cm, "01")
        c.drawRightString(18.5*cm, y-0.4*cm, f"{d['total_amount']:.2f}")
        total += d['total_amount']
        y -= 0.6*cm
        
    # Soma Final
    c.setFont("Helvetica-Bold", 10)
    c.rect(2*cm, y-0.8*cm, 17*cm, 0.8*cm)
    c.drawString(2.5*cm, y-0.5*cm, "SOMA")
    c.drawRightString(18.5*cm, y-0.5*cm, f"{total:.2f}")
    
    c.save()

@modelo25_bp.route('/comprovativo/<int:user_id>/<int:year>')
@login_required
def comprovativo(user_id, year):
    church, user = Church.query.get(current_user.church_id), User.query.get(user_id)
    start, end = datetime(year, 1, 1), datetime(year, 12, 31, 23, 59, 59)
    total = db.session.query(func.sum(Transaction.amount)).filter(Transaction.user_id == user_id, Transaction.church_id == current_user.church_id, Transaction.type == 'income', Transaction.date >= start, Transaction.date <= end).scalar() or 0
    
    filename = f"Comprovativo_{user.tax_id or user.id}_{year}.pdf"
    filepath = os.path.join(current_app.root_path, 'static', 'uploads', 'receipts', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    c = canvas.Canvas(filepath, pagesize=A4)
    c.setFont("Helvetica-Bold", 16); c.drawCentredString(A4[0]/2, A4[1]-3*cm, "COMPROVATIVO DE DONATIVO")
    c.setFont("Helvetica", 10); c.drawString(2*cm, A4[1]-5*cm, f"Entidade: {church.name} (NIF: {church.nif})")
    c.drawString(2*cm, A4[1]-6*cm, f"Doador: {user.name} (NIF: {user.tax_id})")
    c.setFont("Helvetica-Bold", 12); c.drawString(2*cm, A4[1]-8*cm, f"VALOR TOTAL EM {year}: € {total:.2f}")
    c.save()
    return send_file(filepath, as_attachment=True, download_name=filename)
