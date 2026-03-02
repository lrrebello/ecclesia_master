# app/utils/pdf_modelo25.py
import fitz  # PyMuPDF
import os
from datetime import datetime
from flask import current_app

def fill_modelo25_pdf(data, output_filename=None):
    """
    Preenche o Modelo 25 oficial na primeira página do template.
    """
    template_path = os.path.join(current_app.root_path, 'static', 'templates_fiscais', 'MOD_25.pdf')    

    if not os.path.exists(template_path):
        print("PDF oficial não encontrado! Coloque em static/templates_fiscais/MOD_25.pdf")
        return None
    
    doc = fitz.open(template_path)
    page = doc[0]

    # Fonte
    font = "helv"
    
    # Funções auxiliares
    def clean_nif(nif):
        if not nif:
            return ''
        return ''.join(c for c in str(nif) if c.isdigit())
    
    def format_valor(valor):
        return f"{valor:.2f}".replace('.', ',')

    # === COORDENADAS CALIBRADAS ===
    
    # 1. NIF DO DECLARANTE (x:44 até 160, y:166)
    nif_declarante = clean_nif(data.get('nif_declarante', ''))
    x_nif_declarante_inicio = 48
    espacamento_declarante = 12.89  # 116px / 9 dígitos
    y_nif_declarante = 172
    
    # Preenche NIF declarante
    for i, digito in enumerate(nif_declarante[:9]):
        if digito.isdigit():
            x_pos = x_nif_declarante_inicio + (i * espacamento_declarante)
            page.insert_text((x_pos, y_nif_declarante-6), digito, 
                           fontsize=11, fontname=font)
    
    # 2. ANO
    x_ano = 187
    y_ano = 172
    page.insert_text((x_ano, y_ano-6), str(data.get('ano', datetime.now().year))[-4:], 
                    fontsize=11, fontname=font)
    
    # 3. TABELA DE DOAÇÕES
    # NIF doador (x:44 até 165, y:260)
    x_nif_doador_inicio = 48
    espacamento_doador = 13.44  # 121px / 9 dígitos
    y_primeira_linha = 265
    y_segunda_linha = 285
    line_height = y_segunda_linha - y_primeira_linha  # 20 pixels
    
    x_codigo = 238
    x_valor = 478
    largura_campo_valor = 72
    
    # Preenche dados da tabela
    operacoes = data.get('operacoes', [])[:18]
    for i, op in enumerate(operacoes):
        y = y_primeira_linha + (i * line_height)
        
        # NIF doador
        nif_doador = clean_nif(op.get('nif', ''))
        for j, digito in enumerate(nif_doador[:9]):
            if digito.isdigit():
                x_pos = x_nif_doador_inicio + (j * espacamento_doador)
                page.insert_text((x_pos, y-6), digito, fontsize=11, fontname=font)
        
        # Código do donativo (geralmente 01)
        codigo = op.get('codigo', '01')
        page.insert_text((x_codigo, y-6), codigo, fontsize=11, fontname=font)
        
        # Valor em numerário (alinhado à direita)
        valor = op.get('valor', 0)
        valor_formatado = format_valor(valor)
        text_width = fitz.get_text_length(valor_formatado, fontname=font, fontsize=12)
        x_valor_ajustado = x_valor + (largura_campo_valor - text_width)
        page.insert_text((x_valor_ajustado, y-6), valor_formatado, 
                        fontsize=10, fontname=font)
    
    # 4. CAMPO SOMA (total)
    y_total = 731
    total = sum(op.get('valor', 0) for op in operacoes)
    total_formatado = format_valor(total)
    text_width_total = fitz.get_text_length(total_formatado, fontname=font, fontsize=11)
    x_total_ajustado = x_valor + (largura_campo_valor - text_width_total)
    page.insert_text((x_total_ajustado, y_total-6), total_formatado, 
                    fontsize=11, fontname=font)
    
    # 5. CONTABILISTA CERTIFICADO
    y_cont = 815
    x_cont_inicio = 44
    
    if data.get('nif_contabilista'):
        nif_cont = clean_nif(data.get('nif_contabilista', ''))
        for i, digito in enumerate(nif_cont[:9]):
            if digito.isdigit():
                x_pos = x_cont_inicio + (i * espacamento_declarante)
                page.insert_text((x_pos, y_cont-6), digito, fontsize=10, fontname=font)

    # Salvar PDF
    output_doc = fitz.open()
    output_doc.insert_pdf(doc, from_page=0, to_page=0)
    
    if not output_filename:
        output_filename = f"Modelo25_{clean_nif(data.get('nif_declarante', 'sem_nif'))}_{data.get('ano', 'ano')}.pdf"
    
    output_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'receipts', output_filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    output_doc.save(output_path)
    output_doc.close()
    doc.close()
    
    return output_path