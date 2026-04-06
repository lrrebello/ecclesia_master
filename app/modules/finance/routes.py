from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, jsonify, current_app, send_file
from flask_login import login_required, current_user
from app.core.models import (
    Transaction, Asset, MaintenanceLog, db, User, Church, Ministry,
    MinistryTransaction, TransactionCategory, PaymentMethod, SystemLog,
    BankAccount, MBWay, MinistryCategory, MinistryPaymentMethod, Supplier, Bill
)
from app.utils.pdf_gen import generate_receipt, generate_consolidated_receipt
from app.utils.logger import log_action  # <-- IMPORT DO LOGGER
from sqlalchemy import or_, func
import os
from datetime import datetime, timedelta, date

import re

def validar_iban(iban):
    """Valida e formata IBAN português"""
    if not iban:
        return True, None
    
    # Remove espaços e converte para maiúsculas
    iban = re.sub(r'\s+', '', iban).upper()
    
    # IBAN português tem 25 caracteres (PT + 23 dígitos)
    if not re.match(r'^PT\d{23}$', iban):
        return False, "IBAN português deve começar com 'PT' seguido de 23 dígitos (25 caracteres no total)"
    
    return True, iban


def validar_telefone_portugal(telefone):
    """Valida e formata telefone português"""
    if not telefone:
        return True, None
    
    # Remove espaços, traços e outros caracteres
    telefone = re.sub(r'[\s\-\(\)]', '', telefone)
    
    # Se começar com +351, mantém
    if telefone.startswith('+351'):
        numero = telefone[4:]
        if len(numero) == 9 and numero.isdigit():
            return True, telefone
    # Se começar com 00351
    elif telefone.startswith('00351'):
        numero = telefone[5:]
        if len(numero) == 9 and numero.isdigit():
            return True, '+351' + numero
    # Se for número nacional (9 dígitos)
    elif len(telefone) == 9 and telefone.isdigit():
        return True, '+351' + telefone
    # Se for número com 9 dígitos começando com 9 (telemóvel)
    elif len(telefone) == 9 and telefone.isdigit() and telefone[0] == '9':
        return True, '+351' + telefone
    
    # Mensagem mais amigável
    return False, "Telefone deve ter 9 dígitos (ex: 910000000 ou +351 910 000 000)"

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

