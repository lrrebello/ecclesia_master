from fpdf import FPDF
import os
from flask import current_app
from datetime import datetime

class ReceiptPDF(FPDF):
    def header(self):
        # Cabeçalho tratado manualmente na função principal
        pass

    def footer(self):
        # Rodapé tratado manualmente na função principal
        pass


def generate_receipt(transaction):
    """
    Gera recibo individual para uma única transação (versão original mantida)
    """
    pdf = ReceiptPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ========================
    #   CONFIGURAÇÃO DE FONTES UNICODE
    # ========================
    font_dir = os.path.join(current_app.root_path, 'static', 'fonts')
    
    regular_path = os.path.join(font_dir, 'DejaVuSans.ttf')
    bold_path    = os.path.join(font_dir, 'DejaVuSans-Bold.ttf')
    
    use_dejavu = os.path.exists(regular_path) and os.path.exists(bold_path)
    
    if use_dejavu:
        pdf.add_font(family='DejaVu', style='', fname=regular_path, uni=True)
        pdf.add_font(family='DejaVu', style='B', fname=bold_path, uni=True)
        base_font = 'DejaVu'
    else:
        base_font = 'Helvetica'
        current_app.logger.warning(
            "Fontes DejaVuSans não encontradas em app/static/fonts/. "
            "Usando Helvetica como fallback – pode falhar com símbolo €."
        )

    # --- CABEÇALHO COM LOGO E INFORMAÇÕES DA IGREJA ---
    y_start = 10
    
    # Inserir o logo da congregação (se existir)
    if transaction.church and transaction.church.logo_path:
        logo_relative = transaction.church.logo_path
        logo_full_path = os.path.join(current_app.root_path, 'static', logo_relative)
        if os.path.exists(logo_full_path) and os.path.isfile(logo_full_path):
            try:
                pdf.image(logo_full_path, x=10, y=8, w=20)
                current_app.logger.info(f"Logo inserido no recibo: {logo_full_path}")
                x_text = 35
                y_start = 12
            except Exception as e:
                current_app.logger.error(f"Erro ao inserir logo {logo_full_path}: {str(e)}")
                x_text = 10
                y_start = 10
        else:
            current_app.logger.warning(f"Logo não encontrado no disco: {logo_full_path}")
            x_text = 10
            y_start = 10
    else:
        x_text = 10
        y_start = 10
    
    # Nome da igreja em negrito
    pdf.set_xy(x_text, y_start)
    pdf.set_font(base_font, 'B', 12)
    
    church_name = transaction.church.name if transaction.church else "SEDE"
    pdf.cell(0, 10, church_name, 0, 1, 'L')
    
    # Endereço
    pdf.set_x(10)
    pdf.set_font(base_font, '', 10)
    
    address = transaction.church.address if transaction.church and transaction.church.address else "R. Dr. Mário Sacramento, 57 - 4ºEsq. Trás"
    pdf.cell(0, 5, address, 0, 1, 'L')
    
    # Cidade/Código Postal
    pdf.set_x(10)
    city = transaction.church.city if transaction.church and transaction.church.city else "3810-106 Aveiro"
    pdf.cell(0, 5, city, 0, 1, 'L')
    
    pdf.ln(2)
    
    # NIF e outras informações
    pdf.set_x(10)
    nif = f"Nº Contribuinte: {transaction.church.nif}" if transaction.church and transaction.church.nif else "Nº Contribuinte: 517760010"
    pdf.cell(0, 5, nif + "   Qualidade Jurídica: Pessoa Coletiva Religiosa   Reconhecimento:", 0, 1, 'L')
    
    pdf.ln(2)
    
    # Email
    pdf.set_x(10)
    email = f"Email: {transaction.church.email}" if transaction.church and transaction.church.email else "Email: ieadjesus.nacao@gmail.com"
    pdf.cell(0, 5, email, 0, 1, 'L')
    
    pdf.ln(10)
    
    # --- BOX DO DOADOR ---
    start_y = pdf.get_y()
    
    user_name = transaction.user.name if transaction.user else "LUCAS RAMOS REBELLO DA SILVA"
    user_address = transaction.user.address if transaction.user and transaction.user.address else "Praceta infante, edifício Vagueimar 1, BlocoA, rés de chão direito"
    user_city = "3840-273 Gafanha da Vagueira"
    user_nif = transaction.user.documents if transaction.user and transaction.user.documents else "309 889 669"
    user_email = transaction.user.email if transaction.user else "Irrebell0@gmail.com"
    
    pdf.rect(120, start_y - 5, 80, 35)
    
    pdf.set_xy(122, start_y)
    pdf.set_font(base_font, '', 10)
    pdf.cell(0, 5, "Para:", 0, 1)
    
    pdf.set_x(122)
    pdf.set_font(base_font, 'B', 10)
    pdf.cell(0, 5, user_name, 0, 1)
    
    pdf.set_x(122)
    pdf.set_font(base_font, '', 8)
    pdf.multi_cell(76, 4, user_address)
    
    pdf.set_x(122)
    pdf.cell(0, 4, user_city, 0, 1)
    
    pdf.set_x(122)
    pdf.set_font(base_font, '', 8)
    pdf.cell(0, 4, f"Nº Contribuinte: {user_nif}", 0, 1)
    
    pdf.set_x(122)
    pdf.cell(0, 4, f"Email: {user_email}", 0, 1)
    
    pdf.set_y(start_y + 40)
    
    pdf.ln(5)
    
    # --- TÍTULO DO DOCUMENTO ---
    pdf.set_font(base_font, 'B', 14)
    pdf.cell(0, 10, "COMPROVATIVO DE DONATIVO", 0, 1, 'L')
    
    pdf.ln(2)
    
    # --- TABELA DE DADOS ---
    pdf.set_fill_color(240, 240, 240)
    
    col1 = 25   # Nº
    col2 = 50   # Data
    col3 = 70   # Meio de Pagamento
    col4 = 45   # Valor
    
    pdf.set_font(base_font, 'B', 9)
    pdf.cell(col1, 8, "Nº", 1, 0, 'C', True)
    pdf.cell(col2, 8, "Data do Documento", 1, 0, 'C', True)
    pdf.cell(col3, 8, "Meio de Pagamento", 1, 0, 'C', True)
    pdf.cell(col4, 8, "Valor", 1, 1, 'C', True)
    
    pdf.set_font(base_font, '', 10)
    
    numero = f"{transaction.id:02d}" if isinstance(transaction.id, int) else str(transaction.id).zfill(2)
    pdf.cell(col1, 10, numero, 1, 0, 'C')
    
    data = transaction.date.strftime('%d/%m/%Y') if hasattr(transaction, 'date') else "02/02/2025"
    pdf.cell(col2, 10, data, 1, 0, 'C')
    
    payment_method = transaction.payment_method_name if transaction.payment_method_name else "Numerário"
    pdf.cell(col3, 10, payment_method, 1, 0, 'C')
    
    currency = transaction.church.currency_symbol if transaction.church and transaction.church.currency_symbol else "€"
    valor = f"{transaction.amount:.2f}".replace('.', ',') + f" {currency}"
    pdf.cell(col4, 10, valor, 1, 1, 'C')
    
    pdf.ln(10)
    
    # --- TEXTO DE CONFIRMAÇÃO ---
    pdf.set_font(base_font, '', 10)
    valor_extenso = f"{transaction.amount:.2f}".replace('.', ',')
    text = (
        f"Recebemos de V Exas. pelo meio acima indicado a quantia de {valor_extenso} {currency} "
        "como donativo destinado ao desenvolvimento da atividade desta instituição, "
        "concedido sem quaisquer contrapartidas."
    )
    pdf.multi_cell(0, 5, text)
    
    pdf.ln(10)
    
    # --- EFEITOS FISCAIS ---
    pdf.set_font(base_font, 'B', 10)
    pdf.cell(0, 5, "Efeitos fiscais:", 0, 1)
    
    pdf.ln(2)
    
    pdf.set_font(base_font, '', 9)
    pdf.rect(10, pdf.get_y(), 130, 15)
    
    current_y = pdf.get_y()
    pdf.set_xy(12, current_y + 2)
    pdf.cell(0, 5, "Enquadramento no Artigo 61º do EBF (donativo concedido sem contrapartidas)", 0, 1)
    
    pdf.set_xy(12, current_y + 8)
    pdf.cell(0, 5, "n.º 2 do artigo 63.º do EBF", 0, 1)
    
    pdf.set_y(current_y + 20)
    
    pdf.ln(10)
    
    # --- ASSINATURA ---
    pdf.set_font(base_font, '', 10)
    pdf.cell(0, 10, "Respeitosos cumprimentos", 0, 1)
    
    # --- SALVAMENTO ---
    filename = f"COMPROVATIVO_DONATIVO_{transaction.id}_{transaction.date.strftime('%Y%m%d')}.pdf"
    
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads')
    if not os.path.isabs(upload_folder):
        upload_folder = os.path.join(current_app.root_path, 'static/uploads')
    
    receipts_dir = os.path.join(upload_folder, 'receipts')
    os.makedirs(receipts_dir, exist_ok=True)
    
    filepath = os.path.join(receipts_dir, filename)
    pdf.output(filepath)
    
    return filename


