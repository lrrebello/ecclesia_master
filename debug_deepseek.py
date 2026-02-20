import os
from dotenv import load_dotenv
import json
from openai import OpenAI

# NUNCO COLOQUE A CHAVE DIRETO NO CÓDIGO!
# Use variável de ambiente
DEEPSEEK_API_KEY = "sk-bdf61fb071144d5baccacd98b2341963"
BASE_URL = "https://api.deepseek.com"

if not DEEPSEEK_API_KEY:
    raise ValueError("❌ ERRO: Defina a variável DEEPSEEK_API_KEY no ambiente!")

def test_deepseek_communication():
    print("=== TESTE DE COMUNICAÇÃO DEEPSEEK ===")
    print(f"URL: {BASE_URL}")
    print(f"Chave configurada: {'✅ Sim' if DEEPSEEK_API_KEY else '❌ Não'}")
    
    # Mostra apenas os primeiros caracteres para confirmar (seguro)
    print(f"Chave (início): {DEEPSEEK_API_KEY[:5]}...")
    
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=BASE_URL)
    
    # Texto de teste curto
    test_content = "A história de Davi e Golias ensina sobre coragem e confiança em Deus."
    
    system_prompt = "Você é um educador infantil especializado em criar atividades bíblicas divertidas."
    user_prompt = f"""
    Com base neste conteúdo bíblico infantil:
    {test_content}
    
    Crie 3 perguntas de múltipla escolha para crianças.
    Responda APENAS em formato JSON seguindo esta estrutura:
    {{
        "questions": [
            {{
                "question": "Texto da pergunta",
                "options": {{"A": "Opção A", "B": "Opção B", "C": "Opção C"}},
                "correct_option": "A",
                "explanation": "Explicação curta"
            }}
        ]
    }}
    """

    print("\n📤 Enviando requisição...")
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            response_format={'type': 'json_object'}
        )
        
        print("\n✅ SUCESSO! Resposta recebida:")
        print("-" * 40)
        
        # Tenta parsear o JSON para validar
        resposta_json = json.loads(response.choices[0].message.content)
        print(json.dumps(resposta_json, indent=2, ensure_ascii=False))
        
        print("-" * 40)
        print(f"Tokens usados (aproximado): {response.usage.total_tokens}")
        
    except Exception as e:
        print("\n❌ ERRO NA COMUNICAÇÃO")
        print(f"Tipo do erro: {type(e).__name__}")
        print(f"Mensagem: {str(e)}")
        
        # Análise específica de erros comuns
        if "402" in str(e) or "Insufficient Balance" in str(e):
            print("\n💡 DICA: Saldo insuficiente! Verifique:")
            print("   1. Acesse: https://platform.deepseek.com/balance")
            print("   2. Usuários novos ganham 14 yuans de crédito")
            print("   3. Se acabou, é necessário recarga (mínimo R$10)")
        elif "401" in str(e):
            print("\n💡 DICA: Chave inválida ou revogada!")
            print("   Gere uma nova chave em: https://platform.deepseek.com/api_keys")
        elif "404" in str(e):
            print("\n💡 DICA: URL incorreta! Use: https://api.deepseek.com")
        else:
            print("\n💡 DICA: Verifique sua internet e firewall")

if __name__ == "__main__":
    test_deepseek_communication()