# app/utils/pdf_modelo25.py
import fitz  # PyMuPDF
import os
import math
from datetime import datetime
from flask import current_app

def fill_modelo25_pdf(data, output_filename=None):
    """
    Preenche o Modelo 25 oficial, gerando múltiplas declarações se necessário.
    
    Args:
        data: Dicionário com os dados
        output_filename: Nome base do arquivo (opcional)
    
    Returns:
        Se houver apenas um lote: string com o caminho do arquivo
        Se houver múltiplos lotes: lista de strings com os caminhos dos arquivos
    """
    template_path = os.path.join(current_app.root_path, 'static', 'templates_fiscais', 'MOD_25.pdf')    

    if not os.path.exists(template_path):
        print("PDF oficial não encontrado! Coloque em static/templates_fiscais/MOD_25.pdf")
        return None
    
    doc = fitz.open(template_path)
    
    # Funções auxiliares
    def clean_nif(nif):
        if not nif:
            return ''
        return ''.join(c for c in str(nif) if c.isdigit())
    
    def format_valor(valor):
        return f"{valor:.2f}".replace('.', ',')

    # Configurações
    max_linhas = 18
    todas_operacoes = data.get('operacoes', [])
    total_registros = len(todas_operacoes)
    total_lotes = max(1, math.ceil(total_registros / max_linhas))
    
    arquivos_gerados = []
    
    # Gera cada lote
    for lote_num in range(total_lotes):
        # Seleciona as operações deste lote
        inicio = lote_num * max_linhas
        fim = min(inicio + max_linhas, total_registros)
        lote_operacoes = todas_operacoes[inicio:fim]
        
        # Determina o tipo de declaração
        if lote_num == 0:
            tipo_declaracao = "01"  # Primeira
            sufixo = ""
        else:
            tipo_declaracao = "02"  # Substituição
            sufixo = f"_parte{lote_num+1}"
        
        # Cria um novo documento para este lote
        lote_doc = fitz.open()
        lote_doc.insert_pdf(doc, from_page=0, to_page=0)
        page = lote_doc[0]
        
        # Fonte
        font = "helv"
        
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
        
        # 2. ANO - COM ESPAÇAMENTO AJUSTADO
        x_ano = 187
        y_ano = 172
        ano_texto = str(data.get('ano', datetime.now().year))[-4:]
        
        # Desenha cada dígito do ano individualmente para melhor espaçamento
        x_ano_inicio = x_ano
        espacamento_ano = 13  # Aumentei o espaçamento entre dígitos do ano
        for i, digito in enumerate(ano_texto):
            x_pos_ano = x_ano_inicio + (i * espacamento_ano)
            page.insert_text((x_pos_ano, y_ano-6), digito, 
                           fontsize=11, fontname=font)
        
        # 3. TIPO DE DECLARAÇÃO
        # Ajuste estas coordenadas conforme necessário baseado no seu template
        if tipo_declaracao == "01":
            # Marca "Primeira" - Quadrado 01
            page.insert_text((507, 160), "X", fontsize=12, fontname=font)
        else:
            # Marca "Substituição" - Quadrado 02
            page.insert_text((507, 188), "X", fontsize=12, fontname=font)
        
        # 4. TABELA DE DOAÇÕES
        # NIF doador (x:44 até 165, y:260)
        x_nif_doador_inicio = 48
        espacamento_doador = 13.44  # 121px / 9 dígitos
        y_primeira_linha = 265
        y_segunda_linha = 285
        line_height = y_segunda_linha - y_primeira_linha  # 20 pixels
        
        x_codigo = 238
        x_valor = 478
        largura_campo_valor = 72
        
        # Preenche dados da tabela (apenas as operações deste lote)
        for i, op in enumerate(lote_operacoes):
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
        
        # 5. CAMPO SOMA (total deste lote)
        y_total = 731
        total_lote = sum(op.get('valor', 0) for op in lote_operacoes)
        total_formatado = format_valor(total_lote)
        text_width_total = fitz.get_text_length(total_formatado, fontname=font, fontsize=11)
        x_total_ajustado = x_valor + (largura_campo_valor - text_width_total)
        page.insert_text((x_total_ajustado, y_total-6), total_formatado, 
                        fontsize=11, fontname=font)
        
        # 6. CONTABILISTA CERTIFICADO
        y_cont = 815
        x_cont_inicio = 44
        
        if data.get('nif_contabilista'):
            nif_cont = clean_nif(data.get('nif_contabilista', ''))
            for i, digito in enumerate(nif_cont[:9]):
                if digito.isdigit():
                    x_pos = x_cont_inicio + (i * espacamento_declarante)
                    page.insert_text((x_pos, y_cont-6), digito, fontsize=10, fontname=font)

        # Salvar PDF deste lote
        nif_clean = clean_nif(data.get('nif_declarante', 'sem_nif'))
        ano = data.get('ano', 'ano')
        
        if output_filename:
            # Se forneceu nome base, adapta para cada lote
            base, ext = os.path.splitext(output_filename)
            filename = f"{base}{sufixo}{ext}"
        else:
            filename = f"Modelo25_{nif_clean}_{ano}{sufixo}.pdf"
        
        output_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'receipts', filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        lote_doc.save(output_path)
        lote_doc.close()
        arquivos_gerados.append(output_path)
    
    doc.close()
    
    # Log informativo
    if total_lotes > 1:
        print(f"Geradas {total_lotes} declarações Modelo 25 para {total_registros} doações")
    
    # Retorna string se for único arquivo, lista se múltiplos
    if len(arquivos_gerados) == 1:
        return arquivos_gerados[0]
    else:
        return arquivos_gerados