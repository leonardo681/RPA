"""WhatsApp Web: navegação Selenium e clique de envio por reconhecimento de imagem.

Seletores acompanham a interface pública atual e podem exigir ajustes quando a
plataforma muda. Sem evidência positiva o resultado é sempre Não confirmado.
"""

from __future__ import annotations

import ipaddress
import time
from pathlib import Path
from threading import Event
from urllib.parse import urlencode, urlparse, parse_qs

from .emailer import DeliveryError
from .importer import create_driver
from techsolutions.services.validation import normalize_phone


def validate_accessible_link(link):
    parsed = urlparse(link)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise DeliveryError("A fatura precisa de um link HTTP(S) acessível.")
    blocked = hostname == "localhost" or hostname.endswith(".localhost")
    try:
        address = ipaddress.ip_address(hostname)
        blocked = blocked or address.is_loopback or address.is_unspecified
    except ValueError:
        pass
    if blocked:
        raise DeliveryError("PUBLIC_BASE_URL aponta para localhost. Configure o IP do computador na rede para o destinatário abrir a fatura.")


def _normalized(text):
    return " ".join(str(text).split())


class WhatsAppSender:
    def __init__(self, settings, *, stop_event=None, log=print, wait_for_login=None):
        self.settings = settings
        self.stop = stop_event or Event()
        self.log = log
        self.wait_for_login = wait_for_login
        self.driver = None

    def close(self):
        if self.driver is not None:
            try:
                self.driver.quit()
            finally:
                self.driver = None

    def _connected(self):
        from selenium.webdriver.common.by import By
        return bool(self.driver.find_elements(By.CSS_SELECTOR, "#pane-side, [data-testid='chat-list'], [aria-label='Chat list']"))

    def _login(self):
        while not self.stop.is_set():
            deadline = time.monotonic() + 30
            self.log("WhatsApp: aguardando login por até 30 segundos; leia o QR Code se necessário.")
            while time.monotonic() < deadline and not self.stop.is_set():
                if self._connected():
                    return
                self.stop.wait(0.5)
            if self.stop.is_set():
                break
            prompt = "Login WhatsApp não concluído em 30 segundos. Continuar aguardando mais 30 segundos?"
            if self.wait_for_login is None or not self.wait_for_login(prompt):
                raise DeliveryError("Login no WhatsApp não concluído; nenhuma mensagem enviada.")
        raise DeliveryError("Interrupção solicitada antes do envio WhatsApp.")

    def _ensure_browser(self):
        if getattr(self.settings, "browser_headless", False):
            raise DeliveryError("O envio WhatsApp por imagem exige navegador visível (BROWSER_HEADLESS=false).")
        reference = Path(self.settings.whatsapp_send_image)
        if not reference.is_file():
            raise DeliveryError(f"Imagem de referência ausente: {reference}. Capture o botão Enviar conforme o README.")
        if self.driver is None:
            self.driver = create_driver(self.settings, persistent=True)
            self.driver.get("https://web.whatsapp.com/")
        if not self._connected():
            self._login()

    def _interface_error(self):
        from selenium.webdriver.common.by import By
        texts = " ".join(element.text for element in self.driver.find_elements(
            By.CSS_SELECTOR, "[role='dialog'], [role='alert'], [data-testid='alert-phone']"
        )).casefold()
        if any(term in texts for term in ("phone number shared via url is invalid", "número de telefone compartilhado", "não está no whatsapp", "isn't on whatsapp", "is not on whatsapp", "número de telefone inválido")):
            raise DeliveryError("Número inválido ou sem WhatsApp, conforme indicação da interface.")
        if any(term in texts for term in ("computer not connected", "computador não conectado", "sem conexão", "check your internet", "verifique sua conexão")):
            raise DeliveryError("WhatsApp Web indicou perda de conexão.")

    def _message_key(self, outgoing):
        # data-id pertence à mensagem, enquanto o identificador do WebElement muda
        # quando o WhatsApp redesenha o histórico. Ausência de data-id é inconclusiva.
        return self.driver.execute_script("""
            const node = arguments[0].closest('[data-id]') || arguments[0].querySelector('[data-id]');
            return node ? node.getAttribute('data-id') : null;
        """, outgoing)

    def _click_image(self, composer):
        """Localiza a imagem somente na área do rodapé; nenhum clique Selenium."""
        import pyautogui

        if not self.driver.execute_script("return document.hasFocus()"):
            raise DeliveryError("O WhatsApp não está em primeiro plano. Ative o navegador antes de reprocessar a falha.")
        position = self.driver.execute_script("""
            const box = arguments[0].getBoundingClientRect();
            const border = Math.max(0, (window.outerWidth-window.innerWidth)/2);
            return {left: window.screenX+border+box.left,
                    top: window.screenY+window.outerHeight-window.innerHeight-border+box.top,
                    width: box.width, height: box.height,
                    screenWidth: window.screen.width};
        """, composer)
        screen_width, screen_height = pyautogui.size()
        scale = screen_width / position["screenWidth"]
        left = max(0, round(position["left"] * scale))
        top = max(0, round(position["top"] * scale))
        width = min(screen_width - left, round(position["width"] * scale))
        height = min(screen_height - top, round(position["height"] * scale))
        if width <= 0 or height <= 0:
            raise DeliveryError("Área do botão fora da tela. Maximize o navegador no monitor principal.")
        try:
            matches = list(pyautogui.locateAllOnScreen(
                str(self.settings.whatsapp_send_image),
                confidence=float(self.settings.whatsapp_confidence),
                region=(left, top, width, height),
            ))
        except pyautogui.ImageNotFoundException as exc:
            raise DeliveryError("Botão Enviar não localizado pela imagem. Confira tema, escala e referência.") from exc
        if len(matches) != 1:
            raise DeliveryError(f"Reconhecimento encontrou {len(matches)} candidatos no rodapé; envio suspenso.")
        if self.stop.is_set():
            raise DeliveryError("Interrupção solicitada antes do clique.")
        if not self.driver.execute_script("return document.hasFocus()"):
            raise DeliveryError("O navegador perdeu o foco antes do clique; nenhuma mensagem enviada.")
        target = pyautogui.center(matches[0])
        # Uma falha durante o clique pode ocorrer depois de o sistema receber o evento.
        try:
            pyautogui.click(target.x, target.y)
        except Exception as exc:
            raise DeliveryError("Falha durante o clique; confira a conversa manualmente.", uncertain=True) from exc

    def send(self, item):
        from selenium.webdriver.common.by import By

        phone = normalize_phone(item["recipient"])
        validate_accessible_link(item["link"])
        self._ensure_browser()
        original_tab = self.driver.current_window_handle
        self.driver.switch_to.new_window("tab")
        clicked = False
        try:
            query = urlencode({"phone": phone, "text": item["message"]})
            self.driver.get(f"https://web.whatsapp.com/send?{query}")
            # A URL de envio não é, sozinha, uma prova de entrega, mas é uma
            # barreira contra o operador trocar a conversa enquanto a página
            # carrega. Se a interface ocultar/redirecionar o telefone, paramos.
            current_phone = parse_qs(urlparse(self.driver.current_url).query).get("phone", [""])[0]
            if current_phone and normalize_phone(current_phone) != phone:
                raise DeliveryError("A conversa aberta não corresponde ao telefone revisado; envio suspenso.")
            if not current_phone and "send" not in self.driver.current_url:
                raise DeliveryError("Não foi possível comprovar a conversa do telefone revisado; envio suspenso.")
            deadline = time.monotonic() + max(10, int(self.settings.wait_timeout))
            footer = None
            while time.monotonic() < deadline:
                if self.stop.is_set():
                    raise DeliveryError("Interrupção solicitada antes do envio.")
                self._interface_error()
                editors = self.driver.find_elements(By.CSS_SELECTOR, "footer [contenteditable='true'][role='textbox']")
                if editors and _normalized(editors[0].get_attribute("textContent")) == _normalized(item["message"]):
                    footer = self.driver.find_element(By.CSS_SELECTOR, "footer")
                    break
                self.stop.wait(0.5)
            if footer is None:
                raise DeliveryError("Tempo limite: a conversa e o texto não foram confirmados. Verifique login, telefone e conexão.")
            before = {self._message_key(element) for element in self.driver.find_elements(By.CSS_SELECTOR, ".message-out")}
            self._click_image(footer)
            clicked = True
            # Depois do clique, conclui a verificação antes de obedecer à interrupção.
            deadline = time.monotonic() + max(10, int(self.settings.wait_timeout))
            while time.monotonic() < deadline:
                self._interface_error()
                for outgoing in self.driver.find_elements(By.CSS_SELECTOR, ".message-out"):
                    key = self._message_key(outgoing)
                    if not key or key in before or _normalized(item["message"]) not in _normalized(outgoing.text):
                        continue
                    indicators = outgoing.find_elements(By.CSS_SELECTOR,
                        "[data-icon='msg-check'], [data-icon='msg-dblcheck'], [data-icon='msg-dblcheck-ack']")
                    if indicators:
                        return {"status": "Enviado", "evidence": "Nova mensagem de saída com texto integral e marca de envio na interface; leitura não confirmada."}
                time.sleep(0.5)
            raise DeliveryError("Clique realizado, mas nenhuma nova mensagem com marca de envio foi confirmada. Confira manualmente; não haverá reenvio automático.", uncertain=True)
        except DeliveryError as exc:
            if clicked:
                exc.uncertain = True
            raise
        except Exception as exc:
            raise DeliveryError(f"Falha no WhatsApp ({type(exc).__name__}): {str(exc).split('Stacktrace:')[0].strip()}", uncertain=clicked) from exc
        finally:
            try:
                self.driver.close()
                self.driver.switch_to.window(original_tab)
            except Exception:
                pass
