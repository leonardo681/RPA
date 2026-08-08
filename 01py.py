import os
import re
import time
from datetime import datetime

try:
    import pyautogui
    import pyperclip
except ImportError as exc:
    raise SystemExit(f"Biblioteca ausente: {exc}. Instale com: pip install pyautogui pyperclip")

# --- TRAVAS DE SEGURANÇA ---
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.8


class RPACorporativo:
    def __init__(self):
        """Coleta os dados do operador e prepara os arquivos de saída."""
        print("--- Iniciando Robô Corporativo ---")
        self.nome = self._validar_nome()
        self.setor = self._validar_setor()
        self.data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.nome_arquivo = (
            f"Relatorio_{re.sub(r'[^A-Za-z0-9_.-]+', '_', self.nome)}_"
            f"{datetime.now().strftime('%d%m%Y_%H%M')}"
        )
        self.pasta_saida = os.path.join(os.getcwd(), "relatorios")
        os.makedirs(self.pasta_saida, exist_ok=True)

    def _validar_nome(self):
        while True:
            nome = input("Digite o nome do operador: ").strip()
            if nome:
                return nome
            print("Nome inválido. Informe um nome válido.")

    def _validar_setor(self):
        setores_validos = ["Financeiro", "RH", "TI"]
        while True:
            setor = input("Digite o setor (Financeiro, RH ou TI): ").strip()
            if setor in setores_validos:
                return setor
            print("Setor inválido. Escolha Financeiro, RH ou TI.")

    def _mostrar_foco(self):
        janela = pyautogui.getActiveWindow()
        if janela:
            print(f"Janela ativa: {janela.title}")

    def abrir_notepad(self):
        """Passo 1: abre o Bloco de Notas e prepara o ambiente."""
        print("Abrindo o Bloco de Notas...")
        os.startfile("notepad.exe")
        time.sleep(3)
        self._mostrar_foco()

    def gerar_relatorio(self):
        """Passo 2: cria o relatório textual e cola no Bloco de Notas."""
        print("Gerando relatório textual...")
        texto = f"""RELATÓRIO DE ATIVIDADES DIÁRIAS
------------------------------
Operador: {self.nome}
Setor: {self.setor}
Data/Hora: {self.data_hora}
Status: Rotina automatizada concluída com sucesso.
------------------------------"""
        pyperclip.copy(texto)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(2)

    def salvar_relatorio(self):
        """Passo 3: salva o relatório como arquivo .txt."""
        pyautogui.hotkey("ctrl", "s")
        time.sleep(2)
        caminho = os.path.join(self.pasta_saida, f"{self.nome_arquivo}.txt")
        print(f"Salvando relatório em {caminho}...")
        pyperclip.copy(caminho)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(1)
        pyautogui.press("enter")
        time.sleep(2)

    def registrar_excel(self):
        """Passo 4: abre o Excel e registra os dados em formato de tabela."""
        print("Abrindo o Excel...")
        os.startfile("excel.exe")
        time.sleep(5)
        pyautogui.press("enter")
        time.sleep(2)

        cabecalhos = "Operador\tSetor\tData/Hora"
        pyperclip.copy(cabecalhos)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("down")
        time.sleep(2)

        dados = f"{self.nome}\t{self.setor}\t{self.data_hora}"
        pyperclip.copy(dados)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(2)

        pyautogui.hotkey("ctrl", "b")
        time.sleep(5)
        caminho = f"{self.nome_arquivo}.txt"
        print(f"Salvando relatório em {caminho}...")
        pyperclip.copy(caminho)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")
        time.sleep(5)

    def gerar_documento_word(self):
        """Passo 5: abre o Word e cria o documento oficial."""
        print("Abrindo o Word...")
        os.startfile("winword.exe")
        time.sleep(5)
        pyautogui.press("enter")
        time.sleep(2)

        texto_relatorio = f"""RELATÓRIO DE ATIVIDADES DIÁRIAS
------------------------------
Operador: {self.nome}
Setor: {self.setor}
Data/Hora: {self.data_hora}
Status: Rotina automatizada concluída com sucesso.
------------------------------"""
        pyperclip.copy(texto_relatorio)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(5)

        pyautogui.hotkey("ctrl", "b")
        time.sleep(5)
        caminho_doc =  f"{self.nome_arquivo}.docx"
        print(f"Salvando documento oficial em {caminho_doc}...")
        time.sleep(5)
        pyperclip.copy(caminho_doc)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")
        time.sleep(5)

    def fechar_programas(self):
        """Passo 6: encerra os programas corretamente."""
        print("Encerrando os programas...")
        for _ in range(3):
            pyautogui.hotkey("alt", "f4")
            time.sleep(10)
            
        print("Aplicações encerradas.")

    def executar(self):
        """Executa o fluxo completo do robô."""
        try:
            self.abrir_notepad()
            self.gerar_relatorio()
            self.salvar_relatorio()
            self.registrar_excel()
            self.gerar_documento_word()
            self.fechar_programas()
            print("Execução finalizada com sucesso!")
        except Exception as exc:
            print(f"Erro durante a automação: {exc}")


if __name__ == "__main__":
    robo = RPACorporativo()
    robo.executar()
