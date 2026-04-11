import os
import json
import time
from google import genai
from google.genai import types
from flask import current_app
from dotenv import load_dotenv

load_dotenv()

def get_gemini_client(church_id=None):
    """Retorna cliente Gemini configurado com a chave da filial"""
    from app.core.models import Church
    
    api_key = None
    
    if church_id:
        church = Church.query.get(church_id)
        if church and church.gemini_api_key:
            api_key = church.gemini_api_key
    
    # Fallback para .env se não tiver configurado na filial
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        return None
    return genai.Client(api_key=api_key)

def split_content_for_ai(content, max_chars=5000):
    """Divide conteúdo grande em partes menores para processamento"""
    if not content or len(content) <= max_chars:
        return [content] if content else []
    
    parts = []
    current_part = ""
    
    # Tentar dividir por parágrafos
    paragraphs = content.split('\n\n')
    
    for para in paragraphs:
        if len(current_part) + len(para) > max_chars:
            if current_part:
                parts.append(current_part)
            current_part = para
        else:
            if current_part:
                current_part += '\n\n' + para
            else:
                current_part = para
    
    if current_part:
        parts.append(current_part)
    
    return parts

def extract_text_from_file(file_path):
    """Extrai texto de arquivos localmente (fallback)"""
    try:
        from .text_extractor import extract_text
        return extract_text(file_path)
    except Exception as e:
        current_app.logger.error(f"Erro no extract_text: {e}")
        return None

def generate_questions(content_or_path, type='adult', count=7, is_file=False, church_id=None):
    client = get_gemini_client(church_id=church_id)  # 🔥 CORRIGIDO
    if not client:
        return {"error": "GEMINI_API_KEY não configurada no ambiente."}

    model_name = 'gemini-2.5-flash'
    contents = []
    indexing_wait = 2
    text_content = ""

    # Processar arquivo
    if is_file and os.path.exists(content_or_path):
        try:
            ext = os.path.splitext(content_or_path)[1].lower()
            mime_type = "application/pdf"
            if ext == ".docx": 
                mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            elif ext == ".pptx": 
                mime_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            elif ext == ".txt": 
                mime_type = "text/plain"

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
            text_content = extract_text_from_file(content_or_path)
            if not text_content:
                return {"error": f"Falha no processamento do arquivo: {str(e)}"}
    else:
        text_content = content_or_path

    # Se texto for muito grande
    if text_content and len(text_content) > 8000:
        current_app.logger.info(f"Conteúdo grande ({len(text_content)} caracteres). Usando primeiros 6000 caracteres.")
        text_content = text_content[:6000]
        partial_note = "\n\n[Nota: O conteúdo original é muito extenso. As questões foram geradas com base na primeira parte do texto.]"
        text_content += partial_note

    if text_content:
        contents.append(types.Part(text=text_content))

    # Montar o prompt
    if type == 'kids':
        prompt_text = f"""
        Você é um educador infantil especializado em criar atividades bíblicas divertidas.
        Com base no conteúdo fornecido:
        
        1. Crie {count} perguntas de múltipla escolha para crianças de 5 a 10 anos.
        Para cada pergunta, forneça 3 opções (A, B, C).
        Indique a resposta correta e uma breve explicação alegre.
        DISTRIBUA A RESPOSTA CORRETA ALEATORIAMENTE ENTRE A, B e C (não coloque sempre em A).

        2. Extraia 8 palavras-chave importantes da história para jogos.
        As palavras devem ser substantivos simples (sem espaços).

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
                    "correct_option": "B",
                    "explanation": "Explicação curta"
                }}
            ],
            "game_words": ["PALAVRA1", "PALAVRA2", "PALAVRA3"]
        }}
        """
    else:
        prompt_text = f"""
        Gere {count} questões de múltipla escolha baseadas no seguinte conteúdo bíblico.
        
        REGRAS IMPORTANTES:
        - DISTRIBUA a resposta correta aleatoriamente entre A, B, C e D (NÃO coloque sempre em A)
        - As perguntas devem ser relevantes e baseadas APENAS no conteúdo fornecido
        - Cada questão deve ter 4 opções (A, B, C, D)
        - Inclua uma explicação breve para a resposta correta
        
        Responda APENAS em formato JSON, sem texto adicional:
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
                    "correct_option": "C",
                    "explanation": "Explicação curta"
                }}
            ]
        }}
        """

    contents.append(types.Part(text=prompt_text))

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                temperature=0.3,
                http_options={'timeout': 60000}
            )
        )
        
        if not response or not response.text:
            return {"error": "A IA não retornou uma resposta válida a tempo."}
        
        ai_text = response.text.strip()
        
        if ai_text.startswith("```json"):
            ai_text = ai_text.split("```json")[1].split("```")[0].strip()
        elif ai_text.startswith("```"):
            ai_text = ai_text.split("```")[1].split("```")[0].strip()
        
        ai_data = json.loads(ai_text)
        
        if type == 'kids' and 'game_words' not in ai_data:
            ai_data['game_words'] = []
        
        return ai_data
    
    except json.JSONDecodeError as e:
        current_app.logger.error(f"Erro ao decodificar JSON: {e}")
        return {"error": f"Resposta da IA não é JSON válido: {str(e)}"}
    
    except Exception as e:
        current_app.logger.error(f"Erro na API do Gemini: {str(e)}")
        return {"error": f"Falha na geração de conteúdo: {str(e)}"}