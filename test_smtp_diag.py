import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# Configurações (Baseadas no seu .env)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "lrrebello@gmail.com"
SENDER_PASSWORD = "dvho ecfq tikh ewpt" # Senha de app fornecida
RECEIVER_EMAIL = "lrrebello@gmail.com" # Teste enviando para você mesmo

def test_smtp():
    print(f"--- Iniciando Diagnóstico de E-mail ---")
    print(f"Conectando a {SMTP_SERVER}:{SMTP_PORT}...")
    
    message = MIMEMultipart("alternative")
    message["Subject"] = "Teste de Diagnóstico Ecclesia Master"
    message["From"] = SENDER_EMAIL
    message["To"] = RECEIVER_EMAIL
    
    text = "Se você recebeu este e-mail, a conexão SMTP está funcionando corretamente!"
    part1 = MIMEText(text, "plain")
    message.attach(part1)

    context = ssl.create_default_context()
    
    try:
        # Tenta conectar
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.set_debuglevel(1) # Ativa logs detalhados
        
        print("Enviando comando STARTTLS...")
        server.starttls(context=context)
        
        print("Tentando fazer login...")
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        
        print("Enviando e-mail de teste...")
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message.as_string())
        
        print("\n✓ SUCESSO: O e-mail foi enviado com sucesso!")
        
    except Exception as e:
        print(f"\n✗ ERRO DETECTADO: {str(e)}")
        print("\nPossíveis causas:")
        if "Authentication failed" in str(e) or "Username and Password not accepted" in str(e):
            print("- A Senha de App pode estar incorreta ou foi revogada.")
            print("- Verifique se não há espaços extras na senha.")
        elif "Connection refused" in str(e) or "Timeout" in str(e):
            print("- O seu provedor de internet ou firewall pode estar bloqueando a porta 587.")
        else:
            print("- Verifique se a Verificação em Duas Etapas continua ativa na sua conta Google.")
    finally:
        try:
            server.quit()
        except:
            pass

if __name__ == "__main__":
    test_smtp()
