from app import create_app
from app.core.models import db, User, Church, ChurchRole
from datetime import datetime

app = create_app()

def seed_data():
    with app.app_context():
        # 1. Criar a Igreja Inicial
        church = Church.query.filter_by(name="Ecclesia Matriz").first()
        if not church:
            church = Church(
                name="Ecclesia Matriz",
                address="Rua Principal, 123",
                city="Sua Cidade",
                country="Brasil",
                is_main=True
            )
            db.session.add(church)
            db.session.commit()
            print("Igreja 'Ecclesia Matriz' criada!")

        # 2. Criar os Cargos Básicos
        roles = [
            {'name': 'Administrador Global', 'description': 'Acesso total ao sistema', 'order': 1},
            {'name': 'Pastor Líder', 'description': 'Liderança espiritual e administrativa', 'order': 2},
            {'name': 'Membro', 'description': 'Membro regular da congregação', 'order': 10}
        ]
        
        admin_role = None
        for r in roles:
            role = ChurchRole.query.filter_by(name=r['name'], church_id=church.id).first()
            if not role:
                role = ChurchRole(
                    name=r['name'],
                    description=r['description'],
                    order=r['order'],
                    church_id=church.id
                )
                db.session.add(role)
            if r['name'] == 'Administrador Global':
                admin_role = role
        
        db.session.commit()
        print("Cargos iniciais criados!")

        # 3. Criar o Usuário Administrador Inicial
        admin_email = "admin@igreja.com"
        admin_user = User.query.filter_by(email=admin_email).first()
        if not admin_user:
            admin_user = User(
                name="Administrador do Sistema",
                email=admin_email,
                status='active',
                church_id=church.id,
                church_role_id=admin_role.id,
                # Permissões totais
                can_manage_ministries=True,
                can_manage_media=True,
                can_publish_devotionals=True,
                can_approve_members=True,
                can_manage_finance=True,
                can_manage_kids=True,
                can_manage_events=True
            )
            admin_user.set_password("admin123")
            db.session.add(admin_user)
            db.session.commit()
            print(f"Usuário administrador '{admin_email}' criado com senha 'admin123'!")
        else:
            print(f"Usuário '{admin_email}' já existe.")

        print("\nSementeira concluída com sucesso! Você já pode fazer login.")

if __name__ == '__main__':
    seed_data()
