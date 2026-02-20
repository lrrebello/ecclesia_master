# app/utils/pdf_modelo25.py
import fitz  # PyMuPDF
import os
from datetime import datetime
from flask import current_app

def fill_modelo25_pdf(data, output_filename=None):
    """
    Preenche o Modelo 25 oficial sobrepondo texto na página 3.
    data = {
        'nif_declarante': '123456789',
        'nome_declarante': 'Igreja Exemplo',
        'ano': '2025',
        'operacoes': [
            {'nif': '987654321', 'nome': 'Doador ABC', 'codigo': '01', 'valor': 1500.00},
            # mais linhas...
        ],
        # outros campos da página 3 (se precisar)
    }
    """
    template_path = os.path.join(current_app.root_path, 'static', 'templates_fiscais', 'MOD_25.pdf')    

    if not os.path.exists(template_path):
        print("PDF oficial não encontrado! Coloque em static/templates_fiscais/MOD_25.pdf")
        return None
    
    doc = fitz.open(template_path)
    page = doc[0]  # página 3 (índice 2)

    # Fonte e tamanho (aproximado do oficial)
    font = "helv"
    size = 10

    # Cabeçalho
    page.insert_text((50, 168), data.get('nif_declarante', ''), fontsize=13, fontname="helv")  # NIF declarante
    #page.insert_text((100, 168), data.get('nome_declarante', ''), fontsize=10, fontname="helv")  # Nome
    page.insert_text((200, 168), str(data.get('ano', datetime.now().year)), fontsize=13, fontname="helv")  # Ano

# Primeira linha da tabela (ajusta y para cada linha)
    y_start = 260  # altura aproximada da primeira linha da tabela
    line_height = 18
    for i, op in enumerate(data.get('operacoes', [])):
        y = y_start - (i * line_height)
        page.insert_text((50, y), op.get('nif', ''), fontsize=13, fontname="helv")
        #page.insert_text((160, y), op.get('nome', ''), fontsize=9, fontname="helv")
        page.insert_text((200, y), op.get('codigo', '01'), fontsize=13, fontname="helv")
        page.insert_text((430, y), f"{op.get('valor', 0):,.2f}", fontsize=13, fontname="helv")
            
    total = sum(op.get('valor', 0) for op in data.get('operacoes', []))
    page.insert_text((430, 780 - (len(data.get('operacoes', [])) * line_height) - 20), f"   {total:,.2f}", fontsize=13, fontname="helv")

    if not output_filename:
            output_filename = f"Modelo25_{data.get('nif_declarante', 'sem_nif')}_{data.get('ano', 'ano')}.pdf"
        
    output_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'receipts', output_filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    
    doc.save(output_path)
    doc.close()    
        
    return output_path