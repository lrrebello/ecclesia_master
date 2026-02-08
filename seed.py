from app import create_app
from app.core.models import db, User, Church, Devotional, Study, Transaction, Ministry, Family, ChurchRole
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

    # 2. Criar cargos para cada igreja (exemplos)
    # Cargos da Sede
    cargo_admin = ChurchRole(name="Administrador Global", description="Acesso total ao sistema", church_id=sede.id, order=1)
    cargo_pastor_lider = ChurchRole(name="Pastor Líder", description="Liderança da congregação", church_id=sede.id, order=2)
    cargo_tesoureiro = ChurchRole(name="Tesoureiro", description="Gestão financeira da filial", church_id=sede.id, order=3)
    cargo_diácono = ChurchRole(name="Diácono", description="Assistência e serviço", church_id=sede.id, order=4)
    cargo_presbítero = ChurchRole(name="Presbítero", description="Conselho espiritual", church_id=sede.id, order=5)
    cargo_membro = ChurchRole(name="Membro", description="Membro comum", church_id=sede.id, order=10)

    # Cargos da Filial Norte (exemplo de cargos diferentes)
    cargo_pastor_aux = ChurchRole(name="Pastor Auxiliar", description="Apoio ao pastor líder", church_id=filial1.id, order=2)
    cargo_evangelista = ChurchRole(name="Evangelista", description="Pregação e missões", church_id=filial1.id, order=6)
    cargo_missionario = ChurchRole(name="Missionário", description="Trabalho em campo", church_id=filial1.id, order=7)
    cargo_membro_filial = ChurchRole(name="Membro", description="Membro comum", church_id=filial1.id, order=10)

    db.session.add_all([
        cargo_admin, cargo_pastor_lider, cargo_tesoureiro, cargo_diácono, cargo_presbítero, cargo_membro,
        cargo_pastor_aux, cargo_evangelista, cargo_missionario, cargo_membro_filial
    ])
    db.session.commit()

    # 3. Criar Família de exemplo
    familia_silva = Family(name="Família Silva")
    db.session.add(familia_silva)
    db.session.commit()

    # 4. Criar Usuários com cargos vinculados
    admin = User(
        name="Super Admin",
        email="admin@igreja.com",
        birth_date=datetime(1980, 1, 1).date(),
        church_id=sede.id,
        church_role_id=cargo_admin.id,
        status="active"
    )
    admin.set_password("admin123")

    pastor_sede = User(
        name="Pr. Roberto",
        email="pastor@igreja.com",
        birth_date=datetime(1975, 6, 15).date(),
        church_id=sede.id,
        church_role_id=cargo_pastor_lider.id,
        status="active"
    )
    pastor_sede.set_password("pastor123")

    tesoureiro = User(
        name="Irmã Financeira",
        email="tesouro@igreja.com",
        birth_date=datetime(1985, 3, 20).date(),
        church_id=sede.id,
        church_role_id=cargo_tesoureiro.id,
        status="active"
    )
    tesoureiro.set_password("tesouro123")

    diacono = User(
        name="Diácono João",
        email="joao@igreja.com",
        birth_date=datetime(1990, 4, 10).date(),
        church_id=sede.id,
        church_role_id=cargo_diácono.id,
        status="active"
    )
    diacono.set_password("joao123")

    membro_sede = User(
        name="Membro Ativo",
        email="membro@igreja.com",
        birth_date=datetime(1995, 5, 15).date(),
        church_id=sede.id,
        family_id=familia_silva.id,
        church_role_id=cargo_membro.id,
        status="active"
    )
    membro_sede.set_password("membro123")

    pendente = User(
        name="Novo Candidato",
        email="novo@email.com",
        birth_date=datetime(2000, 10, 10).date(),
        church_id=sede.id,
        church_role_id=cargo_membro.id,  # começa como membro comum
        status="pending"
    )
    pendente.set_password("novo123")

    # Usuário da filial (exemplo)
    pastor_aux = User(
        name="Pr. Marcos (Filial)",
        email="marcos@filialnorte.com",
        birth_date=datetime(1982, 7, 22).date(),
        church_id=filial1.id,
        church_role_id=cargo_pastor_aux.id,
        status="active"
    )
    pastor_aux.set_password("marcos123")

    db.session.add_all([admin, pastor_sede, tesoureiro, diacono, membro_sede, pendente, pastor_aux])
    db.session.commit()

    # 5. Ministérios (exemplo)
    louvor = Ministry(
        name="Ministério de Louvor",
        description="Equipe de música e adoração",
        church_id=sede.id,
        leader_id=membro_sede.id
    )
    homens = Ministry(
        name="União Masculina",
        description="Grupo de homens da igreja",
        church_id=sede.id,
        leader_id=pastor_sede.id
    )
    db.session.add_all([louvor, homens])
    db.session.commit()

    # Associar membro a ministérios
    membro_sede.ministries.append(louvor)
    membro_sede.ministries.append(homens)
    db.session.commit()

    # 6. Devocional de exemplo
    dev = Devotional(
        title="Firmeza na Rocha",
        content="Quem ouve estas minhas palavras e as pratica é como um homem prudente que construiu a sua casa sobre a rocha.",
        verse="Mateus 7:24"
    )
    db.session.add(dev)
    db.session.commit()

    print("Seed concluído com sucesso!")
    print("Usuários criados (email / senha):")
    print("- admin@igreja.com / admin123")
    print("- pastor@igreja.com / pastor123")
    print("- tesouro@igreja.com / tesouro123")
    print("- joao@igreja.com / joao123")
    print("- membro@igreja.com / membro123")
    print("- novo@email.com / novo123")
    print("- marcos@filialnorte.com / marcos123")