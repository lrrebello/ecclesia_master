from app import create_app
from app.core.models import db
from seed_db import seed_data

app = create_app()

def init_db():
    with app.app_context():
        # Cria todas as tabelas do zero
        db.create_all()
        print("Estrutura do banco de dados criada com sucesso!")
        
        # Chama a sementeira para criar o admin inicial
        print("\nIniciando sementeira de dados básicos...")
        seed_data()

if __name__ == '__main__':
    init_db()
