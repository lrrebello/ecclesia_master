import pandas as pd
from datetime import datetime
from app import create_app
from app.core.models import db, User

app = create_app()

with app.app_context():
    try:
        df = pd.read_excel('DADOS DOS MEMBROS IEAD JN.xlsx', sheet_name='Sheet1', skiprows=1)
        df = df.dropna(how='all')

        count = 0
        for index, row in df.iterrows():
            birth_date = None
            if pd.notnull(row['Data de nascimento']):
                try:
                    birth_date = datetime.strptime(row['Data de nascimento'], '%d/%m/%Y').date()
                except ValueError:
                    print(f"Aviso: Data de nascimento inválida na linha {index}: {row['Data de nascimento']}")

            # Tenta converter documents para float se o modelo exigir (ajuste se for string)
            documents = None
            if pd.notnull(row['Documento 1']):
                try:
                    documents = float(row['Documento 1'])
                except ValueError:
                    print(f"Aviso: Documento inválido na linha {index}: {row['Documento 1']} - pulando")
                    continue

            user = User(
                name=row['Nome completo'],
                email=row['E-mail'],
                birth_date=birth_date,
                phone=str(row['Telefones']) if pd.notnull(row['Telefones']) else None,
                gender='F' if row['Sexo'] == 'Feminino' else 'M' if row['Sexo'] == 'Masculino' else None,
                address=row['Morada'],
                documents=documents,
                church_id=1,
                status='active'
            )
            user.set_password("mudar123")
            db.session.add(user)
            count += 1

        db.session.commit()
        print(f"Importação concluída! {count} membros importados com sucesso.")

    except Exception as e:
        db.session.rollback()
        print(f"Erro ao importar dados: {str(e)}")