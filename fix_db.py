from app import create_app
from app.core.models import db
from seed_db import seed_data

app = create_app()

def fix_and_init():
    with app.app_context():
        print("Limpando banco de dados para corrigir erro de tamanho de coluna...")
        # Remove todas as tabelas para recriar com o novo tamanho (String(255))
        db.drop_all()
        
        print("Recriando estrutura com correções...")
        db.create_all()
        print("Estrutura do banco de dados criada com sucesso!")
        
        print("\nIniciando sementeira de dados básicos...")
        seed_data()

if __name__ == '__main__':
    fix_and_init()
