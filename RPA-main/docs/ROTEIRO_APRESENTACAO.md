# Roteiro de apresentação — TechSolutions Ltda

Este roteiro organiza o trabalho em **cinco partes**. Reserve cerca de 15 a 20 minutos, além da preparação. Todos os clientes e documentos fornecidos são fictícios. A execução começa em modo demonstrativo, que não envia mensagens reais.

## Preparação

1. Siga o README para instalar Python, criar o ambiente virtual e instalar `requirements.txt`.
2. Configure `.env` a partir de `.env.example`. Para demonstrar no celular, ajuste `PUBLIC_BASE_URL` **antes de gerar PDFs** para o endereço de rede do computador, conforme o README.
3. Inicie a interface com `python desktop.py` e use **Iniciar e abrir sistema web**. Consulte a senha em `data/local_admin_password.txt` se `ADMIN_PASSWORD` não foi definida.
4. Mantenha **Modo demonstrativo** marcado. Use um banco novo para demonstrar os cinco cadastros efetivos; em um banco já populado, os mesmos registros deverão aparecer como duplicidades.
5. Tenha o navegador Chrome disponível para o Selenium. A apresentação de WhatsApp real também depende do navegador visível, sessão iniciada e imagem do botão capturada no próprio computador.
6. Para os envios reais opcionais, preencha destinatários de teste autorizados. Verifique o conteúdo dos documentos antes de enviar dados a um contato de teste.

Não mostre `.env`, senhas de app, cookies ou a senha administrativa durante a apresentação.

## Parte 1 — Sistema web, clientes e persistência

**Objetivo:** apresentar o cadastro via navegador e o armazenamento persistente.

1. Mostre o painel, a listagem de clientes e o formulário de cadastro.
2. Na janela desktop, selecione `clientes_exemplo.xlsx` ou `clientes_exemplo.csv` e clique em **Importar clientes via RPA**.
3. Mostre o navegador sendo preenchido pelo Selenium: nome, e-mail, telefone e endereço, seguido do clique em salvar.
4. Confira cinco clientes no sistema. O resumo da interface mostra sucessos, falhas e registros ignorados.
5. Execute novamente o mesmo arquivo. O e-mail normalizado identifica duplicidades; o total de clientes não deve aumentar.
6. Se desejar mostrar tolerância a falhas, faça uma **cópia** da planilha, inclua uma linha com e-mail inválido entre linhas válidas e importe essa cópia. Mostre a falha registrada e a continuação das outras linhas.
7. Edite um cliente pelo sistema web e recarregue a página para mostrar a persistência.

**Evidência a mostrar:** navegador preenchendo formulário, clientes salvos e segunda importação sem duplicidades. Não atribua o cadastro por formulário ao comando de carga demonstrativa; são funcionalidades distintas.

## Parte 2 — Faturas, situação financeira e documentos

**Objetivo:** mostrar associação entre cliente e fatura, valores precisos e documentos individuais.

1. Cadastre faturas pelo sistema, escolhendo um cliente em cada uma. Há também uma carga de cinco faturas fictícias descrita no README; ela pode ser executada após a demonstração da importação.
2. Mostre uma fatura pendente futura, uma vencida e uma paga. Use filtros de cliente, vencimento e status.
3. Registre manualmente o pagamento de uma fatura de demonstração. Mostre o efeito no painel e a permanência independente do histórico de notificações.
4. Gere um PDF individual pela web e depois use **Gerar PDFs** no desktop para a geração em lote.
5. Abra o documento e confira cliente, número, emissão, vencimento, valor, QR Code e código de barras.
6. Aponte a identificação **FATURA DEMONSTRATIVA — SEM VALIDADE PARA PAGAMENTO**. Explique que o código de barras identifica a fatura; o QR Code abre uma página da fatura e não é PIX.
7. Abra o QR Code no celular somente se o endereço configurado estiver acessível na mesma rede. `localhost` no celular aponta para o próprio celular.

**Evidência a mostrar:** cada PDF corresponde à sua fatura e o pagamento foi uma ação manual explícita. O acesso de demonstração por link é protegido por token; trate o link como informação reservada.

## Parte 3 — Relatório Excel e controle dos envios

**Objetivo:** comprovar que a planilha é entrada efetiva das automações e que IDs relacionam os registros.

