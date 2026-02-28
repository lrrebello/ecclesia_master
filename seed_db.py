# update_db_columns.py (versão corrigida para PostgreSQL + palavras reservadas)
# Executar com: python update_db_columns.py

import os
from pathlib import Path
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import ProgrammingError, OperationalError
from dotenv import load_dotenv

# Carrega o .env
env_path = Path('.') / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print("Arquivo .env carregado com sucesso.")
else:
    print("Aviso: Arquivo .env não encontrado na raiz do projeto.")

# Pega a URI do banco
db_uri = (
    os.getenv('SQLALCHEMY_DATABASE_URI') or
    os.getenv('DATABASE_URL') or
    os.getenv('DB_URI')
)

if not db_uri:
    print("ERRO: Não encontrei nenhuma variável de banco de dados no .env")
    print("Verifique se existe SQLALCHEMY_DATABASE_URI ou DATABASE_URL")
    exit(1)

print(f"Conectando ao banco: {db_uri.split('://')[0]} ...")

engine = create_engine(db_uri, echo=False)  # mude para echo=True se quiser ver os SQLs

# Lista de colunas novas
# Use aspas duplas em nomes de tabela que possam ser reservados (como "user")
new_columns = [
    # Tabela "user" (com aspas!)
    ('"user"', 'postal_code',     'VARCHAR(20)'),
    ('"user"', 'concelho',         'VARCHAR(100)'),
    ('"user"', 'localidade',       'VARCHAR(100)'),
    ('"user"', 'education_level',  'VARCHAR(100)'),
    ('"user"', 'created_at',       'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),

    # Tabela church (normal, sem aspas)
    ('church', 'postal_code',    'VARCHAR(20)'),
    ('church', 'concelho',       'VARCHAR(100)'),
    ('church', 'localidade',     'VARCHAR(100)'),
]

def column_exists(table_name: str, column_name: str) -> bool:
    inspector = inspect(engine)
    # Remove aspas para inspeção (o inspector espera nome sem aspas)
    clean_table = table_name.strip('"')
    columns = [c['name'] for c in inspector.get_columns(clean_table)]
    return column_name in columns

def add_column(table_name: str, column_name: str, column_type: str):
    if column_exists(table_name, column_name):
        print(f"→ Coluna '{column_name}' já existe na tabela {table_name} → pulando")
        return

    sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
    
    with engine.connect() as conn:
        try:
            conn.execute(text(sql))
            conn.commit()
            print(f"✓ Coluna '{column_name}' criada com sucesso em {table_name}")
        except ProgrammingError as e:
            print(f"Erro de sintaxe/programação ao adicionar '{column_name}' em {table_name}: {e}")
        except OperationalError as e:
            print(f"Erro operacional ao adicionar '{column_name}' em {table_name}: {e}")
        except Exception as e:
            print(f"Erro inesperado ao adicionar '{column_name}' em {table_name}: {e}")

print("\nIniciando atualização das colunas novas...\n")

for table, col, col_type in new_columns:
    add_column(table, col, col_type)

print("\nAtualização finalizada!")
print("Se ainda der erro, verifique:")
print("• Permissões do usuário do banco (precisa de ALTER)")
print("• Se as tabelas existem mesmo (rode \\dt no psql para listar)")
print("• Conexão correta no .env")