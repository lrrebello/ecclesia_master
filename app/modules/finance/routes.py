from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, current_app
from flask_login import login_required, current_user
from app.core.models import Transaction, Asset, MaintenanceLog, db, User, Church
from app.utils.pdf_gen import generate_receipt
import os

finance_bp = Blueprint('finance', __name__)

@finance_bp.route('/dashboard')
@login_required
def dashboard():
    # Admin vê tudo, outros veem apenas da sua filial
    if current_user.role == 'admin':
        transactions = Transaction.query.order_by(Transaction.date.desc()).all()
        assets = Asset.query.all()
    elif current_user.role in ['treasurer', 'pastor_leader']:
        transactions = Transaction.query.filter_by(church_id=current_user.church_id).order_by(Transaction.date.desc()).all()
        assets = Asset.query.filter_by(church_id=current_user.church_id).all()
    else:
        transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
        assets = []
    return render_template('finance/dashboard.html', transactions=transactions, assets=assets)

@finance_bp.route('/asset/add', methods=['GET', 'POST'])
@login_required
def add_asset():
    if current_user.role not in ['admin', 'treasurer']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
        
    if request.method == 'POST':
        new_asset = Asset(
            name=request.form.get('name'),
            category=request.form.get('category'),
            identifier=request.form.get('identifier'),
            value=float(request.form.get('value')),
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
    if current_user.role not in ['admin', 'treasurer']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
        
    if request.method == 'POST':
        log = MaintenanceLog(
            asset_id=asset.id,
            description=request.form.get('description'),
            cost=float(request.form.get('cost')),
            type=request.form.get('type')
        )
        # Também registra como uma despesa financeira
        tx = Transaction(
            type='expense',
            category=f'Manutenção: {asset.name}',
            amount=log.cost,
            description=log.description,
            church_id=current_user.church_id
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
    if current_user.role not in ['admin', 'treasurer']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
        
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        new_tx = Transaction(
            type=request.form.get('type'),
            category=request.form.get('category'),
            amount=float(request.form.get('amount')),
            description=request.form.get('description'),
            user_id=int(user_id) if user_id else None,
            church_id=current_user.church_id
        )
        db.session.add(new_tx)
        db.session.commit()
        
        if new_tx.user_id:
            from app.utils.pdf_gen import generate_receipt
            new_tx.receipt_path = generate_receipt(new_tx)
            db.session.commit()
            
        flash('Transação registrada com sucesso!', 'success')
        return redirect(url_for('finance.dashboard'))
        
    members = User.query.filter_by(church_id=current_user.church_id, status='active').all()
    return render_template('finance/add.html', members=members)

@finance_bp.route('/receipt/<int:tx_id>')
@login_required
def download_receipt(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    if current_user.role not in ['admin', 'treasurer'] and tx.user_id != current_user.id:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
        
    if not tx.receipt_path:
        from app.utils.pdf_gen import generate_receipt
        tx.receipt_path = generate_receipt(tx)
        db.session.commit()
        
    return send_from_directory(
        os.path.join(current_app.config['UPLOAD_FOLDER'], 'receipts'),
        tx.receipt_path,
        as_attachment=True
    )
