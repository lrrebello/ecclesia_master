from fpdf import FPDF
import os
from flask import current_app

class ReceiptPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'RECIBO DE CONTRIBUIÇÃO', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def generate_receipt(transaction):
    pdf = ReceiptPDF()
    pdf.add_page()
    pdf.set_font('Arial', '', 12)
    
    # Church Info
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f'Igreja: {transaction.church.name}', 0, 1)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, f'Endereço: {transaction.church.address}', 0, 1)
    pdf.ln(10)
    
    # Transaction Info
    pdf.cell(0, 10, f'Recebemos de: {transaction.user.name if transaction.user else "Doador Anônimo"}', 0, 1)
    pdf.cell(0, 10, f'A quantia de: R$ {transaction.amount:.2f}', 0, 1)
    pdf.cell(0, 10, f'Referente a: {transaction.category.capitalize()}', 0, 1)
    pdf.cell(0, 10, f'Data: {transaction.date.strftime("%d/%m/%Y")}', 0, 1)
    pdf.ln(20)
    
    # Signature
    pdf.line(10, pdf.get_y(), 100, pdf.get_y())
    pdf.cell(0, 10, 'Assinatura da Tesouraria', 0, 1)
    
    filename = f"recibo_{transaction.id}_{transaction.date.strftime('%Y%m%d')}.pdf"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], 'receipts', filename)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    pdf.output(filepath)
    return filename
