from datetime import datetime, timedelta
from app import create_app
from app.core.models import db, Devotional

app = create_app()

def seed_devotionals():
    with app.app_context():
        start_date = datetime(2026, 1, 1).date()
        end_date = datetime(2026, 12, 31).date()
        current_date = start_date
        
        # Exemplos reais em português (inspirados em Pão Diário, Palavra Viva, etc.)
        # Você pode adicionar mais ou substituir por conteúdo real depois
        examples = [
            {"title": "A Paz de Deus", "verse": "Filipenses 4:7", "content": "A paz de Deus, que excede todo entendimento, guardará os vossos corações e os vossos pensamentos em Cristo Jesus."},
            {"title": "Confiança no Senhor", "verse": "Provérbios 3:5-6", "content": "Confia no Senhor de todo o teu coração e não te estribes no teu próprio entendimento."},
            {"title": "O Amor de Deus", "verse": "João 3:16", "content": "Porque Deus amou o mundo de tal maneira que deu o seu Filho unigênito..."},
            {"title": "Força na Fraqueza", "verse": "2 Coríntios 12:9", "content": "A minha graça te basta, porque o meu poder se aperfeiçoa na fraqueza."},
            {"title": "Caminho de Vida", "verse": "Salmos 16:11", "content": "Tu me mostrarás a vereda da vida; na tua presença há plenitude de alegria."},
            # Adicione mais se quiser (ou deixe ciclar)
        ]
        
        count = 0
        while current_date <= end_date:
            existing = Devotional.query.filter_by(date=current_date).first()
            if not existing:
                example = examples[count % len(examples)]  # Cicla pelos exemplos
                new_dev = Devotional(
                    title=example["title"],
                    content=example["content"],
                    verse=example["verse"],
                    date=current_date,
                    church_id=1  # Ajuste para o ID da sede ou deixe None se for geral
                )
                db.session.add(new_dev)
                count += 1
            current_date += timedelta(days=1)
        
        db.session.commit()
        print(f"{count} devocionais adicionados com sucesso (2026)!")

if __name__ == '__main__':
    seed_devotionals()