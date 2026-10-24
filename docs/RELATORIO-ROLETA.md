# Roleta Siga a Estrela — relatório de conclusão local e homologação

Data: 24/10/2026. Projeto original preservado. Nenhuma publicação, migração SQL remota, cobrança, cupom ou reserva real foi criada durante os testes.

## Resultado

A integração foi localizada e exercitada de ponta a ponta **em ambiente isolado**, usando a página original da roleta, o handler original do Painel Mestre, as funções SQL existentes e o checkout original do Experience. Os cinco prêmios foram aplicados e seus estados conferidos no PostgreSQL descartável. O Ensaio Premiado confirmou uma reserva fictícia de total zero sem gateway.

A entrega está preparada para revisão e homologação final. A implantação gerenciada e os pagamentos reais não estão certificados pelos testes locais. As alterações permanecem em branch separada, destinadas a PR de rascunho, sem merge em `main`.

## 1. Serviços e repositórios encontrados

| Componente | Origem e versão inspecionada | Responsabilidade |
| --- | --- | --- |
| Roleta | `liliannogueiraphotography-prog/belem-siga-a-estrela.-`, base `6482e714bcae9707be9b26c5aa76860b2c042a02` | HTML/CSS, vídeo, CPF/aceite, giro e exibição do cupom |
| Painel Mestre/backend | `liliannogueiraphotography-prog/bel-m-masterpiece`, `587b9c770e6984c4ee1a3ddaf70c7765c73adf14` | Rota HTTP, HMAC do CPF, registro, sorteio e funções SQL de validação/consumo |
| Reservas | `liliannogueiraphotography-prog/bel-m-experience-site`, `4abda9e1cc29ad9e3723f23c2a0517edcc923dc6` | Checkout, aplicação/recuperação de saldo e fluxo de pagamento |
| Banco compartilhado configurado no código | Supabase `qgnssvvxrgmtpupaxxll` | Tabelas `belem_customers`, `belem_reservations`, `belem_payments` e `belem_roleta_*` |

Os dois repositórios privados foram encontrados com a autenticação GitHub existente, clonados e inspecionados; suas instruções `AGENTS.md` foram respeitadas. Nenhum arquivo dos dois projetos precisou ser alterado. O README e a configuração do Experience apontam para o mesmo Supabase do Master. **Isso verifica o código/configuração, não a migração efetivamente instalada no serviço gerenciado.**

O GitHub armazena os projetos e sincroniza branches conectadas com o Lovable; o servidor Lovable usa Supabase. A roleta estática usa GitHub Pages. Não há evidência de que o GitHub precise participar de uma transação de cupom.

## 2. Como a integração funciona

1. A página envia `cpf`, `aceite`, `versao_aceite` e `acao` para `POST https://m-master-view.lovable.app/api/public/roleta-sorteio`.
2. O handler valida origem, corpo e CPF; transforma a identidade em HMAC com `ROLETA_CPF_PEPPER`, sem persistir o CPF bruto no caminho inspecionado. Usa as RPCs privilegiadas `belem_roleta_register_cpf`, `belem_roleta_draw` e `belem_roleta_status`.
3. O banco registra participante/consentimento e retorna o mesmo prêmio para a mesma identidade. Cotas e sorteio são transacionais.
4. O botão de resgate abre `https://natal.estudioliliancristina.com.br/`. A cliente copia e aplica o código no campo existente do checkout. **Não há aplicação automática por URL nesse contrato**, e nenhum parâmetro foi inventado.
5. O checkout chama `belem_public_apply_coupon` com reserva, token público e código. O servidor valida a reserva, estado, prazo, não cumulatividade e saldo, usando as funções `belem_apply_roleta_coupon` e a variante compartilhada.
6. O desconto é calculado no servidor sobre o pacote; adicionais são preservados. O resgate é vinculado à reserva. Os triggers atualizam estados na confirmação/cancelamento. O guard de pagamento impede alterar um valor que já esteja em cobrança.

Tabelas principais: `belem_roleta_participants`, `belem_roleta_prizes`, `belem_roleta_coupons`, `belem_roleta_shared_awards`, `belem_roleta_shared_uses` e `belem_roleta_draw_attempts`.

Os scripts `supabase/schema.sql` e `supabase/award-engine.sql` da roleta são um **protótipo anterior `campaign_*`**, distinto desse backend. As correções e os 13 testes anteriores desse protótipo foram preservados, mas não contam como prova da integração publicada e não devem ser aplicados ao banco de reservas.

## 3. O que estava errado e foi corrigido

