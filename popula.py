# seed_users.py
from app import create_app
from app.core.models import db, User, Church
from datetime import datetime

app = create_app()

def seed_users():
    with app.app_context():
        # Pegar a igreja principal (sede) - ajuste o nome se necessário
        sede = Church.query.filter_by(name="AD Jesus para as Nações - Sede").first()
        church_id = sede.id if sede else None
        
        # Lista de usuários para criar/atualizar
        users_data = [
            {
                'name': 'Lucas Ramos Rebello',
                'email': 'lrrebello@gmail.com',
                'password': '19321985D@n',
                'birth_date': datetime(1985, 11, 8).date(),  # exemplo, ajuste se quiser
                'gender': 'Masculino',
                'documents': '123456789',  # NIF exemplo
                'address': 'R. Dr. Mário Sacramento, 57 - Aveiro',
                'phone': '912345678',
                'status': 'active',
                'is_email_verified': True,
                'church_id': church_id,
                'is_ministry_leader': True,  # opcional
                'can_manage_finance': True,  # opcional - ajuste permissões
            },
            {
                'name': 'Kiara',
                'email': 'kiara@igreja.com',
                'password': 'kiara123',
                'birth_date': None,
                'gender': None,
                'documents': None,
                'address': None,
                'phone': None,
                'status': 'active',
                'is_email_verified': True,
                'church_id': church_id,
            },
            {
                'name': 'Natalia',
                'email': 'natyolirebello@gmail.com',
                'password': 'natalia123',  # senha padrão - mude depois
                'birth_date': None,
                'gender': None,
                'documents': None,
                'address': None,
                'phone': None,
                'status': 'active',
                'is_email_verified': True,
                'church_id': church_id,
            },
            {
                'name': 'Italo Oliveira Rebello da Silva',
                'email': 'italorebello2017@gmail.com',
                'password': 'italo123',  # senha padrão - mude depois
                'birth_date': datetime(2017, 2, 1).date(),
                'gender': 'Masculino',
                'documents': '987654321',
                'address': 'Aveiro',
                'phone': '961234567',
                'status': 'active',
                'is_email_verified': True,
                'church_id': church_id,
            },
        ]

        created = 0
        updated = 0

        for data in users_data:
            email = data['email']
            user = User.query.filter_by(email=email).first()

            if user:
                # Atualiza se já existe (mantém id, atualiza senha e campos)
                print(f"Atualizando usuário existente: {email}")
                user.name = data['name']
                user.set_password(data['password'])
                user.birth_date = data.get('birth_date')
                user.gender = data.get('gender')
                user.documents = data.get('documents')
                user.address = data.get('address')
                user.phone = data.get('phone')
                user.status = data['status']
                user.is_email_verified = data['is_email_verified']
                user.church_id = data['church_id']
                # Permissões extras (opcional)
                user.can_manage_finance = data.get('can_manage_finance', False)
                user.is_ministry_leader = data.get('is_ministry_leader', False)
                updated += 1
            else:
                # Cria novo
                print(f"Criando novo usuário: {email}")
                new_user = User(
                    name=data['name'],
                    email=email,
                    birth_date=data.get('birth_date'),
                    gender=data.get('gender'),
                    documents=data.get('documents'),
                    address=data.get('address'),
                    phone=data.get('phone'),
                    church_id=data['church_id'],
                    status=data['status'],
                    is_email_verified=data['is_email_verified'],
                    data_consent=True,  # assume consentido
                    data_consent_date=datetime.utcnow(),
                    marketing_consent=False,
                )
                new_user.set_password(data['password'])
                # Permissões extras
                new_user.can_manage_finance = data.get('can_manage_finance', False)
                new_user.is_ministry_leader = data.get('is_ministry_leader', False)
                db.session.add(new_user)
                created += 1

        db.session.commit()
        print(f"\nSeed concluído!")
        print(f"Usuários criados: {created}")
        print(f"Usuários atualizados: {updated}")
        print("\nUsuários adicionados/atualizados:")
        for u in users_data:
            print(f"- {u['name']} ({u['email']}) - senha: {u['password']}")

if __name__ == '__main__':
    seed_users()