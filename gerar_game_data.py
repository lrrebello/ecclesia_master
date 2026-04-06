#!/usr/bin/env python3
"""
Script para gerar game_data (palavras para os jogos) para histórias existentes
Uso: python3 gerar_game_data.py
"""

import os
import sys
import json

# Adicionar o diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.core.models import db, BibleStory
from app.utils.gemini_service import generate_questions

app = create_app()

def gerar_game_data():
    """Gera game_data para histórias que não têm ou estão vazias"""
    
    with app.app_context():
        # Buscar histórias sem game_data ou com game_data vazio
        stories = BibleStory.query.filter(
            db.or_(
                BibleStory.game_data.is_(None),
                BibleStory.game_data == '',
                BibleStory.game_data == '[]',
                BibleStory.game_data == 'null'
            )
        ).all()
        
        if not stories:
            print("✅ Todas as histórias já têm game_data!")
            return
        
        print(f"📚 Encontradas {len(stories)} histórias sem game_data\n")
        
        for i, story in enumerate(stories, 1):
            print(f"[{i}/{len(stories)}] Processando: {story.title}")
            
            try:
                # Tentar gerar palavras via IA
                if story.content and len(story.content) > 50:
                    try:
                        result = generate_questions(story.content, type='kids', count=5)
                        if result and "game_words" in result and result["game_words"]:
                            # Usar as palavras geradas pela IA
                            game_words = result["game_words"]
                            story.game_data = json.dumps(game_words)
                            print(f"  ✅ Gerado via IA: {len(game_words)} palavras")
                        else:
                            raise Exception("IA não retornou palavras")
                    except Exception as e:
                        print(f"  ⚠️ Erro na IA: {e}")
                        # Fallback: usar palavras do título
                        game_words = extrair_palavras_do_titulo(story.title)
                        story.game_data = json.dumps(game_words)
                        print(f"  📝 Usando palavras do título: {game_words}")
                else:
                    # Conteúdo insuficiente, usar palavras do título
                    game_words = extrair_palavras_do_titulo(story.title)
                    story.game_data = json.dumps(game_words)
                    print(f"  📝 Conteúdo curto, usando título: {game_words}")
                
                db.session.commit()
                
            except Exception as e:
                print(f"  ❌ Erro: {e}")
                # Palavras padrão como último recurso
                palavras_padrao = ["BÍBLIA", "DEUS", "JESUS", "AMOR", "FÉ"]
                story.game_data = json.dumps(palavras_padrao)
                db.session.commit()
                print(f"  🔄 Usando palavras padrão: {palavras_padrao}")
        
        print("\n" + "="*50)
        print("✅ Processamento concluído!")
        
        # Mostrar resumo
        total = BibleStory.query.count()
        com_game_data = BibleStory.query.filter(BibleStory.game_data.isnot(None)).count()
        print(f"📊 Total de histórias: {total}")
        print(f"📊 Com game_data: {com_game_data}")
        print(f"📊 Sem game_data: {total - com_game_data}")

def extrair_palavras_do_titulo(titulo):
    """Extrai palavras-chave do título da história"""
    # Palavras para ignorar
    ignorar = ['DE', 'DA', 'DO', 'E', 'A', 'O', 'AS', 'OS', 'UM', 'UMA', 'COM', 'POR', 'PARA']
    
    # Separar palavras e converter para maiúsculas
    palavras = titulo.upper().split()
    
    # Filtrar palavras com 3+ letras e que não estão na lista de ignorar
    palavras_filtradas = []
    for p in palavras:
        # Remover pontuação
        p = p.strip('.,;:!?')
        if len(p) >= 3 and p not in ignorar:
            palavras_filtradas.append(p)
    
    # Se não sobrou nenhuma, adicionar palavras padrão
    if not palavras_filtradas:
        palavras_filtradas = ["BÍBLIA", "DEUS", "JESUS", "AMOR", "FÉ"]
    
    return palavras_filtradas[:10]  # Limitar a 10 palavras

def gerar_game_data_para_historia_especifica(historia_id):
    """Gera game_data para uma história específica"""
    with app.app_context():
        story = BibleStory.query.get(historia_id)
        if not story:
            print(f"❌ História com ID {historia_id} não encontrada!")
            return
        
        print(f"📚 Processando: {story.title}")
        
        try:
            if story.content and len(story.content) > 50:
                try:
                    result = generate_questions(story.content, type='kids', count=5)
                    if result and "game_words" in result and result["game_words"]:
                        game_words = result["game_words"]
                        story.game_data = json.dumps(game_words)
                        print(f"  ✅ Gerado via IA: {len(game_words)} palavras")
                    else:
                        raise Exception("IA não retornou palavras")
                except Exception as e:
                    print(f"  ⚠️ Erro na IA: {e}")
                    game_words = extrair_palavras_do_titulo(story.title)
                    story.game_data = json.dumps(game_words)
                    print(f"  📝 Usando palavras do título: {game_words}")
            else:
                game_words = extrair_palavras_do_titulo(story.title)
                story.game_data = json.dumps(game_words)
                print(f"  📝 Usando palavras do título: {game_words}")
            
            db.session.commit()
            print("  ✅ Salvo com sucesso!")
            
        except Exception as e:
            print(f"  ❌ Erro: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Gerar game_data para histórias bíblicas')
    parser.add_argument('--id', type=int, help='ID específico de uma história')
    parser.add_argument('--check', action='store_true', help='Apenas verificar quais histórias não têm game_data')
    
    args = parser.parse_args()
    
    if args.id:
        # Gerar para uma história específica
        gerar_game_data_para_historia_especifica(args.id)
    elif args.check:
        # Apenas verificar
        with app.app_context():
            stories = BibleStory.query.all()
            sem_game_data = []
            for s in stories:
                if not s.game_data or s.game_data == '' or s.game_data == '[]':
                    sem_game_data.append(s)
            
            print(f"📊 Total de histórias: {len(stories)}")
            print(f"📊 Com game_data: {len(stories) - len(sem_game_data)}")
            print(f"📊 Sem game_data: {len(sem_game_data)}")
            
            if sem_game_data:
                print("\n📚 Histórias sem game_data:")
                for s in sem_game_data:
                    print(f"  - ID {s.id}: {s.title}")
    else:
        # Gerar para todas
        gerar_game_data()