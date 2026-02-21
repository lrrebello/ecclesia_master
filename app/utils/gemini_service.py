import os
import json
import time
from google import genai
from google.genai import types
from flask import current_app
from dotenv import load_dotenv

load_dotenv()

def get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)

def generate_questions(content_or_path, type='adult', count=7, is_file=False):
    client = get_gemini_client()
    if not client:
        return {"error": "GEMINI_API_KEY não configurada no ambiente."}

    # Modelo recomendado para 2026
    model_name = 'gemini-2.5-flash'
    contents = []
    
    # Tempo de espera para indexação de arquivos (reduzido para 2s)
    indexing_wait = 2

    # Preparar o conteúdo
    text_content = ""
    if is_file and os.path.exists(content_or_path):
        try:
            ext = os.path.splitext(content_or_path)[1].lower()
            mime_type = "application/pdf"
            if ext == ".docx": mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            elif ext == ".pptx": mime_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            elif ext == ".txt": mime_type = "text/plain"

            # Upload do arquivo
            uploaded_file = client.files.upload(
                file=content_or_path,
                config=types.UploadFileConfig(mime_type=mime_type)
            )
            
            time.sleep(indexing_wait)
            
            contents.append(types.Part(
                file_data=types.FileData(
                    file_uri=uploaded_file.uri,
                    mime_type=mime_type
                )
            ))
        except Exception as e:
            current_app.logger.error(f"Erro no upload Gemini: {e}")
            # Fallback: extrair texto localmente
            try:
                from .text_extractor import extract_text
                text_content = extract_text(content_or_path)
            except Exception as extract_err:
                return {"error": f"Falha no processamento do arquivo: {str(extract_err)}"}
    else:
        # Conteúdo direto como texto
        text_content = content_or_path[:15000]  # limite de caracteres

    # Se tiver texto extraído ou direto, adiciona como Part de texto
    if text_content:
        contents.append(types.Part(text=text_content))

    # Montar o prompt correto baseado no tipo
    if type == 'kids':
        prompt_text = f"""
        Você é um educador infantil especializado em criar atividades bíblicas divertidas.
        Com base no conteúdo fornecido:
        
        1. Crie {count} perguntas de múltipla escolha para crianças de 5 a 10 anos.
        Para cada pergunta, forneça 3 opções (A, B, C).
        Indique a resposta correta e uma breve explicação alegre.

        2. Extraia 12 palavras-chave importantes da história para jogos de Caça-Palavras e Palavras Cruzadas.
        As palavras devem ser substantivos simples (sem espaços ou hífens). Para cada palavra, forneça uma dica curta.

        Responda APENAS em formato JSON seguindo EXATAMENTE esta estrutura:
        {{
            "questions": [
                {{
                    "question": "Texto da pergunta",
                    "options": {{
                        "A": "Opção A",
                        "B": "Opção B",
                        "C": "Opção C"
                    }},
                    "correct_option": "A",
                    "explanation": "Explicação curta"
                }}
            ],
            "game_words": [
                {{ "word": "PALAVRA", "hint": "Dica da palavra" }}
            ]
        }}
        """
    else:  # adult
        prompt_text = f"""
        Gere {count} questões de múltipla escolha baseadas no seguinte conteúdo: {text_content}.
        
        Para cada questão:
        - Crie uma pergunta clara e relevante.
        - Gere 4 opções (A, B, C, D).
        - A resposta correta deve ser variada e aleatória entre A, B, C e D (NÃO coloque sempre na A ou na primeira opção).
        - Inclua uma explicação breve para a resposta correta.

        Responda APENAS em formato JSON estrito, sem texto adicional:
        {{
            "questions": [
                {{
                    "question": "Texto da pergunta",
                    "options": {{
                        "A": "Opção A",
                        "B": "Opção B",
                        "C": "Opção C",
                        "D": "Opção D"
                    }},
                    "correct_option": "B",  // exemplo - deve variar!
                    "explanation": "Explicação curta"
                }}
            ]
        }}
        """

    # Adiciona o prompt como última parte
    contents.append(types.Part(text=prompt_text))

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                temperature=0.3,
                http_options={'timeout': 25000}  # 25 segundos
            )
        )
        
        if not response or not response.text:
            return {"error": "A IA não retornou uma resposta válida a tempo."}
        
        ai_text = response.text.strip()
        
        # Limpa formatação markdown se vier
        if ai_text.startswith("```json"):
            ai_text = ai_text.split("```json")[1].split("```")[0].strip()
        
        ai_data = json.loads(ai_text)
        return ai_data
    
    except Exception as e:
        current_app.logger.error(f"Erro na API do Gemini: {str(e)}")
        return {"error": f"Falha na geração de conteúdo: {str(e)}"}