| Problema | Correção preservada ou concluída |
| --- | --- |
| Recuperação mencionada nas mensagens, mas controle removido | Botão funcional com `acao: consultar`, sem novo sorteio |
| Modo `?teste=1` ainda permitia caminhos reais | Bloqueio antes da API em todos os controles, incluindo teclado/formulário |
| Controlador demonstrativo antigo coexistia com o real e lia resultados de `localStorage` | Removido o controlador obsoleto; armazenamento antigo é ignorado sem apagar dados do usuário |
| Ausência de prazo da requisição, estado pendente e bloqueio contra cliques repetidos | Timeout, campos bloqueados durante operação e recuperação após resultado incerto |
| Resposta incompleta ou cupom vencido/usado podia habilitar resgate | Verificação de estrutura/estado, validade individual e rechecagem de expiração na tela/clique |
| Correção anterior exigia vencimento para todo cupom e rejeitava o estado `shared` | Corrigida a incompatibilidade com o contrato real: 5%, `status: shared`, `percent_off: 5`, `expires_at: null` é permitido |
| Possível código compartilhado reconfigurado no Painel | Aceita o código confirmado pelo servidor, sem fixar `ESTRELA5` como único valor válido na interface |
| Exceção compartilhada poderia ser ampla demais | Não é aceita para outros prêmios, percentuais divergentes ou cupom individual sem validade |
| Cupom já vinculado a reserva não tinha orientação específica | Estado `applied` orienta retomar a reserva; não oferece um novo resgate |
| Troca de CPF/retirada do aceite mantinha resultado anterior | Limpa a exibição/habilitação anterior |
| Clipboard ausente gerava erro síncrono | Fallback para copiar manualmente |
| Protótipo SQL local retornava cupons usados/vencidos e falhava em solicitações simultâneas da mesma sessão | Correção anterior mantida e testada, isoladamente do backend real |

O HTML e o CSS anteriores ao JavaScript continuam idênticos à base. O controlador foi extraído para `assets/roleta.js`; animações, vídeo completo, sons e texto comercial do ensaio foram preservados. O código publicado da roleta ainda correspondia ao HEAD antigo na consulta feita; as correções não foram publicadas.

## 4. Regras existentes preservadas

O contrato e o banco do **Master** são a fonte da integração, não o protótipo antigo:

| Prêmio | Cota padrão no código | Modalidade |
| --- | --- | --- |
| 5% | Sem cota numérica | Compartilhável, padrão `ESTRELA5`, sem vencimento; uma aplicação por reserva, reutilizável em outras reservas |
| 10% | 50 | Individual, uso único; prazo configurado no Master, padrão 120 minutos |
| 20% | 10 | Individual, uso único; padrão 120 minutos |
| 50% | 3 | Individual, uso único; padrão 120 minutos |
| Ensaio Premiado | 1 | Individual, uso único; padrão 120 minutos |

O código compartilhado é configurável no Painel. Percentuais não incidem nos adicionais. Ensaio usa o crédito do Pacote 1 do lote: R$680, R$880 ou R$1.000; upgrade paga a diferença, com extras e não cumulatividade existentes. Nenhum preço foi alterado.

Pesos, liberação e prazos efetivos são configuração do Master; não foram modificados na campanha. As migrações existentes tratam devolução de cota de cupom expirado/revogado e restauração sob regras da reserva. Os limiares progressivos e prazos de 24h do protótipo `campaign_*` não devem ser confundidos com essas regras. O relatório anterior foi superado por esta inspeção do backend real.

## 5. Verificações externas efetivamente realizadas

| Operação somente leitura | Resultado |
| --- | --- |
| GitHub: acesso e descoberta de repositórios relacionados | Os dois projetos privados foram acessados com autenticação existente |
| GET nos três sites envolvidos | HTTP 200 |
| OPTIONS da rota de sorteio com origem oficial | HTTP 204 e `Access-Control-Allow-Origin` correto |
| OPTIONS com origem não autorizada | HTTP 403, sem autorização CORS |
| Comparação do HTML publicado da roleta com o Git antigo | Correspondente à base anterior às correções |
| GET de metadados OpenAPI do Supabase com a chave publicável versionada | HTTP 401; não foi possível certificar grants/migrações por esse acesso |

GET da URL da API retorna HTML porque não há handler GET ali; o preflight e o código do handler POST foram verificados separadamente. **A API existe.** Não foi realizado POST de sorteio, registro, aplicação de cupom ou reserva em produção. O 401 de metadados não demonstra falha dos vínculos gerenciados pelo Lovable, que não estão disponíveis para inspeção nesta máquina.

## 6. Testes executados e resultados

| Suíte | Resultado | O que demonstra |
| --- | --- | --- |
| Roleta — Chromium | 24 testes passaram | Jornada com vídeo, cinco prêmios, contrato compartilhado, recuperação, rede, timeout, duplicidade, fraude de resposta, expiração e modo de teste isolado |
| Protótipo `campaign_*` — PostgreSQL descartável | 13 testes passaram | Correções anteriores preservadas; concorrência, unicidade, estados e cotas do protótipo |
| Master — funções/endpoint reais | 19 testes passaram | CPF, origem, HMAC/assinatura, sorteio e recuperação usando RPCs originais locais |
| Master — SQL real em cópia isolada | 11 grupos passaram | Valores, validades, não cumulatividade, seis giros simultâneos da mesma identidade, disputa de cupom e corrida contra início de pagamento |
| Experience — suítes existentes | 189 testes passaram, em 14 arquivos | Checkout, restauração de saldo, preços, créditos, pagamento e erros; provedores externos simulados |
| Jornada entre os três projetos — Chromium | 5 testes passaram | Cada prêmio foi sorteado pelo handler original, recuperado, aplicado no checkout original e conferido no banco |

