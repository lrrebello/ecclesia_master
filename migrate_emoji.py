#!/usr/bin/env python
# migrate_emoji_fixed.py - Popula o banco com emojis e palavras associadas

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.core.models import EmojiWord
from datetime import datetime

# ========== EMOJIS E SUAS PALAVRAS ASSOCIADAS (CORRIGIDO) ==========
emoji_data = {
    # 👑 COROA - Reis
    '👑': ['DAVI', 'REI', 'SALOMÃO', 'SALOMAO', 'COROA', 'JESUS REI', 'SOBERANO', 'MAJESTADE', 'TRONO', 'REALEZA'],
    
    # 🦁 LEÃO - Daniel
    '🦁': ['LEÃO', 'LEAO', 'DANIEL', 'CORAGEM', 'JUDEIA', 'FORÇA', 'PODER', 'JUDÁ', 'VALENTIA'],
    
    # ✝️ CRUZ - Jesus
    '✝️': ['JESUS', 'CRUZ', 'SALVAÇÃO', 'SALVACAO', 'CRISTO', 'CALVÁRIO', 'REDENÇÃO', 'REDENCAO', 'MESSIAS', 'SENHOR'],
    
    # 🙏 ORAÇÃO - Fé
    '🙏': ['ORAÇÃO', 'ORACAO', 'FÉ', 'FE', 'CLAMOR', 'INTERCESSÃO', 'INTERCESSAO', 'AGRADECIMENTO', 'SUPLICA', 'ADORAÇÃO', 'ADORACAO', 'JEJUM'],
    
    # 📖 BÍBLIA - Escrituras
    '📖': ['BÍBLIA', 'BIBLIA', 'ESCRITURAS', 'PALAVRA', 'SAGRADA', 'LIVRO', 'SALMOS', 'SALMO', 'EVANGELHO', 'APOCALIPSE'],
    
    # ⛰️ MONTANHA - Sinai
    '⛰️': ['MONTANHA', 'MONTE', 'SINAI', 'OLIVAIS', 'CARMELO', 'MORRO', 'COLINA'],
    
    # 💧 ÁGUA - Batismo
    '💧': ['ÁGUA', 'AGUA', 'BATISMO', 'RIO', 'BATIZAR', 'MANÁ', 'MANA'],
    
    # 🎣 PESCAR - Apóstolos
    '🎣': ['PESCAR', 'PESCADOR', 'REDES', 'REDE', 'PESCA', 'APÓSTOLOS', 'APOSTOLOS', 'PEDRO', 'ANDRÉ', 'TIAGO', 'JOÃO'],
    
    # 🚢 ARCA - Noé
    '🚢': ['ARCA', 'NOÉ', 'NOE', 'BARCO', 'NAU', 'DILÚVIO', 'DILUVIO', 'JONAS'],
    
    # ⚔️ ESPADA - Golias
    '⚔️': ['ESPADA', 'GUERRA', 'BATALHA', 'GOLIAS', 'GUERREIRO', 'JOSUÉ', 'JOSUE', 'GIDEÃO', 'GIDEAO'],
    
    # ⭐ ESTRELA - Belém
    '⭐': ['ESTRELA', 'BELÉM', 'BELEM', 'NATAL', 'REIS MAGOS', 'GUIDA'],
    
    # 🕊️ POMBA - Espírito Santo
    '🕊️': ['POMBA', 'PAZ', 'ESPÍRITO SANTO', 'ESPIRITO SANTO', 'PALOMA'],
    
    # 🐟 PEIXE - Jonas
    '🐟': ['PEIXE', 'JONAS', 'MULTIDÃO', 'MULTIDAO', 'BALEIA'],
    
    # 🔥 FOGO - Elias
    '🔥': ['FOGO', 'ELIAS', 'PENTECOSTES', 'FORNALHA', 'CHAMA'],
    
    # 💡 LUZ - Milagre
    '💡': ['LUZ', 'MILAGRE', 'SABEDORIA', 'REVELAÇÃO', 'REVELACAO', 'SAL', 'ILUMINAR'],
    
    # 🌊 MAR - Jordão
    '🌊': ['MAR', 'JORDÃO', 'JORDAO', 'MAR VERMELHO', 'ONDAS', 'ÁGUAS', 'AGUAS'],
    
    # 🌈 ARCO-ÍRIS - Aliança
    '🌈': ['ARCO-ÍRIS', 'ARCO IRIS', 'ESPERANÇA', 'ESPERANCA', 'PROMESSA', 'ALIANÇA', 'ALIANCA'],
    
    # 🛟 SALVAÇÃO - Resgate
    '🛟': ['SALVAÇÃO', 'SALVACAO', 'RESGATE', 'SALVADOR', 'SALVAR', 'LIVRAMENTO'],
    
    # 🏠 CASA - Lar
    '🏠': ['CASA', 'LAR', 'FAMÍLIA', 'FAMILIA', 'JERUSALÉM', 'JERUSALEM', 'BELÉM', 'BELEM', 'NAZARÉ', 'NAZARE'],
    
    # ⛪ IGREJA - Templo
    '⛪': ['IGREJA', 'TEMPLO', 'ADORAÇÃO', 'ADORACAO', 'CONGREGAÇÃO', 'CONGREGACAO', 'SANTUÁRIO'],
    
    # 🩺 CURA - Milagres
    '🩺': ['CURA', 'SAÚDE', 'SAUDE', 'DOENÇA', 'DOENCA', 'JESUS CURA', 'PARALÍTICO', 'PARALITICO', 'CIEGO', 'LEPROSO'],
    
    # 💀 MORTE - Ressurreição
    '💀': ['MORTE', 'RESSURREIÇÃO', 'RESSURREICAO', 'LÁZARO', 'LAZARO', 'PÁSCOA', 'PASCOA'],
    
    # 🌱 VIDA - Criação
    '🌱': ['VIDA', 'CRIAÇÃO', 'CRIACAO', 'JARDIM', 'PARAÍSO', 'PARAISO', 'SEMENTE', 'NASCER'],
    
    # ✨ DEUS - Glória
    '✨': ['DEUS', 'GLÓRIA', 'GLORIA', 'ANJO', 'ARCANJO', 'GABRIEL', 'MIGUEL', 'SERAFIM', 'QUERUBIM', 'PRESENÇA'],
    
    # 📜 MOISÉS - Lei
    '📜': ['MOISÉS', 'MOISES', 'TÁBUAS', 'TABUAS', 'LEI', 'MANDAMENTOS', 'PROFETA', 'PROFETAS', 'ROLO'],
    
    # 👼 ANJO - Gabriel
    '👼': ['ANJO', 'GABRIEL', 'MIGUEL', 'ANJOS', 'CELESTIAL', 'MENSAGEIRO', 'ANUNCIAÇÃO', 'ANUNCIACAO'],
    
    # ❤️ AMOR - Ágape
    '❤️': ['AMOR', 'ÁGAPE', 'AGAPE', 'MISERICÓRDIA', 'MISERICORDIA', 'GRAÇA', 'GRACA', 'COMPAIXÃO', 'COMPAIXAO'],
    
    # 🤝 AJUDA - Serviço
    '🤝': ['AJUDA', 'SERVIÇO', 'SERVICO', 'COMUNHÃO', 'COMUNHAO', 'PERDÃO', 'PERDAO', 'SOLIDARIEDADE'],
    
    # 🦅 ÁGUIA - João
    '🦅': ['ÁGUIA', 'AGUIA', 'JOÃO', 'JOAO', 'EVANGELISTA', 'ISAÍAS', 'ISAIAS', 'RENOVAR'],
    
    # 🐑 CORDEIRO - Jesus
    '🐑': ['CORDEIRO', 'OVELHA', 'PASTOR', 'BOM PASTOR', 'ABEL', 'SACRIFÍCIO', 'SACRIFICIO', 'REBANHO'],
    
    # 🏜️ DESERTO - Êxodo
    '🏜️': ['DESERTO', 'EGITO', 'ÊXODO', 'EXODO', 'PEREGRINAÇÃO', 'PEREGRINACAO', 'TENTAÇÃO', 'TENTACAO'],
    
    # 🔑 PEDRO - Chaves
    '🔑': ['PEDRO', 'CHAVE', 'REINO', 'PODER', 'AUTORIDADE', 'PORTA'],
    
    # 💪 SANSÃO - Força
    '💪': ['SANSÃO', 'SANSAO', 'FORÇA', 'CORAGEM', 'VALENTIA', 'DÉBORA', 'DEBORA'],
    
    # 👨 ADÃO - Homem
    '👨': ['ADÃO', 'ADAO', 'HOMEM', 'ABRAÃO', 'ABRAAM', 'JOSÉ', 'JOSE', 'JACÓ', 'JACO'],
    
    # 👩 EVA - Mulher
    '👩': ['EVA', 'MULHER', 'SARAH', 'SARA', 'RUTE', 'ESTER', 'MARIA', 'MARTA'],
    
    # 🌍 TERRA - Planeta
    '🌍': ['TERRA', 'MUNDO', 'CRIAÇÃO', 'CRIACAO'],
    
    # ☀️ SOL - Estrela
    '☀️': ['SOL', 'CLARIDADE', 'DIA'],
    
    # 🌙 LUA - Noite
    '🌙': ['LUA', 'NOITE'],
    
    # 🌳 ÉDEN - Jardim
    '🌳': ['ÉDEN', 'EDEN', 'JARDIM', 'ÁRVORE', 'ARVORE']
}

def migrate():
    app = create_app()
    with app.app_context():
        count = 0
        for emoji, words in emoji_data.items():
            new_emoji = EmojiWord(
                emoji=emoji,
                emoji_type='unicode',
                words=words,
                #created_by=1
            )
            db.session.add(new_emoji)
            count += 1
            print(f"✅ Adicionado: {emoji} → {len(words)} palavras")
        
        db.session.commit()
        print(f"\n🎉 Migração concluída! {count} emojis adicionados.")
        print(f"📊 Total de emojis no banco: {EmojiWord.query.count()}")

if __name__ == '__main__':
    migrate()