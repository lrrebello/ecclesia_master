# seed_users_render.py
# Rode localmente com: python seed_users_render.py
# Certifique-se de que o .env tem DATABASE_URL apontando para o Postgres do Render

from app import create_app
from app.core.models import db, User, Church, ChurchRole
from datetime import datetime
import os
from dotenv import load_dotenv

# Carrega .env (com DATABASE_URL do Render)
load_dotenv()

app = create_app()

def seed_users():
    with app.app_context():
        # Pegar igreja sede
        sede = Church.query.filter_by(name="AD Jesus para as Nações - Sede").first()
        church_id = sede.id if sede else None
        
        # Pegar role de Administrador Global
        admin_role = ChurchRole.query.filter_by(name="Administrador Global").first()
        admin_role_id = admin_role.id if admin_role else None
        
        # Usuários a criar/atualizar
        users_data = [
            {
                'name': 'Lucas Ramos Rebello da Silva',
                'email': 'lrrebello@gmail.com',
                'password': '19321985D@n',
                'birth_date': datetime(1985, 11, 8).date(),
                'gender': 'Masculino',
                'documents': '651651',
                'address': '16516',
                'phone': '6516511',
                'status': 'active',
                'is_email_verified': True,
                'church_id': church_id,
                'church_role_id': admin_role_id,  # Admin Global
                'can_manage_ministries': True,
                'can_manage_media': True,
                'can_publish_devotionals': True,
                'can_approve_members': True,
                'can_manage_finance': True,
                'can_manage_kids': True,
                'can_manage_events': True,
                'data_consent': True,
                'data_consent_date': datetime.utcnow(),
                'marketing_consent': True,
            },
            {
                'name': 'Kiara',
                'email': 'kiara@igreja.com',
                'password': 'kiara123',
                'status': 'active',
                'is_email_verified': True,
                'church_id': church_id,
                'data_consent': True,
                'data_consent_date': datetime.utcnow(),
            },
            {
                'name': 'Natalia',
                'email': 'natyolirebello@gmail.com',
                'password': 'natalia123',  # Senha padrão - mude depois
                'status': 'active',
                'is_email_verified': True,
                'church_id': church_id,
                'data_consent': True,
                'data_consent_date': datetime.utcnow(),
            },
            {
                'name': 'Italo Oliveira Rebello da Silva',
                'email': 'italorebello2017@gmail.com',
                'password': 'italo123',  # Senha padrão - mude depois
                'birth_date': datetime(2017, 2, 1).date(),
                'gender': 'Masculino',
                'documents': 'sdasda',
                'address': 'ohsduoan',
                'phone': '5165165',
                'status': 'active',
                'is_email_verified': True,
                'church_id': church_id,
                'data_consent': True,
                'data_consent_date': datetime.utcnow(),
            },
        ]

        created = 0
        updated = 0

        for data in users_data:
            email = data['email']
            user = User.query.filter_by(email=email).first()

            if user:
                print(f"Atualizando usuário existente: {email}")
                for key, value in data.items():
                    if key == 'password':
                        user.set_password(value)
                    else:
                        setattr(user, key, value)
                updated += 1
            else:
                print(f"Criando novo usuário: {email}")
                new_user = User(**data)
                new_user.set_password(data['password'])
                db.session.add(new_user)
                created += 1

        db.session.commit()
        print(f"\nSeed concluído com sucesso!")
        print(f"Usuários criados: {created}")
        print(f"Usuários atualizados: {updated}")
        print("\nDetalhes dos usuários:")
        for u in users_data:
            print(f"- {u['name']} ({u['email']}) - Senha: {u['password']} - Verificado: Sim - Ativo: Sim")

if __name__ == '__main__':
    seed_users()