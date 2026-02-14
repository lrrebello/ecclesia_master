from datetime import datetime, timedelta
from app import create_app
from app.core.models import db, Devotional

app = create_app()

def fix_devotional_dates_safe():
    with app.app_context():
        # Pegar todos os devocionais ordenados pela data atual
        devotionals = Devotional.query.order_by(Devotional.date).all()
        if not devotionals:
            print("Nenhum devocional encontrado.")
            return
        
        # Data inicial desejada (hoje ou uma data recente)
        base_date = datetime(2026, 2, 9).date()  # Ajuste se quiser outra data inicial
        
        updated = 0
        for dev in devotionals:
            new_date = base_date
            # Encontra a próxima data livre
            while Devotional.query.filter_by(date=new_date).first():
                new_date += timedelta(days=1)
            
            if dev.date != new_date:
                dev.date = new_date
                updated += 1
        
        db.session.commit()
        print(f"{updated} datas corrigidas com sucesso!")
        if devotionals:
            latest = Devotional.query.order_by(Devotional.date.desc()).first()
            print(f"Data do mais recente agora: {latest.date}")
            print(f"Data de hoje: {datetime.utcnow().date()}")

if __name__ == '__main__':
    fix_devotional_dates_safe()