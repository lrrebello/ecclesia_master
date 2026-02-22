import os
from app.core.models import db
from app import create_app
from sqlalchemy import text

app = create_app()

def migrate():
    with app.app_context():
        try:
            # Adicionar colunas para artes do cartão
            columns = [
                ("member_card_front", "VARCHAR(255)"),
                ("member_card_back", "VARCHAR(255)")
            ]
            
            for col_name, col_type in columns:
                try:
                    db.session.execute(text(f"ALTER TABLE church ADD COLUMN {col_name} {col_type}"))
                    db.session.commit()
                    print(f"Coluna {col_name} adicionada com sucesso.")
                except Exception as e:
                    db.session.rollback()
                    print(f"Erro ao adicionar {col_name} (pode já existir): {e}")
            
            print("Migração concluída!")
        except Exception as e:
            print(f"Erro geral na migração: {e}")

if __name__ == "__main__":
    migrate()