São **250 testes individuais mais 11 grupos SQL**, sem contar execuções repetidas. `node --check assets/roleta.js` e `git diff --check` também passaram.

As jornadas conferiram rejeição de código inválido; percentuais corretos com adicionais preservados; saldo após refresh; participante registrado por identidade hash e consentimento; cupons percentuais em `applied`; e Ensaio Premiado em `redeemed` com reserva `confirmed`, um pagamento contábil de R$0 e **zero tentativas de gateway**.

A primeira execução da ponte de navegador detectou e bloqueou os scripts de analytics do checkout. A ponte foi ajustada para neutralizar explicitamente esses scripts somente nos testes; as cinco jornadas foram repetidas e passaram. Nenhuma visita/conversão fictícia foi enviada aos provedores nessa suíte integrada.

A cópia SQL usa os corpos originais das funções e as constraints/triggers necessários, mas não replica integralmente RLS, grants ou configuração gerenciada. A reserva inicial, o cliente e o aceite dos termos são fixtures locais; o formulário completo de inscrição/agenda não foi percorrido. A ponte substitui transporte e fornece a origem oficial ao handler; não simula sucesso do sorteio nem do cupom. Os testes de pagamento substituem o provedor, sem cobranças reais. Safari físico ainda não foi testado.

## 7. Arquivos alterados

Todos no repositório da roleta; Master e Experience permanecem sem alterações:

- `index.html`: controlador único, sem mudar o HTML/CSS aprovado.
- `assets/roleta.js`: lógica de participação, recuperação, validade e contrato compartilhado.
- `supabase/award-engine.sql`: correção anterior preservada no protótipo legado; não aplicada remotamente.
- `tests/test_roleta_browser.py`, `tests/test_award_engine.py`, `tests/requirements.txt`: regressões e dependência de teste.
- `tests/integration/serve-isolated.ts`, `full_stack_browser.py`, `run_stack.py`, `README.md`: ponte e execução reproduzível dos três projetos.
- `.gitignore`: somente artefatos Python gerados.
- `README.md`, `docs/PLANO-DE-IMPLEMENTACAO.md`, este relatório: instruções e distinção entre plano histórico e integração real.

Como reproduzir a suíte local: `python3 -m unittest discover -s tests -v`. Para os três projetos, seguir [tests/integration/README.md](../tests/integration/README.md). O runner cria e remove seus próprios serviços e contêiner; os resultados registram os commits utilizados.

## 8. O que falta para liberar aos clientes

1. **Conferir no Lovable as vinculações existentes do projeto Master:** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` e `ROLETA_CPF_PEPPER`; no Experience, conexão publicável com o mesmo Supabase. Não enviar valores pelo chat nem colocar chaves privadas no Git. Não trocar o pepper existente sem plano de migração: a identidade do CPF depende dele.
2. **Confirmar paridade do banco implantado**, especialmente as funções de roleta/cupom e as correções `0014_coupon_payment_race_guards` e `0015_roleta_expiry_restore_and_lock_order`. Conferir por acesso administrativo somente leitura. Não reaplicar migrações ou o SQL legado da roleta sem revisão e autorização.
3. **Homologar com configurações equivalentes em staging**, incluindo formulário de inscrição/agenda, Safari físico, expiração real e pagamentos/webhooks sandbox. As rotas públicas não devem aceitar a origem de um ambiente de teste em produção apenas para facilitar ensaios.
   A recuperação pública inspecionada usa CPF e aceite, sem prova adicional de posse do CPF; o caminho `consultar` não aplica o limitador de registro/giro. HMAC em repouso e CORS não impedem consultas automatizadas com CPFs conhecidos. É uma limitação concreta do contrato existente, ainda não corrigida: a proteção contra enumeração precisa de revisão no backend antes de declarar segurança completa. Acrescentar verificação de posse mudaria a jornada aprovada e requer uma decisão; não foi introduzida silenciosamente.
4. **Revisar e aprovar o PR da roleta e sua publicação**, sem push/merge automático em `main`. Um push nessa branch de produção dispara o GitHub Pages existente. Nenhuma aprovação de produção foi presumida.

A menor ação externa é conferir as vinculações e a versão das funções no Lovable/Supabase, com os valores mantidos nos respectivos gerenciadores seguros. Os repositórios necessários já foram encontrados; não é preciso criar outro backend ou outro banco de produção.
