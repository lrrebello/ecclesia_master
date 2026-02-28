# update_db_columns.py
# Executar com: python3 update_db_columns.py

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

engine = create_engine(db_uri, echo=False)  # mude para True se quiser ver os comandos SQL

# Lista de colunas novas a adicionar
# Use aspas duplas em "user" porque é palavra reservada no PostgreSQL
new_columns = [
    # Tabela "user"
    ('"user"', 'postal_code',     'VARCHAR(20)'),
    ('"user"', 'concelho',         'VARCHAR(100)'),
    ('"user"', 'localidade',       'VARCHAR(100)'),
    ('"user"', 'education_level',  'VARCHAR(100)'),
    ('"user"', 'created_at',       'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),

    # Tabela church
    ('church', 'postal_code',      'VARCHAR(20)'),
    ('church', 'concelho',         'VARCHAR(100)'),
    ('church', 'localidade',       'VARCHAR(100)'),

    # Se quiser adicionar os campos de layout JSON para o editor de cartão (opcional agora)
    ('church', 'card_front_layout', 'JSONB'),  # ou JSON se for PostgreSQL < 9.4
    ('church', 'card_back_layout',  'JSONB'),
]

def column_exists(table_name: str, column_name: str) -> bool:
    inspector = inspect(engine)
    # Remove aspas para inspeção
    clean_table = table_name.strip('"')
    try:
        columns = [c['name'] for c in inspector.get_columns(clean_table)]
        return column_name in columns
    except Exception:
        print(f"→ Tabela {clean_table} não encontrada ou sem acesso → pulando checagem")
        return False

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
            print(f"Erro de sintaxe ao adicionar '{column_name}' em {table_name}: {e}")
        except OperationalError as e:
            print(f"Erro operacional ao adicionar '{column_name}' em {table_name}: {e}")
        except Exception as e:
            print(f"Erro inesperado ao adicionar '{column_name}' em {table_name}: {e}")

print("\nIniciando atualização das colunas novas...\n")

for table, col, col_type in new_columns:
    add_column(table, col, col_type)

print("\nAtualização finalizada!")
print("Se quiser adicionar mais campos no futuro, é só incluir na lista 'new_columns'.")
print("Dica: Após rodar, verifique no banco com:")
print("   psql -d seu_banco -c '\\d \"user\"'")
print("   psql -d seu_banco -c '\\d church'")