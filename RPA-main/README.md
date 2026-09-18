# TechSolutions Ltda — RPA de cobrança demonstrativo

Projeto acadêmico local que automatiza o ciclo de cobrança com Flask, SQLite, Selenium, PyAutoGUI, PDFs, Excel, WhatsApp Web e Gmail. O sistema inicia em modo demonstrativo: ele mostra mensagens e anexos e grava `Simulado`, sem transmitir mensagens.

## Arquitetura

```text
app.py                 servidor Flask
desktop.py             interface tkinter e fluxo em segundo plano
manage.py              comandos de inicialização e dados fictícios
techsolutions/services  SQLite, validações e valores em centavos
techsolutions/web       rotas, templates Bootstrap e acesso por token
techsolutions/reports   PDFs demonstrativos e relatório Excel
techsolutions/automation Selenium, WhatsApp, SMTP e lotes idempotentes
exemplos/               clientes_exemplo.xlsx e clientes_exemplo.csv
docs/                   roteiro de apresentação e checklist
tests/                  testes automatizados e teste Selenium opt-in
```

## Windows: primeira execução

Abra o PowerShell na pasta do projeto. Com Python 3.11 ou superior instalado:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py demo
python desktop.py
```

Se a política do PowerShell bloquear a ativação, execute diretamente `.venv\Scripts\python.exe`. O comando `manage.py demo` cria o banco em `data/`, cinco clientes, cinco faturas, PDFs, QR Codes e `data/faturas_relatorio.xlsx`. Para subir somente o sistema web use `python app.py`; a senha local é criada em `data/local_admin_password.txt` quando `ADMIN_PASSWORD` está vazio.

Na interface desktop, informe `exemplos/clientes_exemplo.xlsx`, clique em “Iniciar e abrir sistema web”, faça login e use “Importar clientes via RPA”. O robô digita os cinco registros no formulário HTML. Uma segunda execução encontra os mesmos e-mails e os marca como duplicados. Depois use “Gerar PDFs” e “Exportar relatório Excel”. O fluxo completo para quando não existem faturas, pois cadastrar cliente não cria uma dívida automaticamente.

## PDFs e QR Code

Cada arquivo `data/pdfs/fatura_000001_cliente_000001.pdf` é uma fatura demonstrativa com logo, dados do cliente, valor em centavos convertido somente na apresentação, Code128 interno e QR Code. O aviso “FATURA DEMONSTRATIVA — SEM VALIDADE PARA PAGAMENTO” aparece no documento. O Code128 não é linha digitável e o QR Code não é PIX: ele abre `/f/<token>`.

Para abrir o QR Code em um celular na mesma rede, configure no `.env` `WEB_HOST=0.0.0.0` e `PUBLIC_BASE_URL=http://IP_DO_PC:5000`, descubra o IPv4 com `ipconfig`, permita a porta 5000 somente na rede privada e reinicie o servidor. `localhost` no telefone aponta para o próprio telefone. O token é aleatório; ainda assim, compartilhe apenas com o destinatário e não publique a URL.

## Relatório e histórico

O Excel é recriado a partir do banco, mantendo estados de notificação por `fatura_id` e canal. A planilha é lida antes de cada lote e todos os vínculos (cliente, valor, vencimento, caminho, token e PDF) são conferidos contra o SQLite. A reserva transacional impede dois workers de enviar a mesma cobrança. `Falha` só volta ao lote com a caixa “reprocessar falhas”; `Não confirmado` e `Em processamento` exigem verificação manual. Pagamento é uma alteração financeira separada e não é inferido por mensagem enviada.

## WhatsApp Web

O envio real exige modo real aprovado na revisão do lote, navegador visível, contatos autorizados, login manual e `PUBLIC_BASE_URL` acessível ao destinatário. O robô aguarda o login em períodos de 30 segundos, abre a URL codificada `/send?phone=&text=`, usa exclusivamente PyAutoGUI para clicar na imagem de referência e procura uma nova mensagem de saída com texto e marca visual. Clique sem evidência gera “Não confirmado”.

Não há imagem de botão no repositório de propósito. Para capturá-la: abra WhatsApp Web no navegador em 100% de escala, maximize a janela, use a ferramenta de captura do Windows somente sobre o botão Enviar, salve como `assets/whatsapp_send.png` e mantenha tema, zoom e monitor iguais. `locateOnScreen` depende de resolução, escala, tema e OpenCV; se encontrar zero ou mais de um candidato, o envio é suspenso. Não use contatos sem autorização nem tente contornar limites da plataforma.

## Gmail

Configure no `.env` `SMTP_USER`, `SMTP_PASSWORD` e opcionalmente `SMTP_FROM`. Use `smtp.gmail.com` com porta 465 (SSL) ou 587 (STARTTLS). Em contas com verificação em duas etapas, crie uma senha de app na Conta Google; nunca coloque a senha real no repositório. O servidor aceitar a mensagem significa apenas aceitação SMTP, não confirmação de recebimento ou leitura. O PDF é escolhido pelo ID e verificado por hash antes do envio.

## Segurança local

Não versionar `.env`, `data/`, cookies, perfis de navegador, PDFs reais ou imagens de sessão. O Flask usa senha local, sessão HTTPOnly, CSRF, cabeçalhos de privacidade e tokens não previsíveis para faturas públicas. Este projeto é para apresentação local; não substitui autenticação corporativa, armazenamento de segredos, antivírus, auditoria ou um portal público de cobrança.

## Testes e limites da validação

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Os testes automatizados cobrem valores em centavos, duplicidade, banco, PDFs, QR Code, Excel, histórico, revisão de lote, idempotência, Gmail simulado, GUI e interrupção. O teste de navegador opcional usa Chrome instalado e grava evidência em `data/validacao/`:

```powershell
.\.venv\Scripts\python.exe tests/run_selenium_check.py
```

Login do WhatsApp, leitura do QR Code, captura da imagem, senha de app Gmail, firewall da rede e confirmação de recebimento dependem do computador do apresentador. Nenhum envio real ou recebimento foi afirmado pelo projeto.

O roteiro em cinco partes está em [docs/ROTEIRO_APRESENTACAO.md](docs/ROTEIRO_APRESENTACAO.md), e a correspondência dos requisitos está em [docs/CHECKLIST.md](docs/CHECKLIST.md).
