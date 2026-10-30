# Siga a Estrela | Belém 2026

Site independente para campanha de QR codes, vídeo oficial, roleta e cupons. Não alterar o site de reservas existente.

## Jornada implementada

QR Code com origem identificada → portal da estrela → vídeo oficial de Belém → botão da roleta após o vídeo completo → resultado confirmado pelo servidor → cupom individual ou compartilhável de 5% → site oficial de reservas.

## Prêmios implementados

- 1 ensaio Belém com 10 fotos digitais
- 3 descontos de 50%
- 10 descontos de 20%
- 50 descontos de 10%, conforme alteração do commit `a1b8000`
- 5% como prêmio mínimo, sem limite pré-definido

## Desenvolvimento e testes

Site estático, sem instalação ou build de produção. Na raiz do repositório:

```sh
python3 -m http.server 8000 --bind 0.0.0.0
```

Use `?teste=1` para demonstração isolada, sem acessar o sorteio real. O modo normal aponta para a API publicada; não o use com dados fictícios sem interceptação ou homologação.

Testes de navegador e de concorrência SQL estão em `tests/`. Instruções, resultados, requisitos de acesso e checklist manual: [Relatório da roleta](docs/RELATORIO-ROLETA.md).

## Situação da integração

As correções não foram publicadas. A emissão, validação e aplicação foram verificadas com o backend existente em ambiente isolado. A configuração gerenciada e os pagamentos/webhooks sandbox ainda exigem homologação separada. Não ativar a campanha nem executar SQL no banco das reservas antes dessa validação e da autorização para publicação.

A integração existente foi localizada nos projetos privados `bel-m-masterpiece` e `bel-m-experience-site` e testada localmente com os cinco prêmios. O prêmio de 5% usa código compartilhável, padrão `ESTRELA5`, sem vencimento, conforme o contrato do Master. Os scripts `campaign_*` deste repositório são históricos e não devem ser aplicados ao banco compartilhado de reservas.

Execução reproduzível entre os três projetos: [testes de integração](tests/integration/README.md). A homologação da configuração publicada e a autorização de produção continuam pendentes.

Atualização da segurança da recuperação, testes e ordem de ativação: [prontidão da candidata](docs/PRONTIDAO-SEGURANCA.md). A migração 0017 pertence ao Master e depende de revisão/autorização; o fluxo exige publicação coordenada dos dois PRs.
