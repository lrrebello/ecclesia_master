import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'ecclesia.db')

def migrate():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(user)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'tax_id' not in columns:
            print("Adicionando coluna 'tax_id'...")
            cursor.execute("ALTER TABLE user ADD COLUMN tax_id VARCHAR(20)")
            
            # Se a coluna 'nif' existir, migrar os dados para 'tax_id'
            if 'nif' in columns:
                print("Migrando dados de 'nif' para 'tax_id'...")
                cursor.execute("UPDATE user SET tax_id = nif")
        
        conn.commit()
        print("✓ Migração concluída com sucesso!")
        
    except sqlite3.Error as e:
        print(f"✗ Erro: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
