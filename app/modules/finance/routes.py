from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, current_app, send_file
from flask_login import login_required, current_user
from app.core.models import (
    Transaction, Asset, MaintenanceLog, db, User, Church, Ministry,
    MinistryTransaction, TransactionCategory, PaymentMethod
)
from app.utils.pdf_gen import generate_receipt, generate_consolidated_receipt  # <-- IMPORT CORRETO AQUI
from sqlalchemy import or_, func
import os
from datetime import datetime, timedelta, date

finance_bp = Blueprint('finance', __name__)

def is_admin():
    return current_user.church_role and current_user.church_role.name == 'Administrador Global'

def can_manage_finance():
    if current_user.can_manage_finance:
        return True
    if not current_user.church_role:
        return False
    role = current_user.church_role
    return (
        role.name == 'Administrador Global' or
        role.is_lead_pastor or
        role.name == 'Tesoureiro'
    )

@finance_bp.route('/dashboard')
@login_required
def dashboard():
    if not can_manage_finance():
        return redirect(url_for('finance.member_finance'))
    
    # Filtros
    search = request.args.get('search')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    category_id = request.args.get('category_id')
    payment_method_id = request.args.get('payment_method_id')
    tx_type = request.args.get('type')

    if is_admin():
        query = Transaction.query
        asset_query = Asset.query
    else:
        query = Transaction.query.filter_by(church_id=current_user.church_id)
        asset_query = Asset.query.filter_by(church_id=current_user.church_id)

    # Aplicar filtros
    if search:
        query = query.join(User, Transaction.user_id == User.id, isouter=True).filter(or_(
            Transaction.description.ilike(f'%{search}%'),
            Transaction.category_name.ilike(f'%{search}%'),
            Transaction.payment_method_name.ilike(f'%{search}%'),
            User.name.ilike(f'%{search}%')
        ))
    if start_date:
        query = query.filter(Transaction.date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Transaction.date <= datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))
    if category_id:
        query = query.filter(Transaction.category_id == category_id)
    if payment_method_id:
        query = query.filter(Transaction.payment_method_id == payment_method_id)
    if tx_type:
        query = query.filter(Transaction.type == tx_type)

    transactions = query.order_by(Transaction.date.desc()).all()
    assets = asset_query.all()
    members = User.query.filter_by(church_id=current_user.church_id, status='active').order_by(User.name).all()
    categories = TransactionCategory.query.filter_by(church_id=current_user.church_id, is_active=True).all()
    payment_methods = PaymentMethod.query.filter_by(church_id=current_user.church_id, is_active=True).all()

    total_income = sum(t.amount for t in transactions if t.type == 'income')
    total_expense = sum(t.amount for t in transactions if t.type == 'expense')
    
    stats = {
        'income': total_income,
        'expense': total_expense,
        'balance': total_income - total_expense
    }
    
    return render_template('finance/dashboard.html', 
                           transactions=transactions, 
                           assets=assets, 
                           stats=stats, 
                           members=members,
                           categories=categories,
                           payment_methods=payment_methods,
                           filters={'search': search, 'start_date': start_date, 'end_date': end_date, 'category_id': category_id, 'payment_method_id': payment_method_id, 'type': tx_type})

@finance_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def manage_settings():
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
    
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        if form_type == 'category':
            name = request.form.get('name')
            type_ = request.form.get('type')  # evitei usar 'type' como variável
            if name and type_:
                new_cat = TransactionCategory(name=name, type=type_, church_id=current_user.church_id)
                db.session.add(new_cat)
                db.session.commit()
                flash('Categoria cadastrada com sucesso!', 'success')
        elif form_type == 'payment_method':
            name = request.form.get('name')
            is_electronic = 'is_electronic' in request.form
            if name:
                new_method = PaymentMethod(name=name, is_electronic=is_electronic, church_id=current_user.church_id)
                db.session.add(new_method)
                db.session.commit()
                flash('Meio de pagamento cadastrado com sucesso!', 'success')
        return redirect(url_for('finance.manage_settings'))
        
    categories = TransactionCategory.query.filter_by(church_id=current_user.church_id, is_active=True).all()
    payment_methods = PaymentMethod.query.filter_by(church_id=current_user.church_id, is_active=True).all()
    return render_template('finance/settings.html', categories=categories, payment_methods=payment_methods)

@finance_bp.route('/categories/delete/<int:id>', methods=['POST'])
@login_required
def delete_category(id):
    if not can_manage_finance():
        return redirect(url_for('finance.dashboard'))
    cat = TransactionCategory.query.get_or_404(id)
    if cat.church_id == current_user.church_id:
        cat.is_active = False
        db.session.commit()
        flash('Categoria desativada.', 'info')
    return redirect(url_for('finance.manage_settings'))

