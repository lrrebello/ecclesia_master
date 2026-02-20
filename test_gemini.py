import os
import io
import time
import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

def test_gemini_with_pdf():
    print("=== TESTE GOOGLE GEMINI COM PDF (História da Criação) ===")
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        print("ERRO: GEMINI_API_KEY não encontrada no .env")
        return

    client = genai.Client(api_key=api_key)

    pdf_url = "https://bibleforchildren.org/PDFs/portuguese/01_When_God_Made_Everything_Portuguese.pdf"
    
    print(f"\nBaixando PDF de: {pdf_url}")
    try:
        response = httpx.get(pdf_url, timeout=30)
        response.raise_for_status()
        pdf_content = response.content
        pdf_bytes = io.BytesIO(pdf_content)
        print(f"Download concluído! Tamanho: {len(pdf_content) / 1024:.1f} KB")
    except Exception as e:
        print(f"Erro ao baixar PDF: {str(e)}")
        return

    # Upload via Files API (já funcionou no teu run anterior)
    uploaded_file = None
    file_part = None
    print("\nFazendo upload para o Gemini Files API...")
    try:
        uploaded_file = client.files.upload(
            file=pdf_bytes,
            config=dict(
                mime_type="application/pdf",
                display_name="01_When_God_Made_Everything_Portuguese.pdf"
            )
        )
        print(f"Upload concluído! URI: {uploaded_file.uri}")
        print(f"Nome: {uploaded_file.name} | Estado: {uploaded_file.state}")
        
        time.sleep(5)  # Tempo para indexação
        
        file_part = types.Part(
            file_data=types.FileData(
                file_uri=uploaded_file.uri,
                mime_type="application/pdf"
            )
        )
        print("Usando Files API (upload separado)")
    
    except Exception as e:
        print(f"Erro no upload Files API: {str(e)}")
        print("Tentando modo inline...")
        # Fallback inline
        file_part = types.Part(
            inline_data=types.Blob(
                data=pdf_content,
                mime_type="application/pdf"
            )
        )
        print("Usando modo inline (PDF enviado diretamente)")

    # Prompt
    prompt = """
    Você leu a história bíblica infantil "Quando Deus Criou Todas as Coisas" (baseada em Gênesis 1-2).
    Gere exatamente 7 questões de compreensão para crianças (nível ensino fundamental inicial), 
    baseadas apenas no conteúdo da história fornecida no PDF.

    Cada questão deve ser de múltipla escolha com:
    - 4 alternativas (A, B, C, D)
    - Apenas UMA correta
    - Inclua a resposta correta no final de cada questão, no formato: RESPOSTA CORRETA: X

    As questões devem cobrir diferentes partes da criação (dias 1 a 7, homem e mulher, descanso, etc.).
    Numere as questões de 1 a 7.
    Responda apenas com as 7 questões, sem introdução ou conclusão extra.
    """

    print("\nGerando 7 questões com o modelo...")
    models_to_try = [
        'gemini-2.5-flash',
        'gemini-2.5-flash-latest',
        'gemini-2.5-pro',
    ]

    success = False
    for model_name in models_to_try:
        print(f"\nTentando com {model_name}...")
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    file_part,
                    types.Part(text=prompt)  # ← Correção aqui: usa keyword 'text=' ou Part(text=...)
                ],
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=1500,
                )
            )
            
            print(f"\n--- SUCESSO COM {model_name}! ---")
            print("\nQuestões geradas:\n")
            print(response.text.strip())
            
            if hasattr(response, 'usage_metadata'):
                print(f"\nTokens: Prompt {response.usage_metadata.prompt_token_count} + Gerados {response.usage_metadata.candidates_token_count}")
            
            success = True
            break
        
        except Exception as e:
            print(f"Falha com {model_name}: {str(e).splitlines()[0]}")

    if not success:
        print("\n!!! TODOS OS MODELOS FALHARAM !!!")
        print("Dicas:")
        print("- Confirma pip show google-genai → deve ser versão recente (2025+). Se não, pip install --upgrade google-genai")
        print("- Testa no https://aistudio.google.com: upload o PDF manualmente e gera com o prompt para ver se a chave/modelo suporta PDF.")
        print("- Alternativa simples: usa contents=[prompt, file_part] se o SDK converter auto (mas com Part correto).")

if __name__ == "__main__":
    test_gemini_with_pdf()