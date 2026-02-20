from datetime import datetime, timedelta
from app import create_app
from app.core.models import db, Devotional

app = create_app()

def seed_devotionals():
    with app.app_context():
        # Ano bissexto 2026
        start_date = datetime(2026, 1, 1).date()
        end_date = datetime(2026, 12, 31).date()
        current_date = start_date
        
        # Exemplos reais/inspirados em devocionais cristãos em português (2026 style)
        # Fontes: Pão Diário, Devocional Diário, Voltemos ao Evangelho, Bíblia On, etc.
        # Cada um tem title, verse, content curto (podes expandir depois)
        examples = [
    {
        "title": "A Paz que Excede Todo Entendimento",
        "verse": "Filipenses 4:7",
        "content": "A paz de Deus, que excede todo o entendimento, guardará os vossos corações e os vossos pensamentos em Cristo Jesus. Em meio ao caos do mundo, busque essa paz que vem do alto e confie no Senhor."
    },
    {
        "title": "Confiança no Senhor de Todo o Coração",
        "verse": "Provérbios 3:5-6",
        "content": "Confia no Senhor de todo o teu coração e não te estribes no teu próprio entendimento. Reconhece-o em todos os teus caminhos, e ele endireitará as tuas veredas. Entrega teu futuro a Ele."
    },
    {
        "title": "O Amor Incondicional de Deus",
        "verse": "João 3:16",
        "content": "Porque Deus amou o mundo de tal maneira que deu o seu Filho unigênito, para que todo aquele que nele crê não pereça, mas tenha a vida eterna. Esse amor é a base da nossa esperança eterna."
    },
    {
        "title": "Graça que Basta na Fraqueza",
        "verse": "2 Coríntios 12:9",
        "content": "A minha graça te basta, porque o meu poder se aperfeiçoa na fraqueza. Quando nos sentimos fracos, é aí que o Senhor se fortalece em nós e nos sustenta."
    },
    {
        "title": "Caminho da Vida na Presença de Deus",
        "verse": "Salmos 16:11",
        "content": "Tu me mostrarás a vereda da vida; na tua presença há plenitude de alegria; à tua direita há delícias perpetuamente. Busque a presença dEle diariamente."
    },
    {
        "title": "Honra ao Senhor com os Teus Bens",
        "verse": "Provérbios 3:9-10",
        "content": "Honra ao Senhor com os teus bens e com as primícias de toda a tua renda; e se encherão fartamente os teus celeiros. Deus abençoa quem O prioriza."
    },
    {
        "title": "Oração do Pai Nosso – Um Modelo de Oração",
        "verse": "Mateus 6:9-13",
        "content": "Pai nosso, que estás nos céus... Dá-nos hoje o nosso pão de cada dia. Perdoa-nos as nossas dívidas, assim como nós perdoamos aos nossos devedores. Ore com simplicidade e fé."
    },
    {
        "title": "Maravilhado com a Ressurreição de Cristo",
        "verse": "1 Coríntios 15:20",
        "content": "Mas de fato Cristo ressuscitou dos mortos, sendo ele as primícias entre aqueles que dormiram. Essa verdade transforma o nosso luto em esperança eterna."
    },
    {
        "title": "Venham e Vejam – Convite de Jesus",
        "verse": "João 1:46",
        "content": "Natanael lhe disse: Pode vir alguma coisa boa de Nazaré? Filipe respondeu: Vem e vê. Jesus nos convida a experimentar pessoalmente quem Ele é."
    },
    {
        "title": "Plenitude de Alegria no Ano Novo",
        "verse": "Salmos 16:11",
        "content": "Neste ano que se inicia, viva a plenitude de alegria na presença do Senhor, pois Ele é a fonte de toda felicidade verdadeira e duradoura."
    },
    {
        "title": "O Custo de Reclamar",
        "verse": "Números 11:1",
        "content": "E o povo se queixou aos ouvidos do Senhor... E o fogo do Senhor acendeu-se entre eles. Reclamar abre portas para descontentamento; agradeça e confie."
    },
    {
        "title": "Quando Você é Imortal",
        "verse": "João 11:25-26",
        "content": "Eu sou a ressurreição e a vida; quem crê em mim, ainda que esteja morto, viverá. A morte não tem a última palavra para quem está em Cristo."
    },
    {
        "title": "Lealdade Silenciosa em Cristo",
        "verse": "Mateus 6:6",
        "content": "Mas tu, quando orares, entra no teu quarto e, fechando a porta, ora a teu Pai em secreto. A verdadeira devoção muitas vezes é silenciosa e pessoal."
    },
    {
        "title": "Os Sábios Propósitos de Deus",
        "verse": "Romanos 8:28",
        "content": "Sabemos que todas as coisas cooperam para o bem daqueles que amam a Deus. Mesmo nas dificuldades, Deus tem um propósito sábio e amoroso."
    },
    {
        "title": "Revestidos de Coragem",
        "verse": "Josué 1:9",
        "content": "Não to mandei eu? Sê forte e corajoso; não temas, nem te espantes, porque o Senhor teu Deus é contigo por onde quer que andares."
    },
    {
        "title": "A Força que Vem do Senhor",
        "verse": "Isaías 40:31",
        "content": "Mas os que esperam no Senhor renovam as suas forças; sobem com asas como águias; correm e não se cansam; caminham e não se fatigam."
    },
    {
        "title": "A Palavra Viva e Eficaz",
        "verse": "Hebreus 4:12",
        "content": "Porque a palavra de Deus é viva, e eficaz, e mais cortante do que qualquer espada de dois gumes. Deixa que ela penetre teu coração hoje."
    },
    {
        "title": "Disciplinas Espirituais para Maturidade",
        "verse": "1 Timóteo 4:7-8",
        "content": "Exercita-te, pessoalmente, na piedade. Porque o exercício corporal para pouco aproveita; a piedade, porém, para tudo é proveitosa."
    },
    {
        "title": "Não Dá Nada – Confiança em Deus",
        "verse": "Filipenses 4:19",
        "content": "O meu Deus suprirá todas as vossas necessidades segundo as suas riquezas na glória em Cristo Jesus. Confie que Ele cuida de ti."
    },
    {
        "title": "Vivendo o Reino de Deus Hoje",
        "verse": "Mateus 6:33",
        "content": "Buscai primeiro o reino de Deus e a sua justiça, e todas estas coisas vos serão acrescentadas. Priorize o Reino em tuas decisões diárias."
    },
    # Mais 10 para chegar a 30 (ciclagem melhor)
    {
        "title": "A Luz que Vence as Trevas",
        "verse": "João 8:12",
        "content": "Eu sou a luz do mundo; quem me segue não andará nas trevas, mas terá a luz da vida. Deixe Cristo iluminar teu caminho hoje."
    },
    {
        "title": "Perdão que Liberta",
        "verse": "Efésios 4:32",
        "content": "Sede uns para com os outros benignos, compassivos, perdoando-vos uns aos outros, como também Deus vos perdoou em Cristo."
    },
    {
        "title": "Esperança que Não Envergonha",
        "verse": "Romanos 5:5",
        "content": "A esperança não traz confusão, porquanto o amor de Deus está derramado em nossos corações pelo Espírito Santo que nos foi dado."
    },
    {
        "title": "O Poder da Oração Fervorosa",
        "verse": "Tiago 5:16",
        "content": "A oração feita por um justo pode muito em seus efeitos. Ore com fé e veja Deus agir."
    },
    {
        "title": "Crescimento na Graça",
        "verse": "2 Pedro 3:18",
        "content": "Antes, crescei na graça e no conhecimento de nosso Senhor e Salvador Jesus Cristo. Cresça espiritualmente dia após dia."
    },
    {
        "title": "Deus Cuida dos Teus Temores",
        "verse": "Isaías 41:10",
        "content": "Não temas, porque eu sou contigo; não te assombres, porque eu sou o teu Deus; eu te esforço, e te ajudo, e te sustento com a destra da minha justiça."
    },
    {
        "title": "A Alegria do Senhor é a Nossa Força",
        "verse": "Neemias 8:10",
        "content": "Não vos entristeçais, porque a alegria do Senhor é a vossa força. Encontre alegria nEle mesmo nas provações."
    },
    {
        "title": "Chamados para Ser Luz",
        "verse": "Mateus 5:14",
        "content": "Vós sois a luz do mundo. Não se pode esconder uma cidade edificada sobre um monte. Brilhe para a glória de Deus."
    },
    {
        "title": "Descanso em Cristo",
        "verse": "Mateus 11:28",
        "content": "Vinde a mim, todos os que estais cansados e oprimidos, e eu vos aliviarei. Entregue teu fardo a Jesus hoje."
    }
]
        
        count = 0
        total_days = (end_date - start_date).days + 1
        print(f"Iniciando seed de {total_days} dias (2026 - bissexto)...")
        
        while current_date <= end_date:
            existing = Devotional.query.filter_by(date=current_date).first()
            if not existing:
                example = examples[count % len(examples)]  # Cicla pelos exemplos
                new_dev = Devotional(
                    title=example["title"],
                    verse=example["verse"],
                    content=example["content"],
                    date=current_date
                    # church_id=1  # Descomente se quiser associar à igreja principal (ajuste o ID)
                )
                db.session.add(new_dev)
                count += 1
                
                # Progresso a cada 30 dias
                if count % 30 == 0:
                    print(f"{count} devocionais adicionados até {current_date}...")
            
            current_date += timedelta(days=1)
        
        db.session.commit()
        print(f"\nConcluído! {count} devocionais adicionados com sucesso para 2026.")
        if count == 0:
            print("Nenhum novo adicionado (já existiam todos ou erro na query).")

if __name__ == '__main__':
    seed_devotionals()