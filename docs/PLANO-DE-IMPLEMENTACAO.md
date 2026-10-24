# Plano de implementação | Belém Siga a Estrela

> Plano original, mantido como histórico. Quantidades e etapas abaixo podem estar desatualizadas. Consulte o [relatório da auditoria](RELATORIO-ROLETA.md) e o README para a implementação vigente.

## Identidade
Sem árvore de Natal, Papai Noel ou elementos natalinos convencionais. Estrela central, atmosfera de Belém, palha, linho, tons terrosos, dourado e luz quente.
A frase "Entre na história que mudou todas as histórias" aparece apenas na entrada do site, acompanhada da estrela.

## Jornada
1. QR Code com parâmetro ?origem=...
2. Entrada encantadora com estrela.
3. Vídeo oficial do Will sobre Belém. Após 5% reproduzido, mostrar botão "Rode a roleta e descubra seu prêmio".
4. Roleta com estrela central.
5. Prêmio, cupom único, validade e botão "Garantir minha experiência".
6. Botão aponta para https://natal.estudioliliancristina.com.br/ . Aplicação automática do cupom só após confirmação de integração do checkout.

## Origens
pizzaria, panfletos, supermercado, banner2. Mesma página, QR Codes diferentes. A impressão pode agrupar origens conforme orçamento.

## Quantidades
1 ensaio com 10 fotos; 3 cupons 50%; 10 cupons 20%; 150 cupons 10%; 5% sem limite pré-definido.
Distribuir de forma progressiva ao longo de participações, sem esgotar tudo nas primeiras visitas. Definir política de liberação e validade com a proprietária.
Não prometer prêmio grande garantido nem predeterminar resultado individual. Prêmio expirado só retorna ao estoque se o checkout confirmar que não houve resgate.

## Segurança
O navegador não pode escolher o prêmio nem criar cupons válidos. Uma função no servidor precisa registrar participação, usar transação, travar estoque, gerar código único e gravar expiração.
Limitar abusos sem bloquear clientes legítimos. Não confiar apenas em localStorage ou IP.
O checkout deve validar cupom, prazo e uso único do lado do servidor. Sem integração, manter roleta desativada.

## Painel
Acessos, início do vídeo, visualização da roleta, giros, prêmios emitidos, cupons resgatados e reservas por origem. Métricas de reserva dependem de retorno confiável do checkout.

## Pendências
- Receber arquivo ou URL do vídeo oficial do Will.
- Confirmar API ou banco de cupons do checkout Belém.
- Definir validade dos prêmios (proposta: 2h para 50% e ensaio; 24h para 5%, 10% e 20%).
- Criar backend e testes de concorrência e expiração.
- Publicar site separado, configurar domínios e QR Codes, validar no celular.
