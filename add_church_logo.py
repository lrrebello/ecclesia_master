# add_church_logo.py
from sqlalchemy import text
from app.core.models import db
from app import create_app

app = create_app()

with app.app_context():
    # Executa a migração
    db.session.execute(
        text("ALTER TABLE church ADD COLUMN IF NOT EXISTS logo_path VARCHAR(255);")
    )
    db.session.commit()
    print("Campo 'logo_path' adicionado à tabela 'church' (ou já existia).")