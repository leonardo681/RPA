# Checklist de requisitos — TechSolutions Ltda

Este documento relaciona o enunciado às funcionalidades e aos pontos de verificação. A existência da implementação não equivale a comprovar envio real. Consulte o README e o registro de validação do projeto para os testes efetivamente executados.

| Requisito | Implementação e como verificar |
|---|---|
| 1. Fluxo de cobrança completo | Desktop coordena importação → conferência de faturas → PDFs → Excel → leitura do Excel → notificações → atualização dos resultados. |
| 2. Python e arquitetura modular | `techsolutions/web`, `services`, `automation`, `reports` e `gui` separam apresentação, persistência/regras e automação. |
| 2. Tecnologias exigidas | Flask/SQLite, Bootstrap, Selenium, PyAutoGUI, pandas/openpyxl, ReportLab, qrcode, código de barras Code128, smtplib/email.message, dotenv e tkinter. Dependências externas em `requirements.txt`. |
| 3. Tabela clientes | Identificador, nome, e-mail, telefone, endereço e data de cadastro; criação inicial pelo repositório. |
| 3. Tabela faturas | Cliente relacionado, valor em centavos, vencimento, situação financeira, emissão e PDF. |
| 3. Tabela notificações | Relação com fatura e cliente, canal, status, data/hora e erro. |
| 3. Cadastro, edição e listagem | Formulários web com validação de campos, e-mail e telefone; listagem e edição. |
| 3. Faturas e filtros | Cadastro selecionando cliente, listagem por cliente/vencimento/status, visualização/download e pagamento manual. |
| 3. Painel | Totais de clientes, situações das faturas e valores em aberto. |
| 3. Precisão monetária | Regras usam centavos inteiros e conversão decimal; a apresentação formata reais sem calcular dívidas com float. |
| 3. Situação financeira separada | Notificação atualiza seu próprio histórico. Registrar envio não registra pagamento. |
| 4. Exemplos Excel/CSV | Arquivos `clientes_exemplo.xlsx` e `.csv` com ao menos cinco clientes fictícios. |
| 4. Seleção e validação | Seletor desktop, verificação de colunas e validação por linha. |
| 4. Selenium obrigatório | Robô abre e preenche o formulário web, clica em salvar e verifica a resposta. Não cadastra por API ou acesso direto ao banco. |
| 4. Duplicidade | E-mail normalizado identifica o mesmo cliente. Reexecute a planilha e confira que o total não aumenta. |
| 4. Continuação após erro | Resumo de sucessos/falhas/ignorados; uma linha inválida não impede o restante. |
| 5. Documento por fatura | PDF contém identidade visual, dados do cliente, número, datas, valor, Code128 e QR Code. |
| 5. Arquivos e lote | Nome exclusivo por fatura/cliente; geração individual web e geração em lote no desktop. |
| 5. Identificação demonstrativa | O PDF declara “FATURA DEMONSTRATIVA — SEM VALIDADE PARA PAGAMENTO”. |
| 5. QR Code e código de barras | QR contém URL da página protegida por token; Code128 representa identificador de demonstração. Não são PIX nem boleto registrado. |
| 5. Celular na rede | README orienta configurar URL pública com IP local, interface de rede e firewall, antes de gerar o documento. |
| 5. Pagamento | Somente ação financeira correspondente altera a fatura para paga; o QR e o envio não confirmam pagamento. |
| 6. Colunas do relatório | `fatura_id`, `cliente_id`, `nome`, `telefone`, `email`, `valor`, `vencimento`, `status_fatura`, `caminho_pdf`, `link_fatura`, `status_whatsapp`, `data_envio_whatsapp`, `status_email`, `data_envio_email`, `erro_whatsapp`, `erro_email`. |
| 6. Excel como entrada | A preparação dos lotes lê a planilha exportada; os IDs e o estado do banco são conferidos antes dos envios. |
| 6. Resultados por tentativa | Cada tentativa é registrada no banco e refletida no Excel, com identificação da fatura e do canal. |
| 6. Histórico preservado | Nova exportação recompõe os resultados a partir do histórico persistido. |
| 6. Elegibilidade financeira | Apenas cobranças em aberto elegíveis entram no lote; faturas pagas são excluídas. |
| 6. Sem reenvio automático | Resultados reais concluídos e incertos não entram automaticamente. Simulação não se confunde com envio real. |
| 6. Reprocessamento explícito | Operador marca “Reprocessar falhas anteriores neste lote”; resultado incerto exige conferência manual. |
| 7. Telefone brasileiro | Normalização e validação com código 55 antes da preparação do envio. |
| 7. Mensagem e URL | Nome, fatura, valor e vencimento personalizados; mensagem codificada na URL do WhatsApp Web. |
| 7. Login | Espera inicial de até 30 segundos e pergunta explícita para continuar aguardando. |
| 7. Clique por imagem | PyAutoGUI procura uma imagem de referência capturada no computador e clica no botão de envio. |
| 7. Fatura na mensagem | Link acessível para a fatura correspondente, que permite consultar seus dados e documento. O caminho local do PDF não é enviado como URL pública. |
| 7. Sequência | Processamento de uma cobrança por vez e encerramento das abas temporárias quando aplicável. |
| 7. Falhas | Tratamento de telefone inválido, login, botão, conexão, tempo limite e número sem WhatsApp quando identificável na interface. |
| 7. Evidência de envio | Verificação posterior ao clique; resultado insuficiente vira “Não confirmado” e bloqueia repetição automática. |
| 7. Registro de erros | CSV de erros com data/hora, fatura, canal e motivo, além de histórico e relatório. |
| 7. Referência visual | Instruções de captura e limitações de resolução, escala e tema. Não há imagem fictícia de botão apresentada como referência real. |
| 7. Contatos autorizados | Revisão do lote real exige confirmação do operador; não há mecanismo para contornar bloqueios da plataforma. |
| 8. Gmail SMTP | `smtp.gmail.com`, SSL/465 ou STARTTLS/587, credenciais em variáveis de ambiente. |
| 8. Segredos | `.env.example` sem credenciais reais; `segredos.py` somente carrega configurações. |
| 8. Assunto, corpo e anexo | Assunto com vencimento, corpo personalizado e PDF vinculado à fatura. |
| 8. Destinatário e documento | Conferência de cliente, destinatário, fatura e PDF; revisão mostra o redirecionamento quando houver contato de teste. |
| 8. Erros SMTP | Endereço inválido, configuração ausente, autenticação recusada, conexão e documento inexistente geram registro. |
| 8. Recebimento | Aceitação SMTP é distinta de confirmação de recebimento, que deve ser observada manualmente. |
| 9. Controles desktop | Arquivo, endereço web, iniciar/abrir sistema, RPA, PDFs, Excel, WhatsApp, e-mail, fluxo completo e interrupção. |
| 9. Acompanhamento | Barra de progresso, área de logs e resumo de sucessos/falhas/ignorados/simulados. |
| 9. Responsividade | Thread executa tarefas; fila de eventos entrega atualizações à thread principal do tkinter. |
| 9. Fluxo sem faturas | Mensagem orienta cadastrar faturas antes de gerar cobranças; importação de clientes não cria dívidas automaticamente. |
| 9. Interrupção segura | Evento solicita parada entre unidades de trabalho e preserva registros concluídos. |
| 10. Demonstração padrão | GUI sempre inicia com modo demonstrativo; nenhuma variável ativa automaticamente o envio real. |
| 10. Revisão dos lotes | Modal exibe destinatário efetivo/original, mensagem, fatura, PDF e link; confirmação obrigatória antes de envio real. |
| 10. Destinatários de teste | Campos editáveis na GUI e configurações de ambiente, específicos de cada canal. |
| 10. Simulações | Registradas como “Simulado”, preservando a possibilidade de envio real posterior. |
| 10. Proteção de dados | Login administrativo, proteção dos PDFs e links com tokens; segredos, sessões e saídas locais excluídos pelo `.gitignore`. |
| 10. Limitações locais | README documenta escopo de apresentação local, links reservados e cuidados com exposição em rede. |
| 11. Entregáveis | Código, árvore de diretórios, dependências, configuração, inicialização, dados/arquivos exemplo, logo, relatórios, GUI, README, roteiro e checklist. |
| 12. Testes possíveis | Testes automatizados e validações executadas são descritos no registro de validação; conferir evidências reais do ambiente. |
| 12. Dependências externas | Login/conta WhatsApp, Gmail, contatos autorizados, referência de tela e leitura de QR no celular dependem do computador da apresentação. |
| 13. Projeto executável | Arquivos reais implementados, pontos de entrada documentados e configuração demonstrativa disponível. |

## Verificações locais antes da apresentação

- [ ] Ambiente instalado e banco inicializado.
- [ ] Cinco clientes importados pelo formulário Selenium, com navegador visível.
- [ ] Reexecução reconhece duplicidades por e-mail normalizado.
- [ ] Cinco faturas de demonstração relacionadas aos clientes corretos.
- [ ] PDFs com dados e identificadores correspondentes.
- [ ] QR Code legível e URL acessível no dispositivo utilizado.
- [ ] Relatório exportado e lido pelas automações.
- [ ] Resultados gravados após cada tentativa e preservados após nova exportação.
- [ ] Envios reais concluídos não voltam automaticamente ao lote.
- [ ] Situação financeira separada do resultado de notificação.
- [ ] Destinatários e anexos conferidos na revisão.
- [ ] Janela responsiva e interrupção segura observadas.
- [ ] WhatsApp real, somente se autorizado e configurado: evidência posterior ao clique conferida.
- [ ] Gmail real, somente se autorizado e configurado: aceitação SMTP e recebimento manual diferenciados.

Marque apenas o que foi efetivamente validado. Nenhum item desta lista declara que mensagens reais foram enviadas ou recebidas.
