from app import create_app
from app.core.models import db, User, Church, Devotional, Study, Transaction, Ministry, Family, ChurchRole, Asset
from datetime import datetime

app = create_app()

with app.app_context():
    # Limpa tudo (cuidado: só use em desenvolvimento!)
    db.drop_all()
    db.create_all()

    # 1. Criar Igrejas
    sede = Church(
        name="AD Jesus para as Nações - Sede",
        address="Rua Principal, 123",
        city="São Paulo",
        country="Brasil",
        is_main=True
    )
    filial1 = Church(
        name="AD Jesus para as Nações - Filial Norte",
        address="Av. Norte, 456",
        city="São Paulo",
        country="Brasil"
    )
    db.session.add_all([sede, filial1])
    db.session.commit()

    # 2. Criar cargos para cada igreja
    cargo_admin = ChurchRole(name="Administrador Global", description="Acesso total ao sistema", church_id=sede.id, order=1)
    cargo_pastor_lider = ChurchRole(name="Pastor Líder", description="Liderança da congregação", church_id=sede.id, order=2)
    cargo_tesoureiro = ChurchRole(name="Tesoureiro", description="Gestão financeira da filial", church_id=sede.id, order=3)
    cargo_membro = ChurchRole(name="Membro", description="Membro comum", church_id=sede.id, order=10)

    db.session.add_all([cargo_admin, cargo_pastor_lider, cargo_tesoureiro, cargo_membro])
    db.session.commit()

    # 3. Criar Usuários com permissões explícitas
    admin = User(
        name="Super Admin",
        email="admin@igreja.com",
        birth_date=datetime(1980, 1, 1).date(),
        church_id=sede.id,
        church_role_id=cargo_admin.id,
        status="active",
        can_manage_finance=True,
        can_manage_media=True,
        can_publish_devotionals=True,
        can_approve_members=True,
        can_manage_kids=True
    )
    admin.set_password("admin123")

    pastor_sede = User(
        name="Pr. Roberto",
        email="pastor@igreja.com",
        birth_date=datetime(1975, 6, 15).date(),
        church_id=sede.id,
        church_role_id=cargo_pastor_lider.id,
        status="active",
        can_approve_members=True,
        can_publish_devotionals=True,
        can_manage_kids=True
    )
    pastor_sede.set_password("pastor123")

    tesoureiro = User(
        name="Irmã Financeira",
        email="tesouro@igreja.com",
        birth_date=datetime(1985, 3, 20).date(),
        church_id=sede.id,
        church_role_id=cargo_tesoureiro.id,
        status="active",
        can_manage_finance=True
    )
    tesoureiro.set_password("tesouro123")

    membro_sede = User(
        name="Membro Ativo",
        email="membro@igreja.com",
        birth_date=datetime(1995, 5, 15).date(),
        church_id=sede.id,
        church_role_id=cargo_membro.id,
        status="active"
    )
    membro_sede.set_password("membro123")

    db.session.add_all([admin, pastor_sede, tesoureiro, membro_sede])
    db.session.commit()

    # 4. Ministérios
    louvor = Ministry(name="Ministério de Louvor", description="Equipe de música e adoração", church_id=sede.id, leader_id=membro_sede.id)
    kids = Ministry(name="Ministério Infantil", description="Educação cristã para crianças", church_id=sede.id, leader_id=pastor_sede.id)
    db.session.add_all([louvor, kids])
    db.session.commit()

    # 5. Conteúdo
    estudo = Study(title="A Importância da Oração", content="A oração é o fôlego da alma...", category="Espiritualidade", author_id=pastor_sede.id)
    dev = Devotional(title="Firmeza na Rocha", content="O Senhor é o meu pastor...", verse="Salmos 23:1")
    db.session.add_all([estudo, dev])
    
    # 6. Financeiro
    tx1 = Transaction(type='income', category='Dízimo', amount=500.0, description='Dízimo Mensal', user_id=membro_sede.id, church_id=sede.id)
    tx2 = Transaction(type='expense', category='Energia', amount=150.0, description='Conta de Luz', church_id=sede.id)
    db.session.add_all([tx1, tx2])

    # 7. Patrimônio
    som = Asset(name="Mesa de Som", category="Equipamento", identifier="SN-12345", value=2500.0, church_id=sede.id)
    db.session.add(som)

    db.session.commit()
    print("Seed concluído com sucesso!")
    print("Usuários criados (email / senha):")
    print("- admin@igreja.com / admin123")
    print("- pastor@igreja.com / pastor123")
    print("- tesouro@igreja.com / tesouro123")
    print("- membro@igreja.com / membro123")