def is_ministry_leader(ministry):
    """Verifica se o usuário atual é líder, vice-líder ou está na lista extra do ministério"""
    if not current_user.is_authenticated:
        return False
    
    # Verifica líder e vice (existentes)
    if ministry.leader_id == current_user.id or ministry.vice_leader_id == current_user.id:
        return True
    
    # Verifica na lista extra
    if ministry.extra_leaders and current_user.id in ministry.extra_leaders:
        return True
    
    return False

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
    
    # ========== CONTAS A PAGAR (Próximos 30 dias) ==========
    from app.core.models import Bill
    from sqlalchemy import func
    
    today = datetime.now().date()
    next_month = today + timedelta(days=30)
    
    # Total pendente (valor restante) das contas com vencimento nos próximos 30 dias
    bills_pending = db.session.query(
        func.sum(Bill.amount - Bill.amount_paid)
    ).filter(
        Bill.church_id == current_user.church_id,
        Bill.status != 'paid',
        Bill.due_date <= next_month
    ).scalar() or 0
    
    # Contas vencidas (para exibir alerta)
    overdue_bills = db.session.query(
        func.count(Bill.id)
    ).filter(
        Bill.church_id == current_user.church_id,
        Bill.status != 'paid',
        Bill.due_date < today
    ).scalar() or 0
    
    stats = {
        'income': total_income,
        'expense': total_expense,
        'balance': total_income - total_expense,
        'bills_pending': bills_pending,
        'overdue_bills': overdue_bills  # 🔥 Contas vencidas
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
            type_ = request.form.get('type')
            if name and type_:
                new_cat = TransactionCategory(
                    name=name, 
                    type=type_, 
                    church_id=current_user.church_id,
                    is_active=True
                )
                db.session.add(new_cat)
                db.session.commit()
                
                # LOG: Criação de categoria
                log_action(
                    action='CREATE',
                    module='FINANCE',
                    description=f"Nova categoria {type_}: {name}",
                    new_values={
                        'id': new_cat.id,
                        'name': name,
                        'type': type_,
                        'church_id': current_user.church_id
                    },
                    church_id=current_user.church_id
                )
                flash('Categoria cadastrada com sucesso!', 'success')
                
        elif form_type == 'payment_method':
            name = request.form.get('name')
            is_electronic = 'is_electronic' in request.form
            if name:
                new_method = PaymentMethod(
                    name=name, 
                    is_electronic=is_electronic, 
                    church_id=current_user.church_id,
                    is_active=True
                )
                db.session.add(new_method)
                db.session.commit()
                
                # LOG: Criação de método de pagamento
                log_action(
                    action='CREATE',
                    module='FINANCE',
                    description=f"Novo método de pagamento: {name} {'(eletrônico)' if is_electronic else ''}",
                    new_values={
                        'id': new_method.id,
                        'name': name,
                        'is_electronic': is_electronic,
                        'church_id': current_user.church_id
                    },
                    church_id=current_user.church_id
                )
                flash('Meio de pagamento cadastrado com sucesso!', 'success')
                
        return redirect(url_for('finance.manage_settings'))
        
    categories = TransactionCategory.query.filter_by(church_id=current_user.church_id, is_active=True).all()
    payment_methods = PaymentMethod.query.filter_by(church_id=current_user.church_id, is_active=True).all()
    return render_template('finance/settings.html', categories=categories, payment_methods=payment_methods)

@finance_bp.route('/categories/edit/<int:id>', methods=['POST'])
@login_required
def edit_category(id):
    """Editar categoria (nome, tipo ou requires_linked_entity)"""
    if not can_manage_finance():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    category = TransactionCategory.query.get_or_404(id)
    if category.church_id != current_user.church_id:
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    old_values = {
        'name': category.name,
        'type': category.type,
        'is_active': category.is_active,
        'requires_linked_entity': category.requires_linked_entity
    }
    
    category.name = request.form.get('name', category.name)
    category.type = request.form.get('type', category.type)
    category.requires_linked_entity = 'requires_linked_entity' in request.form
    
    try:
        db.session.commit()
        
        log_action(
            action='UPDATE',
            module='FINANCE',
            description=f"Categoria editada: {category.name}",
            old_values=old_values,
            new_values={
                'name': category.name,
                'type': category.type,
                'is_active': category.is_active,
                'requires_linked_entity': category.requires_linked_entity
            },
            church_id=category.church_id
        )
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@finance_bp.route('/categories/delete/<int:id>', methods=['POST'])
@login_required
def delete_category(id):
    if not can_manage_finance():
        return redirect(url_for('finance.dashboard'))
    
    cat = TransactionCategory.query.get_or_404(id)
    if cat.church_id == current_user.church_id:
        old_status = cat.is_active
        old_values = {
            'id': cat.id,
            'name': cat.name,
            'type': cat.type,
            'is_active': old_status
        }
        
        cat.is_active = False
        db.session.commit()
        
        # LOG: Desativação de categoria
        log_action(
            action='UPDATE',
            module='FINANCE',
            description=f"Categoria desativada: {cat.name}",
            old_values=old_values,
            new_values={'is_active': False},
            church_id=cat.church_id
        )
        flash('Categoria desativada.', 'info')
        
    return redirect(url_for('finance.manage_settings'))

@finance_bp.route('/categories/reactivate/<int:id>', methods=['POST'])
@login_required
def reactivate_category(id):
    """Reativar categoria"""
    if not can_manage_finance():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    cat = TransactionCategory.query.get_or_404(id)
    if cat.church_id != current_user.church_id:
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    old_status = cat.is_active
    cat.is_active = True
    
    try:
        db.session.commit()
        
        # LOG: Reativação de categoria
        log_action(
            action='UPDATE',
            module='FINANCE',
            description=f"Categoria reativada: {cat.name}",
            old_values={'is_active': old_status},
            new_values={'is_active': True},
            church_id=cat.church_id
        )
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@finance_bp.route('/payment-methods/edit/<int:id>', methods=['POST'])
@login_required
def edit_payment_method(id):
    """Editar método de pagamento"""
    if not can_manage_finance():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    method = PaymentMethod.query.get_or_404(id)
    if method.church_id != current_user.church_id:
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    old_values = {
        'name': method.name,
        'is_electronic': method.is_electronic,
        'is_active': method.is_active
    }
    
    method.name = request.form.get('name', method.name)
    method.is_electronic = 'is_electronic' in request.form
    
    try:
        db.session.commit()
        
        # LOG: Edição de método de pagamento
        log_action(
            action='UPDATE',
            module='FINANCE',
            description=f"Método de pagamento editado: {method.name}",
            old_values=old_values,
            new_values={
                'name': method.name,
                'is_electronic': method.is_electronic,
                'is_active': method.is_active
            },
            church_id=method.church_id
        )
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@finance_bp.route('/payment-methods/delete/<int:id>', methods=['POST'])
@login_required
def delete_payment_method(id):
    if not can_manage_finance():
        return redirect(url_for('finance.dashboard'))
    
    method = PaymentMethod.query.get_or_404(id)
    if method.church_id == current_user.church_id:
        old_status = method.is_active
        old_values = {
            'id': method.id,
            'name': method.name,
            'is_electronic': method.is_electronic,
            'is_active': old_status
        }
        
        method.is_active = False
        db.session.commit()
        
        # LOG: Desativação de método de pagamento
        log_action(
            action='UPDATE',
            module='FINANCE',
            description=f"Método de pagamento desativado: {method.name}",
            old_values=old_values,
            new_values={'is_active': False},
            church_id=method.church_id
        )
        flash('Meio de pagamento desativado.', 'info')
        
    return redirect(url_for('finance.manage_settings'))

@finance_bp.route('/payment-methods/reactivate/<int:id>', methods=['POST'])
@login_required
def reactivate_payment_method(id):
    """Reativar método de pagamento"""
    if not can_manage_finance():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    method = PaymentMethod.query.get_or_404(id)
    if method.church_id != current_user.church_id:
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    old_status = method.is_active
    method.is_active = True
    
    try:
        db.session.commit()
        
        # LOG: Reativação de método de pagamento
        log_action(
            action='UPDATE',
            module='FINANCE',
            description=f"Método de pagamento reativado: {method.name}",
            old_values={'is_active': old_status},
            new_values={'is_active': True},
            church_id=method.church_id
        )
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

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
    is_leader = is_ministry_leader(ministry)
    if not (is_leader or can_manage_finance()):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    # Busca todas as transações
    transactions = MinistryTransaction.query.filter_by(ministry_id=ministry_id).order_by(MinistryTransaction.date.desc()).all()
    
    income = 0
    expense = 0
    debts = 0
    
    for tx in transactions:
        # Verifica PRIMEIRO ministry_category_id (categorias personalizadas), DEPOIS category_id (categorias gerais)
        if tx.ministry_category_id:
            category = MinistryCategory.query.get(tx.ministry_category_id)
            if category:
                tx.category_name = category.name
            else:
                tx.category_name = "Sem categoria"
        elif tx.category_id:
            category = TransactionCategory.query.get(tx.category_id)
            if category:
                tx.category_name = category.name
            else:
                tx.category_name = "Sem categoria"
        else:
            tx.category_name = "Sem categoria"
        
        # Calcula os stats
        if tx.type == 'income' and tx.is_paid:
            income += tx.amount
        elif tx.type == 'expense':
            expense += tx.amount
        
        if tx.is_debt and not tx.is_paid:
            debts += tx.amount
    
    stats = {
        'income': income,
        'expense': expense,
        'balance': income - expense,
        'pending_debts': debts
    }
    
    return render_template(
        'finance/ministry_finance.html', 
        ministry=ministry, 
        transactions=transactions, 
        stats=stats
    )

@finance_bp.route('/ministry/transaction/delete/<int:tx_id>', methods=['POST'])
@login_required
def delete_ministry_transaction(tx_id):
    """Excluir uma transação do ministério"""
    from app.core.models import MinistryTransaction, Ministry
    
    tx = MinistryTransaction.query.get_or_404(tx_id)
    ministry = Ministry.query.get(tx.ministry_id)
    
    # Verificar permissão
    is_leader = is_ministry_leader(ministry)
    if not (is_leader or can_manage_finance()):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    # Guardar dados para o log
    tx_data = {
        'id': tx.id,
        'type': tx.type,
        'amount': tx.amount,
        'description': tx.description,
        'ministry_id': tx.ministry_id
    }
    
    try:
        db.session.delete(tx)
        db.session.commit()
        
        # LOG: Exclusão de transação
        log_action(
            action='DELETE',
            module='MINISTRY_FINANCE',
            description=f"Exclusão de lançamento do ministério {ministry.name}: {tx.description or 'Sem descrição'} (R$ {tx.amount})",
            old_values=tx_data,
            church_id=ministry.church_id
        )
        
        flash('Lançamento excluído com sucesso!', 'success')
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao excluir transação de ministério {tx_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Erro ao excluir. Tente novamente.'}), 500

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
        bank_account_id = request.form.get('bank_account_id')
        transaction_type = request.form.get('type')  # 🔥 PEGAR O TIPO
        
        category = TransactionCategory.query.get(category_id) if category_id else None
        payment_method = PaymentMethod.query.get(payment_method_id) if payment_method_id else None
        
        # 🔥 NOVA VALIDAÇÃO: Verifica se a categoria exige vínculo
        if category and category.requires_linked_entity and not user_id:
            flash(f'A categoria "{category.name}" exige a identificação do membro vinculado para fins fiscais.', 'danger')
            return redirect(url_for('finance.add_transaction'))
        
        # Validação para meios eletrônicos (mantida)
        if payment_method and payment_method.is_electronic and not user_id:
            flash('Para pagamentos eletrônicos, a identificação do membro é obrigatória para fins fiscais.', 'danger')
            return redirect(url_for('finance.add_transaction'))
            
        amount = float(request.form.get('amount') or 0)
        is_cash = payment_method and payment_method.name.lower() in ['dinheiro', 'numerário', 'cash']
        is_portugal = current_user.church and current_user.church.country.lower() == 'portugal'
        
        if is_portugal and is_cash and amount > 200 and transaction_type == 'income':
            flash('Conforme o Artigo 63º do EBF (Portugal), donativos superiores a 200€ não podem ser efetuados em numerário.', 'danger')
            return redirect(url_for('finance.add_transaction'))

        # Busca informações da conta bancária para o log
        bank_account = None
        bank_account_info = ""
        if bank_account_id:
            bank_account = BankAccount.query.get(bank_account_id)
            if bank_account:
                bank_account_info = f" | Conta: {bank_account.bank_name} - {bank_account.account_number}"
            else:
                bank_account_info = " | Conta não encontrada"
        else:
            bank_account_info = " | Sem vínculo bancário"

        new_tx = Transaction(
            type=request.form.get('type'),
            category_id=int(category_id) if category_id else None,
            category_name=category.name if category else "Geral",
            payment_method_id=int(payment_method_id) if payment_method_id else None,
            payment_method_name=payment_method.name if payment_method else "Dinheiro",
            bank_account_id=int(bank_account_id) if bank_account_id else None,
            amount=amount,
            description=request.form.get('description'),
            user_id=int(user_id) if user_id and user_id != '' else None,
            church_id=current_user.church_id,
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%d') if request.form.get('date') else datetime.utcnow()
        )
        db.session.add(new_tx)
        db.session.commit()
        
        # LOG: Criação de transação com informação da conta
        log_action(
            action='CREATE',
            module='FINANCE',
            description=f"Novo lançamento: {new_tx.description or 'Sem descrição'} ({current_user.church.currency_symbol or 'R$'} {new_tx.amount:.2f}){bank_account_info}",
            new_values={
                'id': new_tx.id,
                'type': new_tx.type,
                'amount': float(new_tx.amount),
                'description': new_tx.description,
                'category': new_tx.category_name,
                'payment_method': new_tx.payment_method_name,
                'user_id': new_tx.user_id,
                'bank_account_id': new_tx.bank_account_id,
                'bank_account_name': bank_account.bank_name if bank_account else None
            },
            church_id=current_user.church_id
        )
        
        flash('Lançamento registrado com sucesso!', 'success')
        return redirect(url_for('finance.dashboard'))
        
    # GET - buscar dados para o formulário
    members = User.query.filter_by(church_id=current_user.church_id, status='active').all()
    categories = TransactionCategory.query.filter_by(church_id=current_user.church_id, is_active=True).all()
    payment_methods = PaymentMethod.query.filter_by(church_id=current_user.church_id, is_active=True).all()
    
    # Buscar contas bancárias disponíveis
    church_bank_accounts = BankAccount.query.filter_by(
        church_id=current_user.church_id,
        ministry_id=None,
        is_active=True
    ).all()
    
    # Contas de ministérios (se tiver permissão)
    ministry_bank_accounts = []
    if can_manage_finance():
        ministries = Ministry.query.filter_by(church_id=current_user.church_id).all()
        for ministry in ministries:
            if is_admin() or ministry.leader_id == current_user.id:
                accounts = BankAccount.query.filter_by(
                    ministry_id=ministry.id,
                    is_active=True
                ).all()
                ministry_bank_accounts.extend(accounts)
    
    today = datetime.utcnow().date().isoformat()
    
    return render_template('finance/add.html', 
                           members=members, 
                           categories=categories, 
                           payment_methods=payment_methods,
                           church_bank_accounts=church_bank_accounts,
                           ministry_bank_accounts=ministry_bank_accounts,
                           today=today)

@finance_bp.route('/transaction/edit/<int:id>', methods=['POST'])
@login_required
def edit_transaction(id):
    """Editar uma transação existente"""
    if not can_manage_finance():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    transaction = Transaction.query.get_or_404(id)
    
    # Verificar permissão
    if not is_admin() and transaction.church_id != current_user.church_id:
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    # Guardar valores antigos
    old_values = {
        'type': transaction.type,
        'amount': transaction.amount,
        'description': transaction.description,
        'category_id': transaction.category_id,
        'category_name': transaction.category_name,
        'payment_method_id': transaction.payment_method_id,
        'payment_method_name': transaction.payment_method_name,
        'user_id': transaction.user_id,
        'bank_account_id': transaction.bank_account_id,
        'date': transaction.date.strftime('%Y-%m-%d') if transaction.date else None
    }
    
    # Obter novos valores do formulário
    new_type = request.form.get('type', transaction.type)
    new_category_id = request.form.get('category_id')
    new_payment_method_id = request.form.get('payment_method_id')
    new_user_id = request.form.get('user_id')
    new_bank_account_id = request.form.get('bank_account_id')
    
    # Buscar a nova categoria selecionada
    new_category = None
    if new_category_id:
        new_category = TransactionCategory.query.get(int(new_category_id))
    
    # Buscar o método de pagamento
    payment_method = None
    if new_payment_method_id:
        payment_method = PaymentMethod.query.get(int(new_payment_method_id))
    
    # 🔥 VALIDAÇÃO: Verificar se a nova categoria exige vínculo
    if new_category and new_category.requires_linked_entity and not new_user_id:
        return jsonify({
            'success': False, 
            'message': f'A categoria "{new_category.name}" exige a identificação do membro vinculado para fins fiscais.'
        }), 400
    
    # 🔥 VALIDAÇÃO: Meios eletrônicos exigem vínculo
    if payment_method and payment_method.is_electronic and not new_user_id:
        return jsonify({
            'success': False, 
            'message': 'Para pagamentos eletrônicos, a identificação do membro é obrigatória para fins fiscais.'
        }), 400
    
    # Validar limite de dinheiro em Portugal (se aplicável)
    amount = float(request.form.get('amount', transaction.amount))
    is_cash = payment_method and payment_method.name.lower() in ['dinheiro', 'numerário', 'cash']
    is_portugal = current_user.church and current_user.church.country.lower() == 'portugal'
    
    if is_portugal and is_cash and amount > 200 and new_type == 'income':
        flash('Conforme o Artigo 63º do EBF (Portugal), donativos superiores a 200€ não podem ser efetuados em numerário.', 'danger')
        return redirect(url_for('finance.add_transaction'))
    
    # Atualizar valores
    transaction.type = new_type
    transaction.amount = amount
    transaction.description = request.form.get('description', transaction.description)
    transaction.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d') if request.form.get('date') else transaction.date
    
    # Atualizar categoria
    if new_category_id:
        category = TransactionCategory.query.get(int(new_category_id))
        if category:
            transaction.category_id = category.id
            transaction.category_name = category.name
    else:
        transaction.category_id = None
        transaction.category_name = "Geral"
    
    # Atualizar método de pagamento
    if new_payment_method_id:
        pm = PaymentMethod.query.get(int(new_payment_method_id))
        if pm:
            transaction.payment_method_id = pm.id
            transaction.payment_method_name = pm.name
    else:
        transaction.payment_method_id = None
        transaction.payment_method_name = "Dinheiro"
    
    # Atualizar membro vinculado
    transaction.user_id = int(new_user_id) if new_user_id and new_user_id != '' else None
    
    # Atualizar conta bancária
    transaction.bank_account_id = int(new_bank_account_id) if new_bank_account_id else None
    
    # Buscar informações da conta para o log
    bank_account = None
    bank_account_info = ""
    if transaction.bank_account_id:
        bank_account = BankAccount.query.get(transaction.bank_account_id)
        if bank_account:
            bank_account_info = f" | Conta: {bank_account.bank_name} - {bank_account.account_number}"
    else:
        bank_account_info = " | Sem vínculo bancário"
    
    try:
        db.session.commit()
        
        # LOG: Edição de transação
        log_action(
            action='UPDATE',
            module='FINANCE',
            description=f"Lançamento editado: {transaction.description or 'Sem descrição'}{bank_account_info}",
            old_values=old_values,
            new_values={
                'type': transaction.type,
                'amount': float(transaction.amount),
                'description': transaction.description,
                'category': transaction.category_name,
                'payment_method': transaction.payment_method_name,
                'user_id': transaction.user_id,
                'bank_account_id': transaction.bank_account_id,
                'bank_account_name': bank_account.bank_name if bank_account else None,
                'date': transaction.date.strftime('%Y-%m-%d') if transaction.date else None
            },
            church_id=transaction.church_id
        )
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@finance_bp.route('/transaction/delete/<int:id>', methods=['POST'])
@login_required
def delete_transaction(id):
    """Exclui um lançamento financeiro (apenas para usuários com permissão)."""
    if not can_manage_finance():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403

    transaction = Transaction.query.get_or_404(id)

    # Verificar permissão específica para a igreja
    if not is_admin() and transaction.church_id != current_user.church_id:
        return jsonify({'success': False, 'message': 'Acesso negado a este lançamento.'}), 403

    # Guardar dados antes de excluir para o log
    tx_data = {
        'id': transaction.id,
        'type': transaction.type,
        'amount': transaction.amount,
        'description': transaction.description,
        'category': transaction.category_name,
        'payment_method': transaction.payment_method_name,
        'user_id': transaction.user_id,
        'date': transaction.date.strftime('%d/%m/%Y') if transaction.date else None,
        'bill_id': transaction.bill_id
    }
    
    # 🔥 SE FOR VINCULADO A UMA CONTA (BILL), REVERTER O PAGAMENTO
    linked_bill = transaction.bill
    bill_updated = False
    
    if linked_bill:
        from decimal import Decimal
        
        # Reverter o pagamento (subtrair o valor da transação)
        linked_bill.amount_paid = max(Decimal('0'), linked_bill.amount_paid - Decimal(str(transaction.amount)))
        
        # Atualizar status da conta
        if linked_bill.amount_paid == 0:
            linked_bill.status = 'pending'
            linked_bill.payment_date = None
        elif linked_bill.amount_paid < linked_bill.amount:
            linked_bill.status = 'partial'
        else:
            linked_bill.status = 'paid'
        
        bill_updated = True

    try:
        db.session.delete(transaction)
        db.session.commit()
        
        # LOG: Exclusão de transação (sem flash para não interferir no JSON)
        if bill_updated:
            log_action(
                action='DELETE',
                module='FINANCE',
                description=f"Exclusão de lançamento: {transaction.description} (R$ {transaction.amount}) - Conta #{linked_bill.id} ajustada",
                old_values=tx_data,
                church_id=transaction.church_id
            )
        else:
            log_action(
                action='DELETE',
                module='FINANCE',
                description=f"Exclusão de lançamento: {transaction.description} (R$ {transaction.amount})",
                old_values=tx_data,
                church_id=transaction.church_id
            )
        
        # Retornar JSON puro sem flash
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao excluir transação {id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Erro ao excluir. Tente novamente.'}), 500
    
    
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
        
        # LOG: Criação de bem
        log_action(
            action='CREATE',
            module='ASSET',
            description=f"Novo bem cadastrado: {new_asset.name} (R$ {new_asset.value})",
            new_values={
                'id': new_asset.id,
                'name': new_asset.name,
                'category': new_asset.category,
                'value': new_asset.value
            },
            church_id=current_user.church_id
        )
        
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
        
        # LOG: Registro de manutenção
        log_action(
            action='CREATE',
            module='MAINTENANCE',
            description=f"Manutenção registrada para {asset.name}: {log.description} (R$ {log.cost})",
            new_values={
                'id': log.id,
                'asset_id': asset.id,
                'asset_name': asset.name,
                'description': log.description,
                'cost': log.cost,
                'type': log.type
            },
            church_id=asset.church_id
        )
        
        flash('Manutenção registrada!', 'success')
        return redirect(url_for('finance.dashboard'))
    return render_template('finance/add_maintenance.html', asset=asset)

@finance_bp.route('/ministry/debt/pay/<int:tx_id>', methods=['GET'])
@login_required
def pay_debt(tx_id):
    """Marcar uma dívida do ministério como paga"""
    from app.core.models import MinistryTransaction, Ministry
    from app.utils.logger import log_action
    
    tx = MinistryTransaction.query.get_or_404(tx_id)
    ministry = Ministry.query.get(tx.ministry_id)
    
    # Verificar permissão
    is_leader = is_ministry_leader(ministry)
    if not (is_leader or can_manage_finance()):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    if not tx.is_debt:
        flash('Esta transação não é uma dívida.', 'warning')
        return redirect(url_for('finance.ministry_finance', ministry_id=ministry.id))
    
    old_values = {'is_paid': tx.is_paid}
    tx.is_paid = True
    
    try:
        db.session.commit()
        
        # Log da ação
        log_action(
            action='UPDATE',
            module='MINISTRY_FINANCE',
            description=f"Dívida paga: {tx.description} (R$ {tx.amount})",
            old_values=old_values,
            new_values={'is_paid': True},
            church_id=ministry.church_id
        )
        
        flash('Dívida marcada como paga!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao processar pagamento: {str(e)}', 'danger')
        current_app.logger.error(f"Erro ao pagar dívida {tx_id}: {str(e)}")
    
    return redirect(url_for('finance.ministry_finance', ministry_id=ministry.id))

# ==================== ROTAS PARA CONTAS BANCÁRIAS ====================

@finance_bp.route('/bank-accounts')
@login_required
def list_bank_accounts():
    """Listar contas bancárias da igreja"""
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
    
    church_accounts = BankAccount.query.filter_by(
        church_id=current_user.church_id, 
        ministry_id=None
    ).all()
    
    # Contas de ministérios (se for líder ou admin)
    ministry_accounts = []
    if can_manage_finance():
        ministries = Ministry.query.filter_by(church_id=current_user.church_id).all()
        for ministry in ministries:
            if is_admin() or ministry.leader_id == current_user.id:
                accounts = BankAccount.query.filter_by(ministry_id=ministry.id).all()
                ministry_accounts.extend(accounts)
    
    return render_template('finance/bank_accounts.html', 
                           church_accounts=church_accounts,
                           ministry_accounts=ministry_accounts)


@finance_bp.route('/bank-account/add', methods=['GET', 'POST'])
@login_required
def add_bank_account():
    """Adicionar nova conta bancária"""
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
    
    if request.method == 'POST':
        ministry_id = request.form.get('ministry_id')
        
        # Verificar permissão para conta de ministério
        if ministry_id:
            ministry = Ministry.query.get(ministry_id)
            if not (is_admin() or (ministry and ministry.leader_id == current_user.id)):
                flash('Acesso negado a este ministério.', 'danger')
                return redirect(url_for('finance.list_bank_accounts'))
        
        # Coletar dados
        bank_name = request.form.get('bank_name', '').strip()
        account_number = request.form.get('account_number', '').strip()
        iban = request.form.get('iban', '').strip()
        mbway_phone = request.form.get('mbway_phone', '').strip()
        
        # Validações básicas
        if not bank_name:
            flash('Nome do banco é obrigatório.', 'danger')
            return redirect(request.url)
        
        if not account_number:
            flash('Número da conta é obrigatório.', 'danger')
            return redirect(request.url)
        
        # Validar IBAN se fornecido
        if iban:
            valido, resultado = validar_iban(iban)
            if not valido:
                flash(f'IBAN inválido: {resultado}', 'danger')
                return redirect(request.url)
            iban = resultado
        
        # Validar telefone MBWay se fornecido
        mbway_created = False
        if mbway_phone:
            valido, resultado = validar_telefone_portugal(mbway_phone)
            if not valido:
                flash(f'Telefone MBWay inválido: {resultado}', 'danger')
                return redirect(request.url)
            mbway_phone = resultado
            
            # Verificar se já existe este telefone MBWay
            existing_mbway = MBWay.query.filter_by(
                phone_number=mbway_phone,
                church_id=current_user.church_id
            ).first()
            
            if not existing_mbway:
                # Criar registro MBWay automaticamente
                new_mbway = MBWay(
                    church_id=current_user.church_id,
                    ministry_id=int(ministry_id) if ministry_id else None,
                    phone_number=mbway_phone,
                    description=f"MBWay da conta {bank_name} - {account_number}",
                    is_active=True
                )
                db.session.add(new_mbway)
                mbway_created = True
                flash('Número MBWay cadastrado automaticamente!', 'success')
        
        # Criar conta bancária
        new_account = BankAccount(
            church_id=current_user.church_id,
            ministry_id=int(ministry_id) if ministry_id else None,
            bank_name=bank_name,
            account_type=request.form.get('account_type'),
            account_number=account_number,
            agency=request.form.get('agency', '').strip(),
            iban=iban if iban else None,
            swift=request.form.get('swift', '').strip() or None,
            pix_key=request.form.get('pix_key', '').strip() or None,
            mbway_phone=mbway_phone if mbway_phone else None,
            notes=request.form.get('notes', '').strip() or None,
            is_active=True
        )
        
        try:
            db.session.add(new_account)
            db.session.commit()
            
            log_action(
                action='CREATE',
                module='BANK_ACCOUNT',
                description=f"Nova conta bancária: {new_account.bank_name} - {new_account.account_number}",
                new_values={'id': new_account.id, 'bank': new_account.bank_name},
                church_id=current_user.church_id
            )
            
            if mbway_created:
                flash('Conta bancária e MBWay cadastrados com sucesso!', 'success')
            else:
                flash('Conta bancária cadastrada com sucesso!', 'success')
                
            return redirect(url_for('finance.list_bank_accounts'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao criar conta bancária: {str(e)}")
            flash('Erro ao cadastrar conta bancária. Verifique os dados.', 'danger')
            return redirect(request.url)
    
    # GET - carregar formulário
    ministries = Ministry.query.filter_by(church_id=current_user.church_id).all()
    return render_template('finance/add_bank_account.html', ministries=ministries)


@finance_bp.route('/bank-account/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_bank_account(id):
    """Editar conta bancária"""
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
    
    account = BankAccount.query.get_or_404(id)
    
    # Verificar permissão
    if account.ministry_id:
        ministry = Ministry.query.get(account.ministry_id)
        if not (is_admin() or (ministry and ministry.leader_id == current_user.id)):
            flash('Acesso negado.', 'danger')
            return redirect(url_for('finance.list_bank_accounts'))
    
    if request.method == 'POST':
        # Validações (mesmas do add)
        mbway_phone = request.form.get('mbway_phone', '').strip()
        
        if mbway_phone:
            valido, resultado = validar_telefone_portugal(mbway_phone)
            if not valido:
                flash(f'Telefone MBWay inválido: {resultado}', 'danger')
                return redirect(request.url)
            mbway_phone = resultado
        
        old_phone = account.mbway_phone
        
        # Atualizar conta
        account.bank_name = request.form.get('bank_name')
        account.account_type = request.form.get('account_type')
        account.account_number = request.form.get('account_number')
        account.agency = request.form.get('agency')
        account.iban = request.form.get('iban') or None
        account.swift = request.form.get('swift') or None
        account.pix_key = request.form.get('pix_key') or None
        account.mbway_phone = mbway_phone or None
        account.notes = request.form.get('notes')
        account.is_active = 'is_active' in request.form
        
        # Se mudou o telefone MBWay, atualizar/ criar registro MBWay
        if mbway_phone and mbway_phone != old_phone:
            # Verificar se já existe MBWay com este número
            existing = MBWay.query.filter_by(
                phone_number=mbway_phone,
                church_id=current_user.church_id
            ).first()
            
            if not existing:
                new_mbway = MBWay(
                    church_id=current_user.church_id,
                    ministry_id=account.ministry_id,
                    phone_number=mbway_phone,
                    description=f"MBWay da conta {account.bank_name} - {account.account_number}",
                    is_active=True
                )
                db.session.add(new_mbway)
                flash('Número MBWay atualizado automaticamente!', 'success')
        
        db.session.commit()
        
        log_action(
            action='UPDATE',
            module='BANK_ACCOUNT',
            description=f"Conta bancária editada: {account.bank_name}",
            church_id=current_user.church_id
        )
        
        flash('Conta bancária atualizada!', 'success')
        return redirect(url_for('finance.list_bank_accounts'))
    
    return render_template('finance/edit_bank_account.html', account=account)


@finance_bp.route('/bank-account/delete/<int:id>', methods=['POST'])
@login_required
def delete_bank_account(id):
    """Excluir conta bancária"""
    if not can_manage_finance():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    account = BankAccount.query.get_or_404(id)
    
    # Verificar permissão
    if account.ministry_id:
        ministry = Ministry.query.get(account.ministry_id)
        if not (is_admin() or (ministry and ministry.leader_id == current_user.id)):
            return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    account_data = {'id': account.id, 'bank': account.bank_name}
    
    try:
        db.session.delete(account)
        db.session.commit()
        
        log_action(
            action='DELETE',
            module='BANK_ACCOUNT',
            description=f"Conta bancária excluída: {account.bank_name}",
            old_values=account_data,
            church_id=current_user.church_id
        )
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# ==================== ROTAS PARA MBWAY ====================

@finance_bp.route('/mbway')
@login_required
def list_mbway():
    """Listar números MBWay"""
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
    
    church_mbway = MBWay.query.filter_by(
        church_id=current_user.church_id,
        ministry_id=None
    ).all()
    
    ministry_mbway = []
    if can_manage_finance():
        ministries = Ministry.query.filter_by(church_id=current_user.church_id).all()
        for ministry in ministries:
            if is_admin() or ministry.leader_id == current_user.id:
                numbers = MBWay.query.filter_by(ministry_id=ministry.id).all()
                ministry_mbway.extend(numbers)
    
    return render_template('finance/mbway.html', 
                           church_mbway=church_mbway,
                           ministry_mbway=ministry_mbway)


@finance_bp.route('/mbway/add', methods=['GET', 'POST'])
@login_required
def add_mbway():
    """Adicionar número MBWay"""
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
    
    if request.method == 'POST':
        ministry_id = request.form.get('ministry_id')
        
        # Verificar permissão
        if ministry_id:
            ministry = Ministry.query.get(ministry_id)
            if not (is_admin() or (ministry and ministry.leader_id == current_user.id)):
                flash('Acesso negado.', 'danger')
                return redirect(url_for('finance.list_mbway'))
        
        new_mbway = MBWay(
            church_id=current_user.church_id,
            ministry_id=int(ministry_id) if ministry_id else None,
            phone_number=request.form.get('phone_number'),
            description=request.form.get('description'),
            is_active=True
        )
        db.session.add(new_mbway)
        db.session.commit()
        
        log_action(
            action='CREATE',
            module='MBWAY',
            description=f"Novo MBWay: {new_mbway.phone_number}",
            new_values={'id': new_mbway.id, 'phone': new_mbway.phone_number},
            church_id=current_user.church_id
        )
        
        flash('Número MBWay cadastrado!', 'success')
        return redirect(url_for('finance.list_mbway'))
    
    ministries = Ministry.query.filter_by(church_id=current_user.church_id).all()
    return render_template('finance/add_mbway.html', ministries=ministries)


# ==================== ATUALIZAÇÃO DAS ROTAS DE MINISTÉRIO ====================

@finance_bp.route('/ministry/<int:ministry_id>/categories')
@login_required
def ministry_categories(ministry_id):
    """Gerenciar categorias do ministério"""
    ministry = Ministry.query.get_or_404(ministry_id)
    if not (is_admin() or is_ministry_leader(ministry) or can_manage_finance()):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    categories = MinistryCategory.query.filter_by(ministry_id=ministry_id).all()
    return render_template('finance/ministry_categories.html', 
                           ministry=ministry, 
                           categories=categories)


@finance_bp.route('/ministry/<int:ministry_id>/categories/add', methods=['POST'])
@login_required
def add_ministry_category(ministry_id):
    """Adicionar categoria personalizada para ministério"""
    ministry = Ministry.query.get_or_404(ministry_id)
    if not (is_admin() or ministry.leader_id == current_user.id or ministry.vice_leader_id == current_user.id):
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    name = request.form.get('name')
    type_ = request.form.get('type')
    
    if not name or not type_:
        return jsonify({'success': False, 'message': 'Nome e tipo obrigatórios.'}), 400
    
    new_cat = MinistryCategory(
        ministry_id=ministry_id,
        name=name,
        type=type_
    )
    db.session.add(new_cat)
    db.session.commit()
    
    log_action(
        action='CREATE',
        module='MINISTRY_FINANCE',
        description=f"Nova categoria no ministério {ministry.name}: {name}",
        new_values={'id': new_cat.id, 'name': name},
        church_id=ministry.church_id
    )
    
    return jsonify({'success': True, 'id': new_cat.id})


@finance_bp.route('/ministry/<int:ministry_id>/payment-methods')
@login_required
def ministry_payment_methods(ministry_id):
    """Gerenciar métodos de pagamento do ministério"""
    ministry = Ministry.query.get_or_404(ministry_id)
    if not (is_admin() or is_ministry_leader(ministry) or can_manage_finance()):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
    
    methods = MinistryPaymentMethod.query.filter_by(ministry_id=ministry_id).all()
    return render_template('finance/ministry_payment_methods.html', 
                           ministry=ministry, 
                           methods=methods)


@finance_bp.route('/ministry/<int:ministry_id>/payment-methods/add', methods=['POST'])
@login_required
def add_ministry_payment_method(ministry_id):
    ministry = Ministry.query.get_or_404(ministry_id)
    if not (is_admin() or ministry.leader_id == current_user.id or ministry.vice_leader_id == current_user.id):
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    name = request.form.get('name')
    
    # CORREÇÃO: tratar o valor corretamente
    raw_value = request.form.get('is_electronic')
    is_electronic = raw_value == 'true'  # Se for 'true', vira True; qualquer outra coisa vira False
    
    print(f"🔍 raw_value: {raw_value}, is_electronic: {is_electronic}")
    
    if not name:
        return jsonify({'success': False, 'message': 'Nome obrigatório.'}), 400
    
    new_method = MinistryPaymentMethod(
        ministry_id=ministry_id,
        name=name,
        is_electronic=is_electronic,
        is_active=True
    )
    db.session.add(new_method)
    db.session.commit()
    
    # LOG CORRETO (sem os ...)
    log_action(
        action='CREATE',
        module='MINISTRY_FINANCE',
        description=f"Novo método de pagamento no ministério {ministry.name}: {name}",
        new_values={'id': new_method.id, 'name': name},
        church_id=ministry.church_id
    )
    
    return jsonify({'success': True, 'id': new_method.id})


# ==================== ATUALIZAÇÃO DA ROTA DE ADIÇÃO DE TRANSAÇÃO DE MINISTÉRIO ====================

@finance_bp.route('/ministry/<int:ministry_id>/add', methods=['GET', 'POST'])
@login_required
def add_ministry_transaction(ministry_id):
    ministry = Ministry.query.get_or_404(ministry_id)
    is_leader = is_ministry_leader(ministry)
    if not (is_leader or can_manage_finance()):
        flash('Acesso negado.', 'danger')
        return redirect(url_for('members.dashboard'))
        
    if request.method == 'POST':
        is_debt = 'is_debt' in request.form
        debtor_id = request.form.get('debtor_id')
        
        # Novos campos para categorias e métodos personalizados
        use_custom = request.form.get('use_custom') == 'on'
        
        # === VALIDAÇÃO DO TIPO VS CATEGORIA ===
        tipo_selecionado = request.form.get('type')
        categoria_tipo = None
        erro_tipo = False
        
        if use_custom:
            # Verificar categoria do ministério
            ministry_category_id = request.form.get('ministry_category_id')
            if ministry_category_id:
                ministry_category = MinistryCategory.query.get(ministry_category_id)
                if ministry_category:
                    categoria_tipo = ministry_category.type
                    if categoria_tipo != tipo_selecionado:
                        flash(f'A categoria "{ministry_category.name}" é do tipo {categoria_tipo}, mas você selecionou {tipo_selecionado}.', 'danger')
                        erro_tipo = True
        else:
            # Verificar categoria geral
            category_id = request.form.get('category_id')
            if category_id:
                category = TransactionCategory.query.get(category_id)
                if category:
                    categoria_tipo = category.type
                    if categoria_tipo != tipo_selecionado:
                        flash(f'A categoria "{category.name}" é do tipo {categoria_tipo}, mas você selecionou {tipo_selecionado}.', 'danger')
                        erro_tipo = True
        
        if erro_tipo:
            return redirect(request.url)
        # ======================================
        
        if use_custom:
            # Usar categorias e métodos do ministério
            ministry_category_id = request.form.get('ministry_category_id')
            ministry_payment_method_id = request.form.get('ministry_payment_method_id')
            
            ministry_category = MinistryCategory.query.get(ministry_category_id) if ministry_category_id else None
            ministry_payment_method = MinistryPaymentMethod.query.get(ministry_payment_method_id) if ministry_payment_method_id else None
            
            category_name = ministry_category.name if ministry_category else "Geral"
            payment_method_name = ministry_payment_method.name if ministry_payment_method else "Dinheiro"
        else:
            # Usar categorias e métodos gerais (padrão atual)
            category_id = request.form.get('category_id')
            payment_method_id = request.form.get('payment_method_id')
            
            category = TransactionCategory.query.get(category_id) if category_id else None
            payment_method = PaymentMethod.query.get(payment_method_id) if payment_method_id else None
            
            category_name = category.name if category else "Geral"
            payment_method_name = payment_method.name if payment_method else "Dinheiro"
        
        # Conta bancária (opcional)
        bank_account_id = request.form.get('bank_account_id')
        
        new_tx = MinistryTransaction(
            ministry_id=ministry.id,
            type=tipo_selecionado,
            category_id=int(category_id) if not use_custom and category_id else None,
            category_name=category_name if not use_custom else None,
            ministry_category_id=int(ministry_category_id) if use_custom and ministry_category_id else None,
            payment_method_id=int(payment_method_id) if not use_custom and payment_method_id else None,
            payment_method_name=payment_method_name if not use_custom else None,
            ministry_payment_method_id=int(ministry_payment_method_id) if use_custom and ministry_payment_method_id else None,
            bank_account_id=int(bank_account_id) if bank_account_id else None,
            amount=float(request.form.get('amount') or 0),
            description=request.form.get('description'),
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%d') if request.form.get('date') else datetime.utcnow(),
            is_debt=is_debt,
            debtor_id=int(debtor_id) if debtor_id and debtor_id != '' else None,
            is_paid=not is_debt
        )
        db.session.add(new_tx)
        db.session.commit()
        
        log_action(
            action='CREATE',
            module='MINISTRY_FINANCE',
            description=f"Lançamento em {ministry.name}: {new_tx.description} (R$ {new_tx.amount})",
            new_values={
                'id': new_tx.id,
                'ministry_id': ministry.id,
                'amount': new_tx.amount
            },
            church_id=ministry.church_id
        )
        
        flash('Lançamento do ministério registrado!', 'success')
        return redirect(url_for('finance.ministry_finance', ministry_id=ministry.id))
    
    # GET - carregar dados para o formulário
    members = User.query.filter_by(church_id=current_user.church_id, status='active').all()
    
    # Categorias e métodos (gerais e do ministério)
    general_categories = TransactionCategory.query.filter_by(church_id=current_user.church_id, is_active=True).all()
    general_payment_methods = PaymentMethod.query.filter_by(church_id=current_user.church_id, is_active=True).all()
    
    ministry_categories = MinistryCategory.query.filter_by(ministry_id=ministry.id, is_active=True).all()
    ministry_payment_methods = MinistryPaymentMethod.query.filter_by(ministry_id=ministry.id, is_active=True).all()
    
    # Contas bancárias disponíveis
    bank_accounts = BankAccount.query.filter(
        db.or_(
            BankAccount.church_id == current_user.church_id,
            BankAccount.ministry_id == ministry.id
        ),
        BankAccount.is_active == True
    ).all()
    
    today = datetime.utcnow().date().isoformat()
    
    return render_template('finance/add_ministry_tx.html', 
                           ministry=ministry, 
                           members=members,
                           general_categories=general_categories,
                           general_payment_methods=general_payment_methods,
                           ministry_categories=ministry_categories,
                           ministry_payment_methods=ministry_payment_methods,
                           bank_accounts=bank_accounts,
                           today=today)

@finance_bp.route('/ministry/payment-method/delete/<int:id>', methods=['POST'])
@login_required
def delete_ministry_payment_method(id):
    """Excluir método de pagamento do ministério"""
    method = MinistryPaymentMethod.query.get_or_404(id)
    ministry = method.ministry
    
    # Verificar permissão
    if not (is_admin() or ministry.leader_id == current_user.id or ministry.vice_leader_id == current_user.id):
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    method_data = {'id': method.id, 'name': method.name}
    
    try:
        db.session.delete(method)
        db.session.commit()
        
        log_action(
            action='DELETE',
            module='MINISTRY_FINANCE',
            description=f"Método de pagamento excluído: {method.name}",
            old_values=method_data,
            church_id=ministry.church_id
        )
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    
@finance_bp.route('/bank-account/<int:account_id>')
@login_required
def bank_account_detail(account_id):
    """Detalhes e extrato de uma conta bancária específica"""
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
    
    account = BankAccount.query.get_or_404(account_id)
    
    # Verificar permissão
    if account.ministry_id:
        ministry = Ministry.query.get(account.ministry_id)
        if not (is_admin() or (ministry and ministry.leader_id == current_user.id)):
            flash('Acesso negado.', 'danger')
            return redirect(url_for('finance.list_bank_accounts'))
    elif account.church_id != current_user.church_id:
        if not is_admin():
            flash('Acesso negado.', 'danger')
            return redirect(url_for('finance.list_bank_accounts'))
    
    # Filtros
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    tx_type = request.args.get('type')
    
    # Query base - transações desta conta
    query = Transaction.query.filter_by(bank_account_id=account_id)
    
    # Aplicar filtros
    if start_date:
        query = query.filter(Transaction.date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Transaction.date <= datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))
    if tx_type:
        query = query.filter(Transaction.type == tx_type)
    
    transactions = query.order_by(Transaction.date.desc()).all()
    
    # Calcular saldos
    total_income = sum(t.amount for t in transactions if t.type == 'income')
    total_expense = sum(t.amount for t in transactions if t.type == 'expense')
    balance = total_income - total_expense
    
    # Buscar transações MBWay associadas a esta conta (se tiver MBWay)
    mbway_transactions = []
    if account.mbway_phone:
        # Se tivesse uma tabela de transações MBWay, buscaria aqui
        pass
    
    stats = {
        'income': total_income,
        'expense': total_expense,
        'balance': balance,
        'transaction_count': len(transactions)
    }
    
    return render_template(
        'finance/bank_account_detail.html',
        account=account,
        transactions=transactions,
        stats=stats,
        mbway_transactions=mbway_transactions,
        filters={
            'start_date': start_date,
            'end_date': end_date,
            'type': tx_type
        }
    )

# ==================== ROTAS PARA FORNECEDORES ====================

@finance_bp.route('/suppliers')
@login_required
def list_suppliers():
    """Listar fornecedores"""
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
    
    search = request.args.get('search', '').strip()
    country = request.args.get('country')
    
    query = Supplier.query.filter_by(church_id=current_user.church_id)
    
    if search:
        query = query.filter(
            or_(
                Supplier.name.ilike(f'%{search}%'),
                Supplier.tax_id.ilike(f'%{search}%'),
                Supplier.email.ilike(f'%{search}%')
            )
        )
    
    if country:
        query = query.filter(Supplier.country == country)
    
    suppliers = query.order_by(Supplier.name).all()
    
    return render_template('finance/suppliers.html', 
                           suppliers=suppliers,
                           search=search)


@finance_bp.route('/supplier/add', methods=['GET', 'POST'])
@login_required
def add_supplier():
    """Adicionar fornecedor"""
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
    
    if request.method == 'POST':
        supplier = Supplier(
            name=request.form.get('name'),
            tax_id=request.form.get('tax_id') or None,
            tax_id_type=request.form.get('tax_id_type') or 'NIF',
            email=request.form.get('email') or None,
            phone=request.form.get('phone') or None,
            mobile=request.form.get('mobile') or None,
            website=request.form.get('website') or None,
            address=request.form.get('address') or None,
            address_number=request.form.get('address_number') or None,
            complement=request.form.get('complement') or None,
            neighborhood=request.form.get('neighborhood') or None,
            city=request.form.get('city') or None,
            state=request.form.get('state') or None,
            postal_code=request.form.get('postal_code') or None,
            country=request.form.get('country') or 'Portugal',
            contact_person=request.form.get('contact_person') or None,
            contact_phone=request.form.get('contact_phone') or None,
            contact_email=request.form.get('contact_email') or None,
            bank_name=request.form.get('bank_name') or None,
            bank_account=request.form.get('bank_account') or None,
            iban=request.form.get('iban') or None,
            swift=request.form.get('swift') or None,
            pix_key=request.form.get('pix_key') or None,
            notes=request.form.get('notes') or None,
            church_id=current_user.church_id,
            is_active=True
        )
        
        db.session.add(supplier)
        db.session.commit()
        
        log_action(
            action='CREATE',
            module='FINANCE',
            description=f"Novo fornecedor: {supplier.name}",
            new_values={'id': supplier.id, 'name': supplier.name, 'tax_id': supplier.tax_id},
            church_id=current_user.church_id
        )
        
        flash('Fornecedor cadastrado com sucesso!', 'success')
        return redirect(url_for('finance.list_suppliers'))
    
    return render_template('finance/add_supplier.html')


@finance_bp.route('/supplier/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_supplier(id):
    """Editar fornecedor"""
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
    
    supplier = Supplier.query.get_or_404(id)
    
    if supplier.church_id != current_user.church_id:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.list_suppliers'))
    
    if request.method == 'POST':
        old_values = {'name': supplier.name, 'tax_id': supplier.tax_id}
        
        supplier.name = request.form.get('name')
        supplier.tax_id = request.form.get('tax_id') or None
        supplier.tax_id_type = request.form.get('tax_id_type') or 'NIF'
        supplier.email = request.form.get('email') or None
        supplier.phone = request.form.get('phone') or None
        supplier.mobile = request.form.get('mobile') or None
        supplier.website = request.form.get('website') or None
        supplier.address = request.form.get('address') or None
        supplier.address_number = request.form.get('address_number') or None
        supplier.complement = request.form.get('complement') or None
        supplier.neighborhood = request.form.get('neighborhood') or None
        supplier.city = request.form.get('city') or None
        supplier.state = request.form.get('state') or None
        supplier.postal_code = request.form.get('postal_code') or None
        supplier.country = request.form.get('country') or 'Portugal'
        supplier.contact_person = request.form.get('contact_person') or None
        supplier.contact_phone = request.form.get('contact_phone') or None
        supplier.contact_email = request.form.get('contact_email') or None
        supplier.bank_name = request.form.get('bank_name') or None
        supplier.bank_account = request.form.get('bank_account') or None
        supplier.iban = request.form.get('iban') or None
        supplier.swift = request.form.get('swift') or None
        supplier.pix_key = request.form.get('pix_key') or None
        supplier.notes = request.form.get('notes') or None
        supplier.is_active = 'is_active' in request.form
        
        db.session.commit()
        
        log_action(
            action='UPDATE',
            module='FINANCE',
            description=f"Fornecedor editado: {supplier.name}",
            old_values=old_values,
            new_values={'name': supplier.name, 'tax_id': supplier.tax_id},
            church_id=current_user.church_id
        )
        
        flash('Fornecedor atualizado!', 'success')
        return redirect(url_for('finance.list_suppliers'))
    
    return render_template('finance/edit_supplier.html', supplier=supplier)


@finance_bp.route('/supplier/delete/<int:id>', methods=['POST'])
@login_required
def delete_supplier(id):
    """Excluir fornecedor"""
    if not can_manage_finance():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    supplier = Supplier.query.get_or_404(id)
    
    if supplier.church_id != current_user.church_id:
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    # Verificar se tem contas vinculadas
    if supplier.bills.count() > 0:
        return jsonify({'success': False, 'message': 'Não é possível excluir. Existem contas vinculadas a este fornecedor.'}), 400
    
    supplier_data = {'id': supplier.id, 'name': supplier.name}
    
    db.session.delete(supplier)
    db.session.commit()
    
    log_action(
        action='DELETE',
        module='FINANCE',
        description=f"Fornecedor excluído: {supplier.name}",
        old_values=supplier_data,
        church_id=current_user.church_id
    )
    
    return jsonify({'success': True})

# ==================== ROTAS PARA CONTAS A PAGAR ====================

@finance_bp.route('/bills')
@login_required
def list_bills():
    """Listar contas a pagar"""
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
    
    # Filtros
    status_filter = request.args.get('status')
    supplier_id = request.args.get('supplier_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = Bill.query.filter_by(church_id=current_user.church_id)
    
    if status_filter:
        query = query.filter(Bill.status == status_filter)
    
    if supplier_id:
        query = query.filter(Bill.supplier_id == int(supplier_id))
    
    if start_date:
        query = query.filter(Bill.due_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    
    if end_date:
        query = query.filter(Bill.due_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
    
    bills = query.order_by(Bill.due_date.asc()).all()
    suppliers = Supplier.query.filter_by(church_id=current_user.church_id, is_active=True).all()
    
    # Totais
    total_pending = sum(b.remaining_amount for b in bills if b.status == 'pending')
    total_overdue = sum(b.remaining_amount for b in bills if b.is_overdue and b.status != 'paid')
    total_paid = sum(b.amount for b in bills if b.status == 'paid')
    
    stats = {
        'total_pending': total_pending,
        'total_overdue': total_overdue,
        'total_paid': total_paid,
        'count': len(bills)
    }
    
    return render_template('finance/bills.html', 
                           bills=bills, 
                           suppliers=suppliers,
                           stats=stats,
                           filters={
                               'status': status_filter,
                               'supplier_id': supplier_id,
                               'start_date': start_date,
                               'end_date': end_date
                           })


@finance_bp.route('/bill/add', methods=['GET', 'POST'])
@login_required
def add_bill():
    """Adicionar conta a pagar"""
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
    
    if request.method == 'POST':
        from decimal import Decimal
        
        bill = Bill(
            supplier_id=int(request.form.get('supplier_id')),
            description=request.form.get('description'),
            amount=Decimal(str(request.form.get('amount'))),  # 🔥 CONVERTER PARA DECIMAL
            due_date=datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date(),
            issue_date=datetime.strptime(request.form.get('issue_date'), '%Y-%m-%d').date() if request.form.get('issue_date') else datetime.utcnow().date(),
            invoice_number=request.form.get('invoice_number') or None,
            invoice_series=request.form.get('invoice_series') or None,
            nf_access_key=request.form.get('nf_access_key') or None,
            category_id=int(request.form.get('category_id')) if request.form.get('category_id') else None,
            payment_method_id=int(request.form.get('payment_method_id')) if request.form.get('payment_method_id') else None,
            bank_account_id=int(request.form.get('bank_account_id')) if request.form.get('bank_account_id') else None,
            notes=request.form.get('notes') or None,
            church_id=current_user.church_id,
            created_by=current_user.id,
            status='pending'
        )
        
        db.session.add(bill)
        db.session.commit()
        
        # 🔥 LOG COM VALORES CONVERTIDOS PARA FLOAT
        log_action(
            action='CREATE',
            module='FINANCE',
            description=f"Nova conta a pagar: {bill.description} - R$ {float(bill.amount):.2f}",
            new_values={
                'id': bill.id, 
                'supplier': bill.supplier.name, 
                'amount': float(bill.amount)
            },
            church_id=current_user.church_id
        )
        
        flash('Conta registrada com sucesso!', 'success')
        return redirect(url_for('finance.list_bills'))
    
    suppliers = Supplier.query.filter_by(church_id=current_user.church_id, is_active=True).order_by(Supplier.name).all()
    categories = TransactionCategory.query.filter_by(church_id=current_user.church_id, type='expense', is_active=True).all()
    payment_methods = PaymentMethod.query.filter_by(church_id=current_user.church_id, is_active=True).all()
    bank_accounts = BankAccount.query.filter_by(church_id=current_user.church_id, is_active=True).all()
    
    return render_template('finance/add_bill.html', 
                           suppliers=suppliers,
                           categories=categories,
                           payment_methods=payment_methods,
                           bank_accounts=bank_accounts)


@finance_bp.route('/bill/pay/<int:id>', methods=['GET', 'POST'])
@login_required
def pay_bill(id):
    """Registrar pagamento de conta"""
    if not can_manage_finance():
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.dashboard'))
    
    bill = Bill.query.get_or_404(id)
    
    if bill.church_id != current_user.church_id:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('finance.list_bills'))
    
    if request.method == 'POST':
        amount_to_pay = float(request.form.get('amount'))
        payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date()
        payment_method_id = request.form.get('payment_method_id')
        bank_account_id = request.form.get('bank_account_id')
        
        if amount_to_pay <= 0:
            flash('Valor inválido.', 'danger')
            return redirect(request.url)
        
        if amount_to_pay > float(bill.remaining_amount):
            flash(f'Valor excede o saldo devedor (R$ {bill.remaining_amount:.2f})', 'danger')
            return redirect(request.url)
        
        # Buscar informações para a transação
        payment_method = PaymentMethod.query.get(payment_method_id) if payment_method_id else None
        bank_account = BankAccount.query.get(bank_account_id) if bank_account_id else None
        
        # Converter para Decimal
        from decimal import Decimal
        amount_decimal = Decimal(str(amount_to_pay))
        
        # 🔥 CRIAR TRANSAÇÃO COM VÍNCULO DA CONTA
        transaction = Transaction(
            type='expense',
            category_id=bill.category_id,
            category_name=bill.category.name if bill.category else f"Pagamento - {bill.supplier.name}",
            payment_method_id=int(payment_method_id) if payment_method_id else None,
            payment_method_name=payment_method.name if payment_method else "Dinheiro",
            bank_account_id=int(bank_account_id) if bank_account_id else None,
            amount=amount_to_pay,
            description=f"Pagamento de {bill.description} - {bill.supplier.name} (NF: {bill.invoice_number or 'sem NF'})",
            date=payment_date,
            church_id=current_user.church_id,
            user_id=None,
            bill_id=bill.id  # 🔥 VÍNCULO EXPLÍCITO
        )
        
        # Atualizar a conta
        bill.amount_paid = bill.amount_paid + amount_decimal
        bill.payment_date = payment_date
        bill.payment_method_id = int(payment_method_id) if payment_method_id else None
        bill.bank_account_id = int(bank_account_id) if bank_account_id else None
        
        if bill.remaining_amount == 0:
            bill.status = 'paid'
        else:
            bill.status = 'partial'
        
        db.session.add(transaction)
        db.session.commit()
        
        # LOG
        log_action(
            action='CREATE',
            module='FINANCE',
            description=f"Pagamento de conta: {bill.description} - R$ {amount_to_pay:.2f}",
            new_values={
                'bill_id': bill.id,
                'transaction_id': transaction.id,
                'amount_paid': float(bill.amount_paid),
                'status': bill.status
            },
            church_id=current_user.church_id
        )
        
        flash(f'Pagamento de R$ {amount_to_pay:.2f} registrado com sucesso!', 'success')
        return redirect(url_for('finance.list_bills'))
    
    # GET - buscar dados para o formulário
    payment_methods = PaymentMethod.query.filter_by(church_id=current_user.church_id, is_active=True).all()
    bank_accounts = BankAccount.query.filter_by(church_id=current_user.church_id, is_active=True).all()
    
    return render_template('finance/pay_bill.html', 
                           bill=bill,
                           payment_methods=payment_methods,
                           bank_accounts=bank_accounts,
                           now=datetime.now())


@finance_bp.route('/bill/<int:id>/details')
@login_required
def bill_details(id):
    """Retorna os detalhes de uma conta via JSON"""
    if not can_manage_finance():
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    bill = Bill.query.get_or_404(id)
    
    if bill.church_id != current_user.church_id:
        return jsonify({'success': False, 'message': 'Acesso negado.'}), 403
    
    # Determinar classe CSS e texto do status
    if bill.status == 'paid':
        status_class = 'text-success'
        status_text = 'Pago'
    elif bill.status == 'partial':
        status_class = 'text-info'
        status_text = f'Parcial ({bill.payment_percentage:.0f}%)'
    elif bill.is_overdue:
        status_class = 'text-danger'
        status_text = 'Vencida'
    else:
        status_class = 'text-warning'
        status_text = 'Pendente'
    
    return jsonify({
        'success': True,
        'bill': {
            'id': bill.id,
            'supplier_name': bill.supplier.name,
            'supplier_tax_id': bill.supplier.tax_id,
            'description': bill.description,
            'amount': f"{float(bill.amount):.2f}",
            'amount_paid': f"{float(bill.amount_paid):.2f}",
            'remaining': f"{float(bill.remaining_amount):.2f}",
            'due_date': bill.due_date.strftime('%d/%m/%Y'),
            'issue_date': bill.issue_date.strftime('%d/%m/%Y'),
            'payment_date': bill.payment_date.strftime('%d/%m/%Y') if bill.payment_date else None,
            'invoice_number': bill.invoice_number,
            'notes': bill.notes,
            'status': bill.status,
            'status_text': status_text,
            'status_class': status_class,
            'is_overdue': bill.is_overdue
        }
    })