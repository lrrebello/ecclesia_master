# app/utils/email_utils.py
from flask import current_app, url_for
from app.core.models import Church, db
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import uuid


def send_email(church_id, to_email, subject, html_content, text_content=None):
    """
    Envia email usando as configurações SMTP da filial
    
    Args:
        church_id: ID da igreja (para pegar as configurações)
        to_email: Email do destinatário
        subject: Assunto do email
        html_content: Conteúdo HTML do email
        text_content: Conteúdo texto plano (opcional)
    
    Returns:
        (success, message)
    """
    church = Church.query.get(church_id)
    if not church:
        return False, "Igreja não encontrada"
    
    if not church.smtp_server or not church.smtp_user or not church.smtp_password:
        return False, "Configurações de email não configuradas para esta igreja"
    
    try:
        # Criar mensagem
        msg = MIMEMultipart('alternative')
        msg['From'] = church.email_from or church.smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Adicionar versão texto plano (fallback)
        if text_content:
            part_text = MIMEText(text_content, 'plain')
            msg.attach(part_text)
        
        # Adicionar versão HTML
        part_html = MIMEText(html_content, 'html')
        msg.attach(part_html)
        
        # Conectar e enviar
        if church.smtp_use_tls:
            server = smtplib.SMTP(church.smtp_server, church.smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(church.smtp_server, church.smtp_port)
        
        server.login(church.smtp_user, church.smtp_password)
        server.send_message(msg)
        server.quit()
        
        return True, "Email enviado com sucesso"
        
    except Exception as e:
        current_app.logger.error(f"Erro ao enviar email: {str(e)}")
        return False, str(e)


def send_verification_email_via_smtp(user):
    """Envia email de verificação usando SMTP da filial"""
    token = user.email_verification_token
    if not token:
        token = str(uuid.uuid4())
        user.email_verification_token = token
        db.session.commit()
    
    church = Church.query.get(user.church_id) if user.church_id else None
    church_name = church.name if church else "Ecclesia Master"
    
    verification_url = url_for('auth.verify_email', token=token, _external=True)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #4f46e5; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
            .header h1 {{ color: white; margin: 0; }}
            .content {{ padding: 30px; background: #f9fafb; }}
            .button {{ display: inline-block; background: #4f46e5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{church_name}</h1>
            </div>
            <div class="content">
                <h2>Olá {user.name}!</h2>
                <p>Bem-vindo ao Ecclesia Master! Ficamos muito felizes com seu interesse em se juntar a nós.</p>
                <p>Para ativar sua conta e começar a usar o sistema, clique no botão abaixo:</p>
                <p style="text-align: center;">
                    <a href="{verification_url}" class="button">Verificar meu e-mail</a>
                </p>
                <p>Se o botão não funcionar, copie e cole o link abaixo no seu navegador:</p>
                <p><a href="{verification_url}">{verification_url}</a></p>
                <p>Este link expira em 24 horas.</p>
                <p>Que Deus te abençoe ricamente!</p>
                <p>Atenciosamente,<br>Equipe {church_name}</p>
            </div>
            <div class="footer">
                <p>Este é um email automático, por favor não responda.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Olá {user.name}!
    
    Bem-vindo ao Ecclesia Master! Ficamos muito felizes com seu interesse em se juntar a nós.
    
    Para ativar sua conta, acesse o link abaixo:
    {verification_url}
    
    Este link expira em 24 horas.
    
    Que Deus te abençoe ricamente!
    
    Atenciosamente,
    Equipe {church_name}
    """
    
    return send_email(
        church_id=user.church_id,
        to_email=user.email,
        subject=f'Verifique seu e-mail - {church_name}',
        html_content=html_content,
        text_content=text_content
    )