1. Clique em **Exportar relatório Excel**.
2. Abra `faturas_relatorio.xlsx`, no caminho mostrado nos logs. Mostre `fatura_id`, `cliente_id`, dados do cliente, valor, vencimento, status financeiro, PDF, link e os campos de envio de ambos os canais.
3. Feche o Excel antes de continuar, pois o Windows pode manter o arquivo bloqueado para gravação.
4. Mostre na revisão de um lote que as faturas pagas não são elegíveis para cobrança.
5. Explique o fluxo: banco → exportação → leitura do Excel → tentativa → gravação no banco e no Excel.
6. Após simular um canal, exporte novamente e mostre que o histórico persistido continua presente.

**Evidência a mostrar:** o status financeiro continua independente de `status_whatsapp` e `status_email`. A simulação gera **Simulado**; esse resultado não impede um envio real posteriormente. Envios reais já concluídos não entram novamente de forma automática.

## Parte 4 — WhatsApp Web e Gmail

**Objetivo:** mostrar a mensagem personalizada, a associação ao documento e o registro honesto do resultado.

1. Com o modo demonstrativo marcado, clique em **Enviar WhatsApp**. Revise o destinatário efetivo, nome, número, valor, vencimento, link e mensagem. Confirme a simulação e mostre o resultado **Simulado**.
2. Repita com **Enviar e-mails**. Confira o destinatário, a fatura e o PDF associado por ID. O PDF não é escolhido pela posição na pasta.
3. Mostre os resultados na planilha e no histórico do sistema web.
4. Para a demonstração real opcional, informe um contato de teste autorizado e desmarque o modo demonstrativo. Revise o lote e marque a confirmação de autorização para habilitar o botão de envio.
5. WhatsApp: conclua o login por QR Code em até 30 segundos ou use a opção de continuar aguardando. Mantenha resolução, escala e tema iguais aos usados ao capturar a imagem. Mostre o PyAutoGUI localizando e clicando no botão de envio.
6. Explique que clicar no botão não basta: o sistema busca evidência da mensagem na interface. Sem evidência suficiente, registra **Não confirmado** e não reenvia automaticamente.
7. Gmail: o envio depende de configuração SMTP e senha de app quando disponível para a conta. A aceitação pelo servidor não comprova recebimento; abra a caixa de entrada do destinatário autorizado para conferência manual.
8. Se uma falha ocorrer, mostre `erros.csv` e o erro registrado no Excel. **Reprocessar falhas anteriores** é uma escolha explícita; resultados incertos exigem conferência manual.

**Evidência a mostrar:** simulação concluída ou evidência real observada no seu computador. Se não houver login, credenciais ou contato autorizado, apresente a simulação e declare que o envio real não foi executado.

## Parte 5 — Interface desktop, integração e interrupção

**Objetivo:** demonstrar o controle integrado sem travar a janela.

1. Mostre os botões das etapas, a seleção de arquivo, o endereço web, os contatos de teste, os logs, o progresso e o resumo.
2. Execute **Fluxo completo**. Ele importa clientes se um arquivo estiver selecionado, verifica a existência de faturas, gera PDFs, exporta o Excel e revisa os lotes dos dois canais.
3. Explique o caso sem faturas: a interface informa que é necessário cadastrá-las; a importação de clientes não cria dívidas automaticamente.
4. Durante um processamento, mova a janela e acompanhe os logs para demonstrar que o trabalho roda em segundo plano.
5. Clique em **Solicitar interrupção segura**. A tentativa em andamento termina em um ponto seguro e os resultados já registrados são preservados. Operações externas podem aguardar o respectivo tempo limite antes de encerrar.
6. Reabra o relatório e o histórico para conferir que as tentativas concluídas antes da interrupção continuam registradas.

**Evidência a mostrar:** janela responsiva, resumo coerente, preservação dos resultados e nenhum pagamento atribuído automaticamente ao envio de uma mensagem.

## Registro dos resultados da apresentação

Preencha este registro com as evidências efetivamente observadas:

| Verificação | Resultado / evidência local |
|---|---|
| Cinco clientes cadastrados pelo formulário Selenium | |
| Segunda importação sem criar duplicidades | |
| Cliente, fatura, PDF e destinatário correspondentes | |
| QR Code lido no computador ou celular | |
| Excel lido e atualizado após as tentativas | |
| Histórico preservado após nova exportação | |
| Pagamento manual separado do envio | |
| Simulação sem envio externo | |
| WhatsApp real e evidência observada, se autorizado | |
| Gmail real aceito por SMTP, se autorizado | |
| Recebimento do e-mail conferido manualmente | |
| Janela responsiva e cancelamento seguro | |

O checklist do projeto descreve funcionalidades implementadas; esta tabela registra a validação específica no computador da apresentação.
