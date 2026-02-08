from app import create_app
from app.core.models import db, User, Church, Devotional, Study, Transaction, Ministry, Family
from datetime import datetime, timedelta

app = create_app()

with app.app_context():
    db.drop_all()
    db.create_all()
    
    # 1. Igrejas
    sede = Church(name="AD Jesus para as Nações - Sede", address="Rua Principal, 123", city="São Paulo", country="Brasil", is_main=True)
    filial1 = Church(name="AD Jesus para as Nações - Filial Norte", address="Av. Norte, 456", city="São Paulo", country="Brasil")
    db.session.add_all([sede, filial1])
    db.session.commit()
    
    # 2. Família
    familia = Family(name="Família Silva")
    db.session.add(familia)
    db.session.commit()
    
    # 3. Usuários
    admin = User(name="Super Admin", email="admin@igreja.com", role="admin", status="active", 
                 church_id=sede.id, birth_date=datetime(1980, 1, 1).date())
    admin.set_password("admin123")
    
    pastor = User(name="Pr. Roberto", email="pastor@igreja.com", role="pastor_leader", status="active", 
                  church_id=sede.id, birth_date=datetime(1975, 6, 15).date())
    pastor.set_password("pastor123")
    
    tesoureiro = User(name="Irmão Financeiro", email="tesouro@igreja.com", role="treasurer", status="active", 
                      church_id=sede.id, birth_date=datetime(1985, 3, 20).date())
    tesoureiro.set_password("tesouro123")
    
    membro = User(name="Membro Ativo", email="membro@igreja.com", role="member", status="active", 
                  church_id=sede.id, family_id=familia.id, birth_date=datetime(1990, 5, 15).date())
    membro.set_password("membro123")
    
    pendente = User(name="Novo Candidato", email="novo@email.com", role="member", status="pending", 
                    church_id=sede.id, birth_date=datetime(2000, 10, 10).date())
    pendente.set_password("novo123")
    
    db.session.add_all([admin, pastor, tesoureiro, membro, pendente])
    db.session.commit()
    
    # 4. Ministérios
    louvor = Ministry(name="Ministério de Louvor", description="Equipe de música e adoração", church_id=sede.id, leader_id=membro.id)
    homens = Ministry(name="União Masculina", description="Grupo de homens da igreja", church_id=sede.id, leader_id=pastor.id)
    db.session.add_all([louvor, homens])
    db.session.commit()
    
    # Associar membro ao ministério
    membro.ministries.append(louvor)
    membro.ministries.append(homens)
    db.session.commit()
    
    # 5. Devocional
    dev = Devotional(title="Firmeza na Rocha", content="Quem ouve estas minhas palavras e as pratica é como um homem prudente que construiu a sua casa sobre a rocha.", verse="Mateus 7:24")
    db.session.add(dev)
    
    db.session.commit()
    print("Ecclesia Master Expandido inicializado com sucesso!")
