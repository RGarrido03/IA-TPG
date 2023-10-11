# Notas da sessão de IA
## Informações básicas
Tem de se submeter um `student.py`, já que o `client.py` vai ser substituído. Copiar o `client.py` para `student.py`.

Caso se use o ChatGPT, mencionar lmao. O mesmo para discussões entre elementos de grupo. Pode-se partilhar ideias, não código.

## Design
4 camadas, túneis.

Fygars são os dragões que lançam chamas. Ganha-se maior pontuação quando se os mata na horizontal.

Ao início, o DigDug abre caminho e os inimigos correm nos túneis cavados.

Os inputs são *queued* a 10Hz. Mais do que isso, ele ignora. O normal é o agent demorar mais do que 1 frame e ter *input lag*. Assim, deve-se **evitar enviar frames muito rapidamente ou muito lentamente**. Deve-se manter um *steady state*, para aproximadamente 100 ms.

Cada nível é ultrapassado quando não existem mais inimigos no mapa, mas tem um limite de 3000 frames (5 minutos). No entanto, a cada nível aumenta o número de inimigos.

## Ações que dão mais pontos
- Matar dragões horizontalmente
- Matar com uma pedra (10000 pontos)

## Estratégia
O agente recebe o dicionário (`state`), faz as contas e devolve uma tecla. Repete-se.

Cada inimigo precisa de 3 inputs para morrer. A *rope* tem uma distância máxima 3. Os damages ficam guardados, mas o *heal* é feito com uma probabilidade de 10% por frame.

Os inimigos podem-se sobrepor, mas só um deles consegue ser atacado. Logo nessa situação o melhor é fugir.

Há uma grande probabilidade de estar a atacar alguém e surgir algum inimigo pelo meio. **É preciso ser reativo**.

Os inimigos desaparecem apenas na posição (1, 1).

Até ao nível 10, os inimigos comportam-se como aspirador-robô.A partir daí, fogem ou perseguem o DigDug.

O túnel cavado é importante para a estratégia. Os Pookas atravessam túneis.

## Acesso a informação
O dicionário contém o mapa, as coordenadas do DD e dos inimigos, o tempo que passou, os pontos, etc. A sensorização está feita, é só processar a informação desse dicionário (p.e., ).

Linhas que processam o keyboard não são necessárias, limpar isso.

O client recebe o dicionário (`state`). Criar classe `Agente` que recebe o estado e devolve uma tecla.

## Avaliação
Caso haja alguma adição relevante ao jogo e o *Pull Request* seja aceite, há um bónus de 1 valor.

Nota 10: 10k pontos.\
Nota 20: O que pontuar mais.\
Nota 16: Mediana.

A partir daí é linear.

Primeira iteração: vou ter com o inimigo, disparo. Nota 10.

O tree search das aulas serve para tirar positiva. O algoritmo A-star, dá para 16.

## Recomendações
- Estar atento ao Slack
- Fazer update do repositório *upstream*