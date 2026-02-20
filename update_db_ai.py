from app import create_app
from app.core.models import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # Lista de comandos para adicionar colunas
    # Usamos blocos try/except individuais e commits para garantir que cada um seja tentado
    # e que erros de transação não bloqueiem os próximos comandos.
    
    commands = [
        # Tabela bible_quiz
        ("ALTER TABLE bible_quiz ADD COLUMN option_d VARCHAR(200)", "bible_quiz.option_d"),
        ("ALTER TABLE bible_quiz ADD COLUMN is_published BOOLEAN DEFAULT TRUE", "bible_quiz.is_published"),
        ("ALTER TABLE bible_quiz ADD COLUMN explanation TEXT", "bible_quiz.explanation"),
        
        # Tabela study_question
        ("ALTER TABLE study_question ADD COLUMN correct_option VARCHAR(1)", "study_question.correct_option"),
        ("ALTER TABLE study_question ADD COLUMN explanation TEXT", "study_question.explanation"),
        ("ALTER TABLE study_question ADD COLUMN is_published BOOLEAN DEFAULT FALSE", "study_question.is_published"),
        
        # Tabela bible_story
        ("ALTER TABLE bible_story ADD COLUMN game_data TEXT", "bible_story.game_data")
    ]

    for cmd, label in commands:
        try:
            db.session.execute(text(cmd))
            db.session.commit()
            print(f"Sucesso: {label} adicionada.")
        except Exception as e:
            db.session.rollback()
            # Se o erro for "already exists", ignoramos silenciosamente
            if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                print(f"Aviso: {label} já existe ou foi ignorada.")
            else:
                print(f"Erro ao adicionar {label}: {str(e).splitlines()[0]}")
    
    print("\nProcesso de atualização finalizado!")
