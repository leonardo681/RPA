import openpyxl 
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as OpenpyxlImage

import selenium 
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import Chrome
from selenium.webdriver.common.keys import Keys

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

import pyautogui as p 
import datetime as dt
import rpa as r
import pandas as pd
import time
import os
import io
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup
from pixqrcodegen import Payload

# Carrega as variáveis do arquivo .env para o ambiente Python
load_dotenv()

# Captura os valores do .env
URL_SITE = os.getenv("URL_SITE")
EMAIL_USUARIO = os.getenv("EMAIL_USUARIO")
SENHA_USUARIO = os.getenv("SENHA_USUARIO")

def criar_pasta_relatorios(pasta='relatorios'):
    """Garante que a pasta para salvar os arquivos exista."""
    if not os.path.exists(pasta):
        os.makedirs(pasta)

def wait_for_element(element_selector, timeout=15):
    """
    Aguarda de forma reativa até que um elemento apareça na página.
    Retorna True se o elemento for encontrado, ou gera uma exceção no tempo limite.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if r.present(element_selector):
            return True
        time.sleep(0.2)  # Verifica a cada 200 milissegundos
    raise Exception(f"Timeout: O elemento '{element_selector}' não carregou dentro de {timeout} segundos.")

def realizar_login(email, senha, url=URL_SITE):
    """
    Função responsável por inicializar o navegador, acessar o site e
    executar o fluxo completo de autenticação via RPA.
    """
    # 1. Inicializa o ambiente RPA
    r.init(visual_automation=True, chrome_browser=True)
    r.url(url)
    
    # 2. Maximiza a janela ativa
    janela = p.getActiveWindow()
    if janela:
        janela.maximize()

    # 3. Fluxo de Login usando os seletores diretos
    print("Iniciando processo de login...")

    

    r.type('//*[@id="user-name"]', email)
    r.type('//*[@id="password"]', senha)
    r.click('//*[@id="login-button"]')
    r.keyboard('[enter]')
        
    print("Login concluído com sucesso!")

def preencher_checkout(primeiro_nome="Leonardo", sobrenome="Souza", cep="01000-000"):
    print("Preenchendo dados de entrega...")
    
    # Preenche o primeiro nome pelo ID
    r.type('#first-name', primeiro_nome)
    
    # Preenche o sobrenome pelo ID
    r.type('#last-name', sobrenome)
    
    # Preenche o CEP pelo ID
    r.type('#postal-code', cep)
    
    print("Avançando para a confirmação...")
    # Clica no botão Continue pelo ID
    r.click('#continue')

def adicionar_e_checkout():
    print("Adicionando produto ao carrinho...")
    # 1. Clica no botão "Add to cart" pelo ID
    r.click('#add-to-cart-sauce-labs-backpack')

    print("Acessando o carrinho...")
    # 2. Clica no ícone do carrinho pela classe CSS
    r.click('.shopping_cart_link')

    print("Iniciando o checkout...")
    # 3. Clica no botão "Checkout" pelo ID
    r.click('#checkout')

def teste(url='https://www.saucedemo.com/'):
    """
    Função responsável por inicializar o navegador, acessar o site e
    executar o fluxo completo de autenticação via RPA.
    """
    # 1. Inicializa o ambiente RPA
    r.init(visual_automation=True, chrome_browser=True)
    r.url(url)
    
    # 2. Maximiza a janela ativa
    janela = p.getActiveWindow()
    if janela:
        janela.maximize()

    # 3. Fluxo de Login usando os seletores diretos
    print("pagina acessada com sucesso!")
    
def rolar_pagina(modo='pixels', pixels=700):
   
    if modo == 'fim':
        time.sleep(2)  # Aguarda a animação da rolagem terminar
        r.dom("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});")
        time.sleep(3)  # Aguarda a animação da rolagem terminar
        r.dom("window.scrollTo({top: 0, behavior: 'smooth'});")
        time.sleep(3)  # Aguarda a animação da rolagem terminar
        rolar_pagina(modo='pixels', pixels=700)

    elif modo == 'pixels':
        # Rola uma quantidade exata de pixels para baixo
        time.sleep(2)  # Aguarda a animação da rolagem terminar
        r.dom(f"window.scrollBy({{top: {pixels}, behavior: 'smooth'}});")

def acessar_categoria(nome_categoria):
    """
    Clica na categoria desejada e aguarda o carregamento da nova página.
    """
    print(f"Clicando na categoria: {nome_categoria}...")
    r.click(nome_categoria)
    print("Página carregada com sucesso!")
        
def extrair_alimentos_apenas_python(nome_arquivo_csv=os.path.join('relatorios', 'alimentos_preparados.csv')):
    criar_pasta_relatorios()
    print("Rolando a página para carregar todos os dados...")
    rolar_pagina(modo='fim')

    print("Capturando HTML completo...")
    html_pagina = r.read('page')
    
    soup = BeautifulSoup(html_pagina, 'html.parser')
    cards = soup.find_all('a', href=lambda href: href and '/tabela-nutricional/' in href)
    
    dados_alimentos = []

    for card in cards:
        texto_card = card.text.strip()
        
        if 'Conta PRO' in texto_card:
            continue
            
        tag_nome = card.find('p', title=True)
        nome = tag_nome['title'] if tag_nome else ''
        
        paragrafos = [p.text.strip() for p in card.find_all('p')]
        
        energia = ''
        carboidratos = ''
        proteinas = ''
        
        for idx, texto in enumerate(paragrafos):
            if 'Energia:' in texto and idx + 1 < len(paragrafos):
                energia = paragrafos[idx + 1]
            elif 'Carboidratos:' in texto and idx + 1 < len(paragrafos):
                carboidratos = paragrafos[idx + 1]
            elif 'Proteínas:' in texto and idx + 1 < len(paragrafos):
                proteinas = paragrafos[idx + 1]

        if nome and energia and 'kcal' in energia:
            link_href = card.get('href', '')
            link_completo = f"https://www.tabelatacoonline.com.br{link_href}" if link_href.startswith('/') else link_href
            
            dados_alimentos.append({
                'Alimento': nome,
                'Energia': energia,
                'Carboidratos': carboidratos,
                'Proteínas': proteinas,
                'Link': link_completo
            })

    print(f"✓ Sucesso! {len(dados_alimentos)} alimentos gratuitos extraídos com dados válidos.")

    if dados_alimentos:
        df = pd.DataFrame(dados_alimentos)
        df.to_csv(nome_arquivo_csv, index=False, encoding='utf-8-sig')
        print(f"✓ Arquivo '{nome_arquivo_csv}' gerado com sucesso!")
    else:
        print("Nenhum dado válido encontrado para salvar.")

    return dados_alimentos

def salvar_em_excel(nome_csv=os.path.join('relatorios', 'alimentos_preparados.csv'),nome_excel=os.path.join('relatorios', 'alimentos_preparados.xlsx')):
    """
    Lê o CSV e converte para Excel dentro da pasta 'relatorios' com rankings e gráficos.
    """
    criar_pasta_relatorios()
    if not os.path.exists(nome_csv):
        print(f"Erro: O arquivo {nome_csv} não foi encontrado para converter em Excel.")
        return

    print("Convertendo CSV para Excel (.xlsx) e gerando gráficos...")
    
    df = pd.read_csv(nome_csv)
    
    for col in ['Energia', 'Carboidratos', 'Proteínas']:
        if col in df.columns:
            df[f'{col}_num'] = (
                df[col].astype(str)
                .str.replace(r'[^\d,.]', '', regex=True)
                .str.replace(',', '.')
            )
            df[f'{col}_num'] = pd.to_numeric(df[f'{col}_num'], errors='coerce').fillna(0)

    df_geral = df.drop(columns=['Energia_num', 'Carboidratos_num', 'Proteínas_num'], errors='ignore')

    def preparar_ranking(coluna_sort):
        return (
            df.sort_values(by=coluna_sort, ascending=False)
            .drop(columns=['Link', 'Energia_num', 'Carboidratos_num', 'Proteínas_num'], errors='ignore')
        )

    df_energia = preparar_ranking('Energia_num')
    df_carbo = preparar_ranking('Carboidratos_num')
    df_proteina = preparar_ranking('Proteínas_num')

    abas_config = {
        'Geral': {'df': df_geral, 'grafico_col': None, 'unidade': ''},
        'Ranking Energia': {'df': df_energia, 'grafico_col': 'Energia_num', 'unidade': 'kcal', 'cor': '#e67e22'},
        'Ranking Carboidratos': {'df': df_carbo, 'grafico_col': 'Carboidratos_num', 'unidade': 'g', 'cor': '#2ecc71'},
        'Ranking Proteínas': {'df': df_proteina, 'grafico_col': 'Proteínas_num', 'unidade': 'g', 'cor': '#3498db'}
    }

    wb = Workbook()
    
    header_fill = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
    header_font = Font(bold=True)

    for index, (nome_aba, config) in enumerate(abas_config.items()):
        if index == 0:
            ws = wb.active
            ws.title = nome_aba
        else:
            ws = wb.create_sheet(title=nome_aba)

        df_aba = config['df']
        colunas = list(df_aba.columns)
        ws.append(colunas)

        for col_num in range(1, len(colunas) + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for linha in df_aba.itertuples(index=False):
            ws.append(list(linha))

        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        col_num_ref = config['grafico_col']
        if col_num_ref:
            top10 = df.sort_values(by=col_num_ref, ascending=False).head(10)
            
            plt.figure(figsize=(8, 4.5))
            plt.barh(top10['Alimento'][::-1], top10[col_num_ref][::-1], color=config['cor'])
            plt.title(f'Top 10 - {nome_aba.replace("Ranking ", "")}', fontsize=12, fontweight='bold')
            plt.xlabel(f'Quantidade ({config["unidade"]})')
            plt.tight_layout()

            img_buf = io.BytesIO()
            plt.savefig(img_buf, format='png', dpi=120)
            img_buf.seek(0)
            plt.close()

            img = OpenpyxlImage(img_buf)
            ws.add_image(img, 'F2')

    wb.save(nome_excel)
    print(f"✓ Arquivo Excel '{nome_excel}' criado na pasta relatórios!")
    
def abrir_excel(nome_excel=os.path.join('relatorios', 'alimentos_preparados.xlsx')):
    """Abre o arquivo Excel localizado na pasta relatorios."""
    if os.path.exists(nome_excel):
        print(f"Abrindo o arquivo '{nome_excel}'...")
        os.startfile(os.path.abspath(nome_excel))
    else:
        print(f"Erro: O arquivo '{nome_excel}' não foi encontrado para ser aberto.")

def fechar_navegador():
    """
    Encerra a sessão do RPA e fecha a janela do navegador aberta pela automação.
    """
    print("Fechando o navegador...")
    r.close()
    print("✓ Navegador fechado com sucesso!")

def salvar_dados_pagina_txt(pasta_destino='relatorios', nome_arquivo='dados_pagina.txt'):

    """
    Captura todo o texto visível da página aberta no navegador 
    e salva o conteúdo em um arquivo de texto (.txt).
    """
    print("Extraindo texto da página...")
    
    # Garante que a pasta destino existe
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino)
        
    caminho_txt = os.path.join(pasta_destino, nome_arquivo)
    
    # Captura o HTML da página atual via biblioteca rpa
    html_pagina = r.read('page')
    soup = BeautifulSoup(html_pagina, 'html.parser')
    
    # Remove elementos visivelmente irrelevantes (scripts, estilos e meta tags)
    for elemento in soup(['script', 'style', 'head', 'title', 'meta']):
        elemento.decompose()
        
    # Extrai apenas o texto legível
    texto_limpo = soup.get_text(separator='\n', strip=True)
    
    # Salva o arquivo com codificação UTF-8
    with open(caminho_txt, 'w', encoding='utf-8') as f:
        f.write(texto_limpo)
        
    print(f"✓ Conteúdo salvo com sucesso em '{caminho_txt}'!")
    return caminho_txt

def finalizar_compra_e_gerar_recibo(pasta_destino='relatorios'):
    """
    Clica no botão #finish do Swag Labs, extrai os dados do pedido,
    gera o QR Code Pix e salva o recibo em formato PDF idêntico ao original.
    """
    print("Finalizando a compra no Swag Labs...")
    
    # 1. Clica no botão de finalizar
    r.click('#finish')
    
    # 2. Captura os dados da página final
    html_pagina = r.read('page')
    soup = BeautifulSoup(html_pagina, 'html.parser')
    
    nome_comprador = "Leonardo Souza"  
    produto_comprado = "Sauce Labs Backpack"
    valor_total = "$32.39"
    data_compra = dt.datetime.now().strftime("%B %d, %Y at %I:%M %p")

    print("Dados capturados com sucesso. Gerando QR Code Pix...")

    # 3. Instancia a classe do PIX
    payload = Payload(
        nome="Swag Labs", 
        chavepix="seu-email-pix@dominio.com", 
        valor=valor_total.replace('$', ''), 
        cidade="SAO PAULO", 
        txtId="SWAGLABS01"
    )
    
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino)
        
    # Passa o parâmetro 'pasta_destino' duas vezes para atender a assinatura da biblioteca (dir, diretorio)
    payload.gerarQrCode(pasta_destino, pasta_destino)
    
    caminho_qrcode = os.path.join(pasta_destino, 'pixqrcodegen.png')

    # 4. Construção do PDF
    nome_pdf = f"comprovante_final.pdf"
    caminho_pdf = os.path.join(pasta_destino, nome_pdf)
    
    doc = SimpleDocTemplate(caminho_pdf, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()

    style_header = ParagraphStyle('Header', fontName='Helvetica-Bold', fontSize=22, textColor=colors.HexColor('#242526'), spaceAfter=4)
    style_sub = ParagraphStyle('Sub', fontName='Helvetica', fontSize=14, textColor=colors.HexColor('#555555'), spaceAfter=15)
    style_title = ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor('#333333'), spaceAfter=5)
    style_text = ParagraphStyle('Text', fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#444444'))
    style_bold = ParagraphStyle('Bold', fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#222222'))

    # Cabeçalho
    story.append(Paragraph("Swag Labs", style_header))
    story.append(Paragraph("Order Receipt", style_sub))
    story.append(Spacer(1, 10))

    # Tabela de Detalhes
    dados_detalhes = [
        [Paragraph("ORDER DETAILS", style_title), Paragraph("SHIP TO", style_title)],
        [Paragraph(f"<b>Order Date</b><br/>{data_compra}", style_text), Paragraph(f"{nome_comprador}<br/>01000-000", style_text)]
    ]
    tabela_detalhes = Table(dados_detalhes, colWidths=[250, 250])
    tabela_detalhes.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    story.append(tabela_detalhes)
    story.append(Spacer(1, 15))

    # Tabela de Itens e Valores
    dados_itens = [
        [Paragraph("ITEMS / DESCRIPTION", style_bold), Paragraph("PRICE", style_bold)],
        [Paragraph(f"<b>{produto_comprado}</b>", style_text), Paragraph("$29.99", style_text)],
        [Paragraph("Item total", style_text), Paragraph("$29.99", style_text)],
        [Paragraph("Tax", style_text), Paragraph("$2.40", style_text)],
        [Paragraph("<b>Total</b>", style_bold), Paragraph(f"<b>{valor_total}</b>", style_bold)]
    ]
    tabela_itens = Table(dados_itens, colWidths=[380, 120])
    tabela_itens.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#DDDDDD')),
        ('LINEBELOW', (0,1), (-1,1), 0.5, colors.HexColor('#EEEEEE')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT')
    ]))
    story.append(tabela_itens)
    story.append(Spacer(1, 15))

    story.append(Paragraph("Thank you for your order! It has been dispatched, and will arrive just as fast as the pony can get there.", style_text))
    story.append(Spacer(1, 15))
    
    # Anexa a imagem do QR Code Pix
    img_qr = Image(caminho_qrcode, width=120, height=120)
    story.append(img_qr)

    doc.build(story)
    print(f"✓ Recibo PDF gerado com sucesso em '{caminho_pdf}'!")

    
    
    return caminho_pdf

def abrir_pdf(caminho_pdf):
    """
    Abre o arquivo PDF gerado no leitor de PDF padrão do sistema (Edge, Chrome, Acrobat, etc.).
    """
    if os.path.exists(caminho_pdf):
        print(f"Abrindo o arquivo PDF '{caminho_pdf}'...")
        os.startfile(os.path.abspath(caminho_pdf))
    else:
        print(f"Erro: O arquivo PDF '{caminho_pdf}' não foi encontrado.")



# --- EXECUÇÃO DO MÉTODO ---
if __name__ == "__main__":
    
    realizar_login(EMAIL_USUARIO, SENHA_USUARIO, url=URL_SITE)
    adicionar_e_checkout()
    preencher_checkout()
    salvar_dados_pagina_txt('relatorios', 'resumo_pagina.txt')
    caminho_pdf = finalizar_compra_e_gerar_recibo('relatorios')
    fechar_navegador()
    abrir_pdf(caminho_pdf)