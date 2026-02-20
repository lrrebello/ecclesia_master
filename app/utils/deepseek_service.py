import os
import json
import time
import io
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

def get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)

def generate_questions(content_or_path, type='adult', count=10, is_file=False):
    client = get_gemini_client()
    if not client:
        return {"error": "GEMINI_API_KEY não configurada no ambiente."}

    model_name = 'gemini-2.5-flash'
    contents = []

    # Se for um arquivo (PDF, DOCX, etc), fazemos o upload para a Files API do Gemini
    if is_file and os.path.exists(content_or_path):
        try:
            # Determinar o mime_type
            ext = os.path.splitext(content_or_path)[1].lower()
            mime_type = "application/pdf"
            if ext == ".docx": mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            elif ext == ".pptx": mime_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            elif ext == ".txt": mime_type = "text/plain"

            # Correção da sintaxe de upload para o SDK google-genai
            # O parâmetro correto é 'file' (que aceita path ou file-like object)
            uploaded_file = client.files.upload(
                file=content_or_path,
                config=types.UploadFileConfig(mime_type=mime_type)
            )
            
            # Aguarda indexação rápida
            time.sleep(5)
            
            # Adiciona a referência do arquivo ao conteúdo
            contents.append(types.Part.from_uri(
                file_uri=uploaded_file.uri,
                mime_type=mime_type
            ))
        except Exception as e:
            print(f"Erro no upload para Gemini Files API: {e}")
            # Se falhar o upload, tentamos extrair o texto localmente como fallback
            try:
                from .text_extractor import extract_text
                text = extract_text(content_or_path)
                contents.append(types.Part.from_text(text=text[:10000]))
            except Exception as e_ext:
                print(f"Erro no fallback de extração: {e_ext}")
                return {"error": f"Não foi possível processar o arquivo: {str(e)}"}
    else:
        # Se for apenas texto
        contents.append(types.Part.from_text(text=content_or_path[:10000]))

    # Configuração do Prompt
    if type == 'kids':
        system_instruction = "Você é um educador infantil especializado em criar atividades bíblicas divertidas."
        prompt_text = f"""
        {system_instruction}
        
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
    else:
        system_instruction = "Você é um teólogo e educador especializado em estudos bíblicos para adultos."
        prompt_text = f"""
        {system_instruction}
        
        Com base no conteúdo fornecido:
        
        Crie {count} perguntas de múltipla escolha para adultos.
        Para cada pergunta, forneça 4 opções (A, B, C, D).
        Indique a resposta correta e uma breve explicação/fonte de onde foi tirada no texto.
        
        Responda APENAS em formato JSON seguindo EXATAMENTE esta estrutura:
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
                    "correct_option": "A",
                    "explanation": "Explicação/Fonte"
                }}
            ]
        }}
        """

    contents.append(types.Part.from_text(text=prompt_text))

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                temperature=0.3
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Erro na API do Gemini: {e}")
        # Fallback para modelo 1.5 se o 2.5 falhar
        try:
            response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json'
                )
            )
            return json.loads(response.text)
        except Exception as e2:
            return {"error": f"Falha na comunicação com a IA: {str(e2)}"}
