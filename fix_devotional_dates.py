from datetime import datetime, timedelta
from app import create_app
from app.core.models import db, Devotional

app = create_app()

def fix_devotional_dates():
    with app.app_context():
        # Pegue todos os devocionais
        devotionals = Devotional.query.all()
        if not devotionals:
            print("Nenhum devocional encontrado.")
            return
        
        # Comece a partir de hoje (ou uma data recente)
        start_date = datetime(2026, 2, 9).date()  # Data de hoje no seu teste
        count = 0
        
        for dev in devotionals:
            new_date = start_date + timedelta(days=count)
            dev.date = new_date
            count += 1
        
        db.session.commit()
        print(f"{len(devotionals)} datas corrigidas! O mais recente agora é {devotionals[-1].date}")

if __name__ == '__main__':
    fix_devotional_dates()