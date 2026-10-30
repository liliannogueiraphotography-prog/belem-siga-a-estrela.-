# Integração isolada entre os três projetos

Este transporte existe **somente para testes locais**. Nunca publique `serve-isolated.ts` como API. Ele exige PostgreSQL em loopback, usuário `fixture_admin` e a tabela marcadora de isolamento. Nenhuma conexão usa credenciais do processo para escolher um banco.

O teste usa:

- A página e o controlador reais deste repositório.
- O handler original `src/routes/api/public/roleta-sorteio.ts` e as funções SQL originais do Painel Mestre, extraídas pelo bootstrap já existente nesse projeto.
- O checkout original do Experience, executado com Vite e RPCs locais.
- PostgreSQL descartável; conexões externas dos transportes e do navegador são recusadas. Fontes e scripts de analytics conhecidos são neutralizados para não enviar visitas/conversões fictícias.

Não substitui sorteio, cálculo, validação ou resgate por resultados fabricados. Os adaptadores substituem transporte Supabase/framework, configurações de exibição não relacionadas e provedores de pagamento. O teste de navegador não solicita pagamento.

## Pré-requisitos

Python 3, dependências de `tests/requirements.txt`, `/usr/bin/chromium`, Docker e Bun. Os outros dois repositórios precisam estar disponíveis com acesso autorizado:

```sh
git clone https://github.com/liliannogueiraphotography-prog/bel-m-masterpiece.git ../bel-m-masterpiece
git clone https://github.com/liliannogueiraphotography-prog/bel-m-experience-site.git ../bel-m-experience-site
```

Não repita o clone se já houver um checkout. Versões verificadas:

- Master: `b89a117ce74b0b80cacfeca14f0aed238ae6b516`.
- Experience: `4abda9e1cc29ad9e3723f23c2a0517edcc923dc6`.
- Bun 1.4.4; PostgreSQL 17 com manifesto fixado no runner.

Instale em cada projeto com `bun install --frozen-lockfile`, preservando lockfiles. Não sobrescreva mudanças existentes para alcançar os commits de referência. O relatório de execução registra os commits efetivamente utilizados.

## Execução

Na raiz da roleta:

```sh
python3 tests/integration/run_stack.py \
  --master ../bel-m-masterpiece \
  --site ../bel-m-experience-site \
  --output /tmp/belem-stack-results
```

O runner recusa portas 55432, 55433 ou 8081 já ocupadas; não mata processos existentes. Cria seu próprio contêiner com dados em tmpfs e porta publicada apenas em `127.0.0.1`. Remove os serviços e o contêiner ao terminar, inclusive em caso de falha. Não executar dois runners simultaneamente, pois os scripts existentes usam portas e `/tmp/roleta-db` fixos.

Os logs e `result.json` ficam no diretório de saída. Uma falha interrompe a execução com status não zero; não é convertida em aprovação ou skip. O navegador recebe a resposta do handler real por uma ponte de transporte local que fornece a origem oficial ao handler; o preflight publicado foi verificado separadamente, sem POST de produção.

## Cobertura e limites

O runner executa os 11 grupos SQL existentes do Master, os 27 testes de roleta/endpoint/segurança do Master, os 189 testes do Experience e cinco jornadas no Chromium. As jornadas sorteiam cada prêmio, recuperam o mesmo código, abrem o link do resgate por redirecionamento **apenas no teste** para o checkout local, rejeitam um código inválido, aplicam o válido e conferem o banco. Descontos percentuais preservam adicionais e saldo após refresh. Ensaio do Pacote 1 confirma uma reserva fictícia de total zero, com um único registro contábil de R$0 e nenhuma tentativa de pagamento.

Os dados de cliente/reserva/termos são fixtures SQL locais; o formulário completo de inscrição e a seleção da agenda não são percorridos nesse teste. Os testes de componente do Experience exercitam handlers/validadores e o checkout real; testes de pagamento simulam o provedor. Autenticação Supabase, RLS, grants e paridade da migração implantada em produção não são certificados por essa cópia isolada. Safari físico e pagamentos/webhooks sandbox exigem homologação separada.

O bootstrap deriva tabelas dos tipos e instala os corpos reais das funções, com as constraints e o trigger necessários às verificações. Não é uma cópia integral do esquema gerenciado. Alterar pesos para determinar os cinco prêmios acontece apenas nas fixtures locais, nunca na campanha real.

## Recuperação protegida

O Master candidato precisa incluir `0017_roleta_recovery_proof.sql` e o bootstrap atualizado. O handler público recebe também `comprovante`, persistido em IndexedDB no navegador, e usa a RPC privilegiada de autorização. Não adaptar a ponte para ignorar essa prova. A limpeza das fixtures inclui a tabela de pedidos para não misturar os limites entre jornadas. Os SHA efetivamente testados ficam em `result.json`.

`BELEM_BROWSER=webkit` permite executar a suíte com WebKit instalado pelo Playwright; `BROWSER_EXECUTABLE` é um caminho opcional para um executável local confiável. Não substitua um erro de mídia por sucesso simulado. Nesta máquina, a execução WebKit teve 27 testes de página aprovados e um erro no vídeo; a suíte integrada completa aprovada é a Chromium. A validação física de Safari permanece pendente.
