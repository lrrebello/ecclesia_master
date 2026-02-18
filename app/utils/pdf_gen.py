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
    pdf = ReceiptPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ========================
    #   CONFIGURAÇÃO DE FONTES UNICODE (para suportar €, ç, ã, etc.)
    # ========================
    font_dir = os.path.join(current_app.root_path, 'static', 'fonts')
    
    regular_path = os.path.join(font_dir, 'DejaVuSans.ttf')
    bold_path    = os.path.join(font_dir, 'DejaVuSans-Bold.ttf')
    
    use_dejavu = os.path.exists(regular_path) and os.path.exists(bold_path)
    
    if use_dejavu:
        pdf.add_font(family='DejaVu', style='', fname=regular_path)
        pdf.add_font(family='DejaVu', style='B', fname=bold_path)
        base_font = 'DejaVu'
    else:
        base_font = 'Helvetica'
        current_app.logger.warning(
            "Fontes DejaVuSans não encontradas em app/static/fonts/. "
            "Usando Helvetica como fallback – pode falhar com símbolo €."
        )

    # --- CABEÇALHO DA IGREJA ---
    pdf.set_font(base_font, 'B', 12)
    church_name = transaction.church.name if transaction.church else "Igreja Evangélica Assembleia de Deus"
    pdf.cell(10, 10, '', 0, 0)  # Espaço para logo futuro
    pdf.cell(0, 10, church_name, 0, 1, 'L')
    
    pdf.ln(5)
    pdf.set_font(base_font, '', 10)
    
    address = transaction.church.address if transaction.church and transaction.church.address else "SEDE R. Dr. Mário Sacramento, 57 - 4ºEsq. Trás"
    city = f"{transaction.church.city}" if transaction.church and transaction.church.city else "3810-106 Aveiro"
    pdf.cell(0, 5, address, 0, 1)
    pdf.cell(0, 5, city, 0, 1)
    
    pdf.ln(5)
    nif = f"Nº Contribuinte: {transaction.church.nif}" if transaction.church and transaction.church.nif else "Nº Contribuinte: 517760010"
    pdf.cell(0, 5, nif, 0, 1)
    pdf.cell(0, 5, "Qualidade Jurídica: Pessoa Coletiva Religiosa", 0, 1)
    pdf.cell(0, 5, "Reconhecimento:", 0, 1)
    
    pdf.ln(5)
    email = f"Email: {transaction.church.email}" if transaction.church and transaction.church.email else "Email: ieadjexus.nacao@gmail.com"
    pdf.cell(0, 5, email, 0, 1)
    
    # --- BOX DO DOADOR (DIREITA) ---
    pdf.set_xy(100, 60)
    pdf.set_font(base_font, '', 10)
    
    user_name = transaction.user.name if transaction.user else "DOADOR NÃO IDENTIFICADO"
    user_address = transaction.user.address if transaction.user and transaction.user.address else "Endereço não informado"
    user_nif = transaction.user.documents if transaction.user and transaction.user.documents else "NIF não informado"
    user_email = transaction.user.email if transaction.user else ""
    
    pdf.rect(95, 60, 100, 30)
    pdf.set_xy(97, 62)
    pdf.cell(0, 5, "Para:", 0, 1)
    pdf.set_x(97)
    pdf.set_font(base_font, 'B', 10)
    pdf.cell(0, 5, user_name.upper(), 0, 1)
    pdf.set_x(97)
    pdf.set_font(base_font, '', 9)
    pdf.multi_cell(95, 4, user_address)
    
    pdf.set_xy(95, 92)
    pdf.set_font(base_font, '', 9)
    pdf.cell(100, 5, f"Nº Contribuinte: {user_nif}", 0, 1, 'C')
    pdf.set_x(95)
    pdf.cell(100, 5, f"Email: {user_email}", 0, 1, 'C')
    
    pdf.ln(10)
    
    # --- TÍTULO DO DOCUMENTO ---
    pdf.set_y(115)
    pdf.set_font(base_font, 'B', 11)
    pdf.cell(0, 10, "COMPROVATIVO DE DONATIVO", 0, 1, 'L')
    
    # --- TABELA DE DADOS ---
    pdf.set_fill_color(220, 235, 245)  # Azul claro
    pdf.set_font(base_font, 'B', 10)
    
    # Cabeçalho da tabela
    pdf.cell(25, 8, "Nº", 1, 0, 'C', True)
    pdf.cell(50, 8, "Data do Documento", 1, 0, 'C', True)
    pdf.cell(70, 8, "Meio de Pagamento", 1, 0, 'C', True)
    pdf.cell(45, 8, "Valor", 1, 1, 'C', True)
    
    # Linha de dados
    pdf.set_font(base_font, '', 10)
    pdf.cell(25, 10, str(transaction.id), 1, 0, 'C')
    pdf.cell(50, 10, transaction.date.strftime('%d/%m/%Y'), 1, 0, 'C')
    
    payment_method = transaction.payment_method_name if transaction.payment_method_name else "Numerário"
    pdf.cell(70, 10, payment_method, 1, 0, 'C')
    
    # Valor (aqui o € deve aparecer corretamente agora)
    currency = transaction.church.currency_symbol if transaction.church else "€"
    pdf.cell(45, 10, f"{transaction.amount:.2f} {currency}", 1, 1, 'C')
    
    pdf.ln(10)
    
    # --- TEXTO DE CONFIRMAÇÃO ---
    pdf.set_font(base_font, '', 10)
    text = (
        f"Recebemos de V. Exas. pelo meio acima indicado a quantia de {transaction.amount:.2f} {currency} "
        "como donativo destinado ao desenvolvimento da atividade desta instituição, "
        "concedido sem quaisquer contrapartidas."
    )
    pdf.multi_cell(0, 5, text)
    
    pdf.ln(10)
    
    # --- EFEITOS FISCAIS ---
    pdf.set_font(base_font, 'B', 10)
    pdf.cell(0, 5, "Efeitos fiscais:", 0, 1)
    
    pdf.set_font(base_font, '', 9)
    pdf.rect(10, pdf.get_y(), 130, 12)
    pdf.set_x(12)
    pdf.cell(0, 6, "Enquadramento no Artigo 61º do EBF (donativo concedido sem contrapartidas)", 0, 1)
    pdf.set_x(12)
    pdf.line(10, pdf.get_y(), 140, pdf.get_y())
    pdf.cell(0, 6, "n.º 2 do artigo 63.º do EBF", 0, 1)
    
    pdf.ln(15)
    pdf.set_font(base_font, '', 10)
    pdf.cell(0, 10, "Respeitosos cumprimentos", 0, 1)
    
    # --- SALVAMENTO ---
    filename = f"recibo_{transaction.id}_{transaction.date.strftime('%Y%m%d')}.pdf"
    
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads')
    if not os.path.isabs(upload_folder):
        upload_folder = os.path.join(current_app.root_path, 'static/uploads')
    
    receipts_dir = os.path.join(upload_folder, 'receipts')
    os.makedirs(receipts_dir, exist_ok=True)
    
    filepath = os.path.join(receipts_dir, filename)
    pdf.output(filepath)
    
    return filename