@finance_bp.route('/payment-methods/delete/<int:id>', methods=['POST'])
@login_required
def delete_payment_method(id):
    if not can_manage_finance():
        return redirect(url_for('finance.dashboard'))
    method = PaymentMethod.query.get_or_404(id)
    if method.church_id == current_user.church_id:
        method.is_active = False
        db.session.commit()
        flash('Meio de pagamento desativado.', 'info')
    return redirect(url_for('finance.manage_settings'))

@finance_bp.route('/my-contributions')
@login_required
def member_finance():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
    debts = MinistryTransaction.query.filter_by(debtor_id=current_user.id, is_paid=False).all()
    return render_template('finance/member_finance.html', transactions=transactions, debts=debts)

@finance_bp.route('/my-contributions/annual-receipt', methods=['GET', 'POST'])
@login_required
def annual_receipt():
    today = date.today()
    default_start = date(today.year, 1, 1)
    default_end = date(today.year, 12, 31)

    if request.method == 'POST':
        try:
            start_str = request.form.get('start_date')
            end_str = request.form.get('end_date')

            start_date = datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else default_start
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date() if end_str else default_end

            if start_date > end_date:
                flash('A data inicial não pode ser posterior à final.', 'danger')
                return redirect(request.url)

            transactions = Transaction.query.filter(
                Transaction.user_id == current_user.id,
                Transaction.date >= start_date,
                Transaction.date <= end_date
            ).order_by(Transaction.date.asc()).all()

            if not transactions:
                flash('Nenhuma contribuição encontrada no período selecionado.', 'warning')
                return redirect(request.url)

            filename = generate_consolidated_receipt(current_user, transactions, start_date, end_date)

            receipts_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'receipts')
            full_path = os.path.join(receipts_dir, filename)

            return send_file(
                full_path,
                as_attachment=True,
                download_name=filename,
                mimetype='application/pdf'
            )

        except ValueError as e:
            flash(f'Formato de data inválido: {str(e)}', 'danger')
            return redirect(request.url)
        except Exception as e:
            current_app.logger.error(f"Erro ao gerar recibo consolidado: {str(e)}")
            flash('Erro ao gerar o recibo. Tente novamente.', 'danger')
            return redirect(request.url)

    return render_template(
        'finance/annual_receipt_form.html',
        default_start=default_start.strftime('%Y-%m-%d'),
        default_end=default_end.strftime('%Y-%m-%d')
    )

@finance_bp.route('/ministry/<int:ministry_id>')
@login_required
def ministry_finance(ministry_id):
    ministry = Ministry.query.get_or_404(ministry_id)
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

@finance_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_transaction():
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
        
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        category_id = request.form.get('category_id')
        payment_method_id = request.form.get('payment_method_id')
        
        category = TransactionCategory.query.get(category_id) if category_id else None
        payment_method = PaymentMethod.query.get(payment_method_id) if payment_method_id else None
        
        if payment_method and payment_method.is_electronic and not user_id:
            flash('Para pagamentos eletrônicos, a identificação do membro é obrigatória para fins fiscais.', 'danger')
            return redirect(url_for('finance.add_transaction'))
            
        amount = float(request.form.get('amount') or 0)
        is_cash = payment_method and payment_method.name.lower() in ['dinheiro', 'numerário', 'cash']
        is_portugal = current_user.church and current_user.church.country.lower() == 'portugal'
        
        if is_portugal and is_cash and amount > 200:
            flash('Conforme o Artigo 63º do EBF (Portugal), donativos superiores a 200€ não podem ser efetuados em numerário.', 'danger')
            return redirect(url_for('finance.add_transaction'))

        new_tx = Transaction(
            type=request.form.get('type'),
            category_id=int(category_id) if category_id else None,
            category_name=category.name if category else "Geral",
            payment_method_id=int(payment_method_id) if payment_method_id else None,
            payment_method_name=payment_method.name if payment_method else "Dinheiro",
            amount=amount,
            description=request.form.get('description'),
            user_id=int(user_id) if user_id and user_id != '' else None,
            church_id=current_user.church_id,
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%d') if request.form.get('date') else datetime.utcnow()
        )
        db.session.add(new_tx)
        db.session.commit()
        flash('Lançamento registrado com sucesso!', 'success')
        return redirect(url_for('finance.dashboard'))
        
    members = User.query.filter_by(church_id=current_user.church_id, status='active').all()
    categories = TransactionCategory.query.filter_by(church_id=current_user.church_id, is_active=True).all()
    payment_methods = PaymentMethod.query.filter_by(church_id=current_user.church_id, is_active=True).all()
    today = datetime.utcnow().date().isoformat()
    return render_template('finance/add.html', members=members, categories=categories, payment_methods=payment_methods, today=today)

