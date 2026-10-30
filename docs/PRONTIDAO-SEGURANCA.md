# Segurança da recuperação — atualização de 29/10/2026

## Situação

A proteção foi implementada e testada nos repositórios existentes da roleta e do Master. A candidata não foi publicada. O Experience e seu checkout permanecem sem alterações; preços, pesos, cotas, prazos e a regra de um giro por CPF foram preservados.

A versão da página e o backend novo precisam ser homologados e publicados juntos. O usuário autorizou continuar as correções; isso não foi tratado como autorização para alterar o banco real ou publicar o site.

## Correções

- `girar` e `consultar` agora enviam um comprovante aleatório de 256 bits, salvo por transação IndexedDB, compartilhado entre abas do mesmo navegador. CPF e cupom não são gravados nesse armazenamento.
- O servidor guarda somente HMAC vinculado à identidade CPF e exige a prova antes de revelar o prêmio. Comprovante incorreto não substitui titularidade nem cria outro prêmio para um cadastro existente.
- Consulta desconhecida, comprovante incorreto e cadastro antigo sem prova recebem a mesma resposta, sem revelar o cupom.
- Uma RPC transacional no Master coordena autorização e sorteio/status. A consulta deixa de contornar o controle de abuso.
- O novo teto técnico de pedidos/consultas é independente dos limites existentes de giro e cadastro: padrão de 60 por IP/hora, configurável de 1 a 10.000. Não muda a quantidade de participações nem o sorteio configurado.
- Falha de armazenamento impede o envio do pedido, com mensagem clara. Falha de conexão conserva o caminho de consulta; recusa explícita permite uma nova tentativa manual, sem repetição automática da emissão.
- A URL do JavaScript inclui versão de cache, evitando reaproveitar o controlador anterior após a publicação.

O comprovante protege a sessão; não verifica a titularidade civil do CPF no primeiro cadastro. Verificação por WhatsApp exigiria decisão e provedor configurado. A alternativa foi apresentada à proprietária; o código preparado é o fluxo de comprovante no mesmo navegador, ainda sujeito à revisão.

## Preservação de clientes antigos

A migração adiciona campos e tabela de segurança. Não apaga, reseta, revoga ou reemite prêmios, reservas ou pagamentos. Não associa automaticamente um comprovante novo a cadastro antigo só pela informação do CPF.

Cupons antigos que a cliente já possui continuam utilizáveis no checkout conforme seus estados/prazos. Recuperação sem comprovante requer atendimento verificado no fluxo administrativo existente; o atendimento e a conferência humana precisam ser validados antes de ativar a nova regra. Não foi criada uma transferência pública de titularidade.

## Testes executados

| Verificação | Resultado |
| --- | --- |
| Navegador Chromium, página da roleta | 28 testes passaram, incluindo persistência do comprovante, duas abas, armazenamento bloqueado e recuperação após falha |
| PostgreSQL legado `campaign_*` | 13 testes passaram; mantido isolado da integração real |
| Master, funções/endpoint e segurança | 27 testes passaram; oito casos novos incluem tentativa de apropriação, legado, HMAC, permissões, janelas e concorrência |
| SQL real do Master, cópia descartável | 11 grupos passaram, preservando distribuição, desconto, estoque e guardas de pagamento |
| Experience | 189 testes passaram |
| Cinco jornadas integradas Chromium | Passaram com a página, handler, SQL e checkout existentes, todos locais; ensaio confirmou reserva fictícia de total zero sem gateway |
| TypeScript e build do Master | Aprovados |
| Sintaxe JS e `git diff --check` | Aprovados |
| WebKit Linux, página da roleta | 27 passaram; 1 erro no carregamento do MP4. A execução não foi aprovada integralmente |
| Safari em iPhone físico e gateways/webhooks sandbox | Não executados |

São 262 testes principais aprovados e 11 grupos SQL, sem contar execuções repetidas. A verificação opcional WebKit foi mantida separada: o erro de vídeo não foi convertido em aprovação nem mascarado por um evento de término simulado. O runtime Linux registrou falhas de mídia/conexão e áudio; a causa não foi resolvida conclusivamente. Não há homologação de Safari físico.

Nos testes de concorrência, provas diferentes disputaram o mesmo CPF e só uma se tornou proprietária. Seis repetições concorrentes com a prova correta recuperaram o mesmo cupom. O teto de consultas também foi respeitado por conexões simultâneas.

Todo sorteio/reserva/pagamento de teste ficou em PostgreSQL descartável. Não houve POST de sorteio, registro, resgate, reserva ou pagamento em produção. Fontes e analytics externos são neutralizados na ponte local para não enviar visitas/conversões fictícias.

## Arquivos desta continuação

**Roleta:** `assets/roleta.js`, `index.html`, `tests/test_roleta_browser.py`, `tests/integration/full_stack_browser.py`, `tests/integration/run_stack.py`, `tests/integration/serve-isolated.ts` e a documentação de prontidão/execução.

**Master:** `src/routes/api/public/roleta-sorteio.ts`, `drizzle/migrations/0017_roleta_recovery_proof.sql`, seu journal, `scripts/roleta-local-bootstrap.py`, testes de endpoint/recuperação e documentação do contrato/ativação.

O plano completo da migração e atendimento está em `docs/ROLETA-RECUPERACAO-SEGURA.md` no [PR #4 do Master](https://github.com/liliannogueiraphotography-prog/bel-m-masterpiece/pull/4), commit `b89a117ce74b0b80cacfeca14f0aed238ae6b516`. A página está no [PR #1 da roleta](https://github.com/liliannogueiraphotography-prog/belem-siga-a-estrela.-/pull/1). A reprodução dos testes está em [tests/integration/README.md](../tests/integration/README.md).

## Menor passo externo para ativar

1. Revisar os dois PRs juntos e confirmar o fluxo de comprovante no navegador, incluindo o atendimento aos antigos.
2. Conferir no Lovable/Supabase o projeto compartilhado, os vínculos `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ROLETA_CPF_PEPPER` e a paridade das migrações. Não trocar o pepper nem enviar valores de chaves pelo chat/Git.
3. Autorizar e aplicar a migração 0017 como uma transação pelo fluxo do Master. Ela pede recarga do esquema REST. Não executar o SQL legado `campaign_*` na base de reservas.
4. Homologar em staging a nova regra, a recuperação de clientes antigos, o vídeo no iPhone físico e os pagamentos/webhooks sandbox.
5. Após autorização, publicar primeiro o backend protegido e em seguida a página atualizada, em janela coordenada. Páginas antigas precisarão ser recarregadas. Não publicar a página sozinha supondo que o servidor antigo já faça essa validação.

Se a migração estiver ausente, o backend falha fechado com `NOT_CONFIGURED`; não retorna à consulta insegura por CPF. Em reversão, preservar dados e comprovantes e suspender o endpoint enquanto se corrige a implantação. Nenhuma dessas ações de produção foi realizada nesta tarefa.
