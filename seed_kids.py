from app import create_app
from app.core.models import db, BibleStory, BibleQuiz

app = create_app()

def seed_kids():
    with app.app_context():
        # Limpar dados antigos se necessário
        # BibleStory.query.delete()
        
        # Adicionar História: A Criação
        story1 = BibleStory(
            title="A Criação do Mundo",
            content="<p>No princípio, Deus criou o céu e a terra. Tudo estava escuro e vazio, mas o Espírito de Deus estava lá.</p><p>Deus disse: 'Haja luz!', e a luz apareceu. Ele viu que a luz era boa e a separou da escuridão.</p><p>Em seis dias, Deus criou as plantas, o sol, a lua, as estrelas, os peixes, os pássaros e todos os animais. Por último, Ele criou o homem e a mulher à Sua imagem.</p><p>No sétimo dia, Deus descansou e abençoou esse dia, porque tinha terminado toda a Sua obra maravilhosa.</p>",
            reference="Gênesis 1",
            order=1,
            image_path="https://img.freepik.com/vetores-gratis/ilustracao-da-historia-da-criacao-da-biblia-desenhada-a-mao_23-2149451000.jpg"
        )
        db.session.add(story1)
        db.session.flush()
        
        # Adicionar Quizzes para a Criação
        db.session.add(BibleQuiz(
            story_id=story1.id,
            question="O que Deus criou no primeiro dia?",
            option_a="Os animais",
            option_b="A luz",
            option_c="As estrelas",
            correct_option="B",
            explanation="Deus disse 'Haja luz' logo no início da criação."
        ))
        
        db.session.add(BibleQuiz(
            story_id=story1.id,
            question="Quantos dias Deus levou para criar tudo antes de descansar?",
            option_a="7 dias",
            option_b="10 dias",
            option_c="6 dias",
            correct_option="C",
            explanation="Deus trabalhou por 6 dias e descansou no 7º dia."
        ))

        # Adicionar História: Arca de Noé
        story2 = BibleStory(
            title="Noé e o Grande Barco",
            content="<p>Deus viu que o mundo estava muito bagunçado e as pessoas não eram mais gentis. Mas Noé era um homem bom e obediente.</p><p>Deus disse a Noé para construir uma arca gigante, um barco enorme feito de madeira. Noé obedeceu, mesmo que as pessoas rissem dele.</p><p>Ele colocou sua família e dois de cada tipo de animal dentro da arca. Então, começou a chover muito por 40 dias e 40 noites.</p><p>Quando a chuva parou, Deus colocou um lindo arco-íris no céu como uma promessa de que nunca mais inundaria a terra inteira.</p>",
            reference="Gênesis 6-9",
            order=2,
            image_path="https://img.freepik.com/vetores-gratis/ilustracao-da-arca-de-noe-desenhada-a-mao_23-2149445474.jpg"
        )
        db.session.add(story2)
        db.session.flush()
        
        db.session.add(BibleQuiz(
            story_id=story2.id,
            question="Qual foi o sinal da promessa de Deus após o dilúvio?",
            option_a="Uma pomba",
            option_b="Um arco-íris",
            option_c="Uma estrela",
            correct_option="B",
            explanation="O arco-íris representa a aliança de Deus com a humanidade."
        ))

        db.session.commit()
        print("Dados do Ecclesia Kids semeados com sucesso!")

if __name__ == "__main__":
    seed_kids()