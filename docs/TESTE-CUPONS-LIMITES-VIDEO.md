# Teste fictício de cupons, cotas e qualidade do vídeo

Data: 30/10/2026, Cuiabá. Os testes ocorreram em PostgreSQL descartável e páginas locais. Nenhuma cobrança, reserva ou emissão real foi criada; nada foi publicado.

## Cupons e jornada

A execução reproduzível entre os projetos passou: 27 testes do Master, 189 do Experience, cinco jornadas Chromium, 11 grupos SQL existentes e cinco grupos novos de esgotamento de cotas. As jornadas usam a página, o handler, as funções SQL e o checkout existentes, com dados fictícios e sem gateways reais.

Em um cenário de cálculo fictício com pacote de R$680 e adicionais de R$100:

| Cupom | Desconto só sobre o pacote | Saldo conferido |
| --- | --- | --- |
| 5% | R$34 | R$746 |
| 10% | R$68 | R$712 |
| 20% | R$136 | R$644 |
| 50% | R$340 | R$440 |

O Ensaio Premiado do Pacote 1, sem adicionais, confirmou uma reserva fictícia de total zero e registrou um único lançamento contábil de R$0, sem tentativa de gateway. O teste também verificou código inválido, recuperação do mesmo prêmio e saldo depois de recarregar o checkout. Os valores acima são fixtures para verificar cálculo, não alteração de preço oficial ou leitura do lote vigente em produção.

## Esgotamento e concorrência

| Prêmio | Cota padrão preservada | Emissões aceitas na disputa | Excedentes recusados |
| --- | --- | --- | --- |
| Ensaio Premiado | 1 | 1 | 12 |
| 50% | 3 | 3 | 12 |
| 20% | 10 | 10 | 12 |
| 10% | 50 | 50 | 12 |

As solicitações simultâneas passaram pela RPC real de autorização/sorteio, em conexões PostgreSQL distintas. Só os pesos das fixtures locais foram ajustados para disputar especificamente cada prêmio; nenhuma cota ou probabilidade real foi alterada.

Depois do esgotamento, ao habilitar o peso de 5% na fixture, o motor retornou `ESTRELA5`, sem emitir outro prêmio maior. Foram verificados também:

- Repetir a mesma participação devolve o mesmo cupom, sem duplicar emissão.
- Cupom maior expirado e não usado libera sua vaga conforme a regra já existente, mas o mesmo CPF não ganha outro prêmio.
- Cupom já resgatado continua contando na cota; não volta ao estoque.
- Trinta participantes fictícios receberam o mesmo compartilhável de 5%, sem criar cupons individuais extras.

Portanto, o limite é de prêmios maiores que ocupam cota (`issued`, `applied`, `redeemed`), e não da quantidade histórica de códigos emitidos ao longo das expirações. Essa semântica existente foi preservada.

**Os números foram confirmados no código e no banco de testes. Não equivalem a leitura autenticada das configurações do Painel Mestre publicado**, que ainda depende do acesso/configuração gerenciados já documentados. Antes de liberar a campanha, conferir as cotas do painel real.

## Vídeo

O arquivo local e o arquivo entregue por HTTPS em `roleta.estudioliliancristina.com.br` tiveram o mesmo SHA-256 e tamanho. Não há seleção de outra resolução nem versão maior escondida pelo player nesse caminho.

- Arquivo: `assets/belem-video-iphone-25mb.MP4`.
- Resolução: 720 × 1280, vertical.
- Duração: aproximadamente 85,47 segundos.
- Bitrate médio de vídeo: aproximadamente 540 kb/s, H.264.
- Tamanho real: 6.873.923 bytes, cerca de 6,9 MB, apesar do nome “25mb”.

A inspeção encontrou somente essa versão no histórico Git e nos arquivos disponíveis. A regra CSS final usa `object-fit: contain`, sem filtro de desfoque no vídeo. A imagem disponível é bastante comprimida e precisa ser ampliada em telas de alta densidade; aumentar o bitrate ou a resolução desse mesmo arquivo não recria os detalhes perdidos. O desfoque artístico do material original também não deve ser confundido com um ajuste do player.

O arquivo não foi reencodado, ampliado artificialmente nem substituído por outra criação. Para melhorar de fato, é necessário receber o original de maior qualidade, idealmente 1080p ou 4K, como arquivo ou link para o arquivo original, evitando reenvio comprimido por mensageiros. Então será possível preparar uma versão web mais nítida, preservando conteúdo, proporção e visual aprovados.

## Reprodução

O runner `tests/integration/run_stack.py` agora inclui `scripts/roleta-quota-isolated-tests.mjs` do Master. O script exige usuário `fixture_admin`, endereço loopback e marcador de isolamento, restaura os pesos e não usa credenciais de produção.

Resultados desta execução: todos os grupos passaram. O runner removeu os serviços e o banco temporários ao terminar. A limitação anterior de WebKit/vídeo e os testes físicos de iPhone permanecem separados desta validação Chromium; esta execução não certifica Safari ou pagamentos reais.
