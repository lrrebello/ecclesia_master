from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, current_app
from flask_login import login_required, current_user
from app.core.models import Transaction, Asset, MaintenanceLog, db, User, Church, Ministry, MinistryTransaction
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
    # Se o usuário for tesoureiro/admin, vê o dashboard geral
    if can_manage_finance():
        if is_admin():
            query = Transaction.query
            asset_query = Asset.query
        else:
            query = Transaction.query.filter_by(church_id=current_user.church_id)
            asset_query = Asset.query.filter_by(church_id=current_user.church_id)

        transactions = query.order_by(Transaction.date.desc()).all()
        assets = asset_query.all()

        total_income = sum(t.amount for t in transactions if t.type == 'income')
        total_expense = sum(t.amount for t in transactions if t.type == 'expense')
        balance = total_income - total_expense

        stats = {
            'income': total_income,
            'expense': total_expense,
            'balance': balance
        }
        return render_template('finance/dashboard.html', transactions=transactions, assets=assets, stats=stats)
    
    # Se não for tesoureiro, redireciona para o painel de membro (onde ele vê seus recibos)
    return redirect(url_for('finance.member_finance'))

@finance_bp.route('/my-contributions')
@login_required
def member_finance():
    # Painel onde o membro vê seus próprios dízimos e ofertas
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
    debts = MinistryTransaction.query.filter_by(debtor_id=current_user.id, is_paid=False).all()
    return render_template('finance/member_finance.html', transactions=transactions, debts=debts)

@finance_bp.route('/ministry/<int:ministry_id>')
@login_required
def ministry_finance(ministry_id):
    ministry = Ministry.query.get_or_404(ministry_id)
    
    # Permissão: Líder do ministério, Tesoureiro ou Admin
    is_leader = ministry.leader_id == current_user.id
    if not (is_leader or can_manage_finance()):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    transactions = MinistryTransaction.query.filter_by(ministry_id=ministry_id).order_by(MinistryTransaction.date.desc()).all()
    
    income = sum(t.amount for t in transactions if t.type == 'income' and t.is_paid)
    expense = sum(t.amount for t in transactions if t.type == 'expense')
    debts = sum(t.amount for t in transactions if t.is_debt and not t.is_paid)
    
    stats = {
        'income': income,
        'expense': expense,
        'balance': income - expense,
        'pending_debts': debts
    }
    
    return render_template('finance/ministry_finance.html', ministry=ministry, transactions=transactions, stats=stats)

@finance_bp.route('/ministry/<int:ministry_id>/add', methods=['GET', 'POST'])
@login_required
def add_ministry_transaction(ministry_id):
    ministry = Ministry.query.get_or_404(ministry_id)
    is_leader = ministry.leader_id == current_user.id
    if not (is_leader or can_manage_finance()):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
        
    if request.method == 'POST':
        is_debt = 'is_debt' in request.form
        debtor_id = request.form.get('debtor_id')
        
        new_tx = MinistryTransaction(
            ministry_id=ministry.id,
            type=request.form.get('type'),
            category=request.form.get('category'),
            amount=float(request.form.get('amount') or 0),
            description=request.form.get('description'),
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%d') if request.form.get('date') else datetime.utcnow(),
            is_debt=is_debt,
            debtor_id=int(debtor_id) if debtor_id and debtor_id != '' else None,
            is_paid=not is_debt # Se for débito, começa como não pago
        )
        db.session.add(new_tx)
        db.session.commit()
        flash('Lançamento do ministério registrado!', 'success')
        return redirect(url_for('finance.ministry_finance', ministry_id=ministry.id))
        
    members = User.query.filter_by(church_id=current_user.church_id, status='active').all()
    today = datetime.utcnow().date().isoformat()
    return render_template('finance/add_ministry_tx.html', ministry=ministry, members=members, today=today)

@finance_bp.route('/ministry/debt/pay/<int:tx_id>')
@login_required
def pay_debt(tx_id):
    tx = MinistryTransaction.query.get_or_404(tx_id)
    ministry = Ministry.query.get(tx.ministry_id)
    
    if not (ministry.leader_id == current_user.id or can_manage_finance()):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
        
    tx.is_paid = True
    db.session.commit()
    flash('Débito marcado como pago!', 'success')
    return redirect(url_for('finance.ministry_finance', ministry_id=tx.ministry_id))

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
    if not can_manage_finance() and tx.user_id != current_user.id:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
        
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