def generate_consolidated_receipt(user, transactions, start_date, end_date):
    """
    Gera recibo consolidado para múltiplas transações em um período.
    Mantém o mesmo estilo visual do recibo individual.
    """
    pdf = ReceiptPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Configuração de fontes (igual ao individual)
    font_dir = os.path.join(current_app.root_path, 'static', 'fonts')
    regular_path = os.path.join(font_dir, 'DejaVuSans.ttf')
    bold_path    = os.path.join(font_dir, 'DejaVuSans-Bold.ttf')
    
    use_dejavu = os.path.exists(regular_path) and os.path.exists(bold_path)
    
    if use_dejavu:
        pdf.add_font(family='DejaVu', style='', fname=regular_path, uni=True)
        pdf.add_font(family='DejaVu', style='B', fname=bold_path, uni=True)
        base_font = 'DejaVu'
    else:
        base_font = 'Helvetica'

    # --- CABEÇALHO (mesmo do individual, usando igreja do usuário) ---
    y_start = 10
    x_text = 10

    church = user.church if hasattr(user, 'church') and user.church else None

    # Logo
    if church and church.logo_path:
        logo_full_path = os.path.join(current_app.root_path, 'static', church.logo_path.lstrip('/'))
        if os.path.exists(logo_full_path):
            try:
                pdf.image(logo_full_path, x=10, y=8, w=20)
                x_text = 35
                y_start = 12
            except:
                pass

    pdf.set_xy(x_text, y_start)
    pdf.set_font(base_font, 'B', 12)
    church_name = church.name if church else "SEDE"
    pdf.cell(0, 10, church_name, 0, 1, 'L')

    pdf.set_x(10)
    pdf.set_font(base_font, '', 10)
    address = church.address if church and church.address else "R. Dr. Mário Sacramento, 57 - 4ºEsq. Trás"
    pdf.cell(0, 5, address, 0, 1, 'L')

    pdf.set_x(10)
    city = church.city if church and church.city else "3810-106 Aveiro"
    pdf.cell(0, 5, city, 0, 1, 'L')

    pdf.ln(2)
    pdf.set_x(10)
    nif = f"Nº Contribuinte: {church.nif}" if church and church.nif else "Nº Contribuinte: 517760010"
    pdf.cell(0, 5, nif + "   Qualidade Jurídica: Pessoa Coletiva Religiosa   Reconhecimento:", 0, 1, 'L')

    pdf.ln(2)
    pdf.set_x(10)
    email = f"Email: {church.email}" if church and church.email else "Email: ieadjesus.nacao@gmail.com"
    pdf.cell(0, 5, email, 0, 1, 'L')

    pdf.ln(10)

    # --- BOX DO DOADOR (usando dados do usuário) ---
    start_y = pdf.get_y()
    pdf.rect(120, start_y - 5, 80, 35)

    pdf.set_xy(122, start_y)
    pdf.set_font(base_font, '', 10)
    pdf.cell(0, 5, "Para:", 0, 1)

    pdf.set_x(122)
    pdf.set_font(base_font, 'B', 10)
    pdf.cell(0, 5, user.name, 0, 1)

    pdf.set_x(122)
    pdf.set_font(base_font, '', 8)
    pdf.multi_cell(76, 4, user.address if user.address else "Endereço não cadastrado")

    pdf.set_x(122)
    pdf.cell(0, 4, user.city if hasattr(user, 'city') and user.city else "Cidade não cadastrada", 0, 1)

    pdf.set_x(122)
    pdf.set_font(base_font, '', 8)
    pdf.cell(0, 4, f"Nº Contribuinte: {user.documents if user.documents else 'Não informado'}", 0, 1)

    pdf.set_x(122)
    pdf.cell(0, 4, f"Email: {user.email}", 0, 1)

    pdf.set_y(start_y + 40)
    pdf.ln(5)

    # --- TÍTULO DO DOCUMENTO ---
    pdf.set_font(base_font, 'B', 14)
    pdf.cell(0, 10, f"COMPROVATIVO DE DONATIVOS - PERÍODO {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}", 0, 1, 'C')
    
    pdf.ln(5)

    # --- TABELA DE TRANSAÇÕES ---
    pdf.set_fill_color(240, 240, 240)
    
    col1 = 30   # Data
    col2 = 70   # Categoria
    col3 = 50   # Meio de Pagamento
    col4 = 40   # Valor
    
    pdf.set_font(base_font, 'B', 10)
    pdf.cell(col1, 8, "Data", 1, 0, 'C', True)
    pdf.cell(col2, 8, "Categoria", 1, 0, 'C', True)
    pdf.cell(col3, 8, "Meio de Pagto", 1, 0, 'C', True)
    pdf.cell(col4, 8, "Valor", 1, 1, 'C', True)

    pdf.set_font(base_font, '', 9)
    total_amount = 0.0
    currency = church.currency_symbol if church and church.currency_symbol else '€'

    for tx in transactions:
        pdf.cell(col1, 7, tx.date.strftime('%d/%m/%Y'), 1, 0, 'C')
        category = tx.category_name.capitalize() if tx.category_name else 'Geral'
        pdf.cell(col2, 7, category[:35] + '...' if len(category) > 35 else category, 1, 0, 'L')
        method = tx.payment_method_name or "Numerário"
        pdf.cell(col3, 7, method[:25] + '...' if len(method) > 25 else method, 1, 0, 'C')
        
        valor_str = f"{tx.amount:,.2f}".replace(',', ' ').replace('.', ',') + f" {currency}"
        pdf.cell(col4, 7, valor_str, 1, 1, 'R')
        
        total_amount += tx.amount

    # Total
    pdf.set_font(base_font, 'B', 10)
    pdf.cell(col1 + col2 + col3, 8, "TOTAL DO PERÍODO", 1, 0, 'R')
    total_str = f"{total_amount:,.2f}".replace(',', ' ').replace('.', ',') + f" {currency}"
    pdf.cell(col4, 8, total_str, 1, 1, 'R')

    pdf.ln(12)

    # --- TEXTO DE CONFIRMAÇÃO ---
    pdf.set_font(base_font, '', 10)
    total_extenso = f"{total_amount:,.2f}".replace('.', ',')
    text = (
        f"No período indicado, recebemos a quantia total de {total_extenso} {currency} "
        "como donativos destinados ao desenvolvimento da atividade desta instituição, "
        "concedidos sem quaisquer contrapartidas."
    )
    pdf.multi_cell(0, 5, text)

    pdf.ln(10)

    # --- EFEITOS FISCAIS (igual ao individual) ---
    pdf.set_font(base_font, 'B', 10)
    pdf.cell(0, 5, "Efeitos fiscais:", 0, 1)
    
    pdf.ln(2)
    
    pdf.set_font(base_font, '', 9)
    pdf.rect(10, pdf.get_y(), 130, 15)
    
    current_y = pdf.get_y()
    pdf.set_xy(12, current_y + 2)
    pdf.cell(0, 5, "Enquadramento no Artigo 61º do EBF (donativo concedido sem contrapartidas)", 0, 1)
    
    pdf.set_xy(12, current_y + 8)
    pdf.cell(0, 5, "n.º 2 do artigo 63.º do EBF", 0, 1)
    
    pdf.set_y(current_y + 20)

    pdf.ln(15)
    pdf.cell(0, 10, "Respeitosos cumprimentos", 0, 1, 'L')

    # --- Nome do arquivo ---
    filename = f"RECIBO_CONSOLIDADO_{user.name.replace(' ', '_')}_{start_date.year}_{end_date.strftime('%Y%m%d')}.pdf"
    
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads')
    if not os.path.isabs(upload_folder):
        upload_folder = os.path.join(current_app.root_path, 'static/uploads')
    
    receipts_dir = os.path.join(upload_folder, 'receipts')
    os.makedirs(receipts_dir, exist_ok=True)
    
    filepath = os.path.join(receipts_dir, filename)
    pdf.output(filepath)
    
    return filename