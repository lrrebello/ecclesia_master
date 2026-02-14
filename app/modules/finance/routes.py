from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, current_app
from flask_login import login_required, current_user
from app.core.models import Transaction, Asset, MaintenanceLog, db, User, Church
from app.utils.pdf_gen import generate_receipt
import os
from datetime import datetime, timedelta
from sqlalchemy import func

finance_bp = Blueprint('finance', __name__)

def is_admin():
    return current_user.church_role and current_user.church_role.name == 'Administrador Global'

def can_manage_finance():
    return current_user.can_manage_finance or (current_user.church_role and current_user.church_role.name in ['Administrador Global', 'Pastor Líder', 'Tesoureiro'])

@finance_bp.route('/dashboard')
@login_required
def dashboard():
    # Verifica permissões
    if not can_manage_finance():
        # Membros comuns veem apenas suas próprias transações
        transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
        return render_template('finance/dashboard.html', transactions=transactions, assets=[], stats=None)

    # Filtro por igreja
    if is_admin():
        query = Transaction.query
        asset_query = Asset.query
    else:
        query = Transaction.query.filter_by(church_id=current_user.church_id)
        asset_query = Asset.query.filter_by(church_id=current_user.church_id)

    transactions = query.order_by(Transaction.date.desc()).all()
    assets = asset_query.all()

    # Estatísticas Simples
    total_income = sum(t.amount for t in transactions if t.type == 'income')
    total_expense = sum(t.amount for t in transactions if t.type == 'expense')
    balance = total_income - total_expense

    stats = {
        'income': total_income,
        'expense': total_expense,
        'balance': balance
    }

    return render_template('finance/dashboard.html', transactions=transactions, assets=assets, stats=stats)

@finance_bp.route('/asset/add', methods=['GET', 'POST'])
@login_required
def add_asset():
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
        
    if request.method == 'POST':
        new_asset = Asset(
            name=request.form.get('name'),
            category=request.form.get('category'),
            identifier=request.form.get('identifier'),
            value=float(request.form.get('value') or 0),
            purchase_date=datetime.strptime(request.form.get('purchase_date'), '%Y-%m-%d').date() if request.form.get('purchase_date') else None,
            church_id=current_user.church_id
        )
        db.session.add(new_asset)
        db.session.commit()
        flash('Bem cadastrado no patrimônio!', 'success')
        return redirect(url_for('finance.dashboard'))
    
    return render_template('finance/add_asset.html')

@finance_bp.route('/asset/<int:id>/maintenance', methods=['GET', 'POST'])
@login_required
def add_maintenance(id):
    asset = Asset.query.get_or_404(id)
    
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
        
    if request.method == 'POST':
        log = MaintenanceLog(
            asset_id=asset.id,
            description=request.form.get('description'),
            cost=float(request.form.get('cost') or 0),
            type=request.form.get('type'),
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%d').date() if request.form.get('date') else datetime.utcnow().date()
        )
        # Registra também como despesa financeira
        tx = Transaction(
            type='expense',
            category=f'Manutenção: {asset.name}',
            amount=log.cost,
            description=log.description,
            church_id=current_user.church_id,
            date=datetime.combine(log.date, datetime.min.time())
        )
        db.session.add(log)
        db.session.add(tx)
        db.session.commit()
        flash('Manutenção registrada e lançada no financeiro!', 'success')
        return redirect(url_for('finance.dashboard'))
    
    return render_template('finance/add_maintenance.html', asset=asset)

@finance_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_transaction():
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
        
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        new_tx = Transaction(
            type=request.form.get('type'),
            category=request.form.get('category'),
            amount=float(request.form.get('amount') or 0),
            description=request.form.get('description'),
            user_id=int(user_id) if user_id and user_id != '' else None,
            church_id=current_user.church_id,
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%d') if request.form.get('date') else datetime.utcnow()
        )
        db.session.add(new_tx)
        db.session.commit()
        
        if new_tx.user_id:
            new_tx.receipt_path = generate_receipt(new_tx)
            db.session.commit()
            
        flash('Transação registrada com sucesso!', 'success')
        return redirect(url_for('finance.dashboard'))
        
    members = User.query.filter_by(church_id=current_user.church_id, status='active').all()
    today = datetime.utcnow().date().isoformat()
    return render_template('finance/add.html', members=members, today=today)

@finance_bp.route('/receipt/<int:tx_id>')
@login_required
def download_receipt(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    
    # Permissão: Admin, Tesoureiro ou o próprio dono do recibo
    if not can_manage_finance() and tx.user_id != current_user.id:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
        
    if not tx.receipt_path:
        tx.receipt_path = generate_receipt(tx)
        db.session.commit()
        
    return send_from_directory(
        os.path.join(current_app.config['UPLOAD_FOLDER'], 'receipts'),
        tx.receipt_path,
        as_attachment=True
    )

@finance_bp.route('/report')
@login_required
def report():
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))

    # Relatório simplificado por categoria (últimos 30 dias)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    if is_admin():
        results = db.session.query(
            Transaction.category, 
            Transaction.type, 
            func.sum(Transaction.amount)
        ).filter(Transaction.date >= thirty_days_ago).group_by(Transaction.category, Transaction.type).all()
    else:
        results = db.session.query(
            Transaction.category, 
            Transaction.type, 
            func.sum(Transaction.amount)
        ).filter(
            Transaction.church_id == current_user.church_id,
            Transaction.date >= thirty_days_ago
        ).group_by(Transaction.category, Transaction.type).all()

    return render_template('finance/report.html', results=results)