@finance_bp.route('/report')
@login_required
def report():
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date and end_date:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
    else:
        start = (datetime.utcnow() - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = datetime.utcnow() + timedelta(days=1)

    prev_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.date < start,
        Transaction.type == 'income'
    )
    prev_expense = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.date < start,
        Transaction.type == 'expense'
    )

    if not is_admin():
        prev_income = prev_income.filter(Transaction.church_id == current_user.church_id)
        prev_expense = prev_expense.filter(Transaction.church_id == current_user.church_id)

    initial_balance = (prev_income.scalar() or 0) - (prev_expense.scalar() or 0)

    query = db.session.query(
        Transaction.category_name, 
        Transaction.type, 
        func.sum(Transaction.amount)
    ).filter(Transaction.date >= start, Transaction.date <= end)

    if not is_admin():
        query = query.filter(Transaction.church_id == current_user.church_id)

    results = query.group_by(Transaction.category_name, Transaction.type).all()

    period_income = sum(amount for name, type_, amount in results if type_ == 'income')
    period_expense = sum(amount for name, type_, amount in results if type_ == 'expense')
    final_balance = initial_balance + period_income - period_expense

    stats = {
        'initial_balance': initial_balance,
        'period_income': period_income,
        'period_expense': period_expense,
        'final_balance': final_balance
    }

    return render_template('finance/report.html', 
                           results=results, 
                           start_date=start_date, 
                           end_date=end_date, 
                           stats=stats)

@finance_bp.route('/export-report')
@login_required
def export_report():
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    category_id = request.args.get('category_id')
    payment_method_id = request.args.get('payment_method_id')
    user_id = request.args.get('user_id')
    tx_type = request.args.get('type')
    
    if start_date and end_date:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
    else:
        start = datetime.utcnow() - timedelta(days=30)
        end = datetime.utcnow() + timedelta(days=1)

    if not is_admin():
        query = Transaction.query.filter(Transaction.church_id == current_user.church_id)
    else:
        query = Transaction.query
    
    query = query.filter(Transaction.date >= start, Transaction.date <= end)
    
    if category_id:
        query = query.filter(Transaction.category_id == category_id)
    if payment_method_id:
        query = query.filter(Transaction.payment_method_id == payment_method_id)
    if user_id:
        query = query.filter(Transaction.user_id == user_id)
    if tx_type:
        query = query.filter(Transaction.type == tx_type)
    
    transactions = query.order_by(Transaction.date.asc()).all()
    
    total_income = sum(t.amount for t in transactions if t.type == 'income')
    total_expense = sum(t.amount for t in transactions if t.type == 'expense')
    balance = total_income - total_expense
    
    report_data = {
        'transactions': transactions,
        'total_income': total_income,
        'total_expense': total_expense,
        'balance': balance,
        'start_date': start_date,
        'end_date': end_date,
        'church_name': current_user.church.name if current_user.church else 'Relatorio Financeiro',
        'generated_at': datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')
    }
    
    return render_template('finance/export_report.html', **report_data)

@finance_bp.route('/receipt/<int:tx_id>')
@login_required
def download_receipt(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    if not (can_manage_finance() or tx.user_id == current_user.id):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
    
    filename = generate_receipt(tx)
    
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads')
    if not os.path.isabs(upload_folder):
        upload_folder = os.path.join(current_app.root_path, 'static/uploads')
        
    receipts_dir = os.path.join(upload_folder, 'receipts')
    
    return send_from_directory(receipts_dir, filename, as_attachment=True)

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
        flash('Bem cadastrado!', 'success')
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
        db.session.add(log)
        db.session.commit()
        flash('Manutenção registrada!', 'success')
        return redirect(url_for('finance.dashboard'))
    return render_template('finance/add_maintenance.html', asset=asset)

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
        category_id = request.form.get('category_id')
        payment_method_id = request.form.get('payment_method_id')
        
        category = TransactionCategory.query.get(category_id) if category_id else None
        payment_method = PaymentMethod.query.get(payment_method_id) if payment_method_id else None
        
        new_tx = MinistryTransaction(
            ministry_id=ministry.id,
            type=request.form.get('type'),
            category_id=int(category_id) if category_id else None,
            category_name=category.name if category else "Geral",
            payment_method_id=int(payment_method_id) if payment_method_id else None,
            payment_method_name=payment_method.name if payment_method else "Dinheiro",
            amount=float(request.form.get('amount') or 0),
            description=request.form.get('description'),
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%d') if request.form.get('date') else datetime.utcnow(),
            is_debt=is_debt,
            debtor_id=int(debtor_id) if debtor_id and debtor_id != '' else None,
            is_paid=not is_debt
        )
        db.session.add(new_tx)
        db.session.commit()
        flash('Lançamento do ministério registrado!', 'success')
        return redirect(url_for('finance.ministry_finance', ministry_id=ministry.id))
        
    members = User.query.filter_by(church_id=current_user.church_id, status='active').all()
    categories = TransactionCategory.query.filter_by(church_id=current_user.church_id, is_active=True).all()
    payment_methods = PaymentMethod.query.filter_by(church_id=current_user.church_id, is_active=True).all()
    today = datetime.utcnow().date().isoformat()
    return render_template('finance/add_ministry_tx.html', ministry=ministry, members=members, categories=categories, payment_methods=payment_methods, today=today)