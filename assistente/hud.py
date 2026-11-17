"""HUD: uma pílula sempre por cima de tudo que mostra o que o assistente está fazendo.

Não rouba o foco e deixa os cliques passarem para a janela de baixo.
"""
import ctypes
import math
import queue
import time
import tkinter as tk
from tkinter import font as tkfont

CHAVE = "#010203"   # cor tratada como transparente
FUNDO = "#0b1220"
TEXTO = "#e5e7eb"
CORES = {"ocioso": "#3b82f6", "ouvindo": "#22d3ee", "pensando": "#f59e0b", "falando": "#34d399", "aviso": "#f472b6"}
TITULOS = {"ocioso": "Jarvis", "ouvindo": "Ouvindo", "pensando": "Pensando", "falando": "Jarvis", "aviso": "Aviso"}


class SemHud:
    """Substituto usado quando o HUD está desligado ou não pôde abrir."""

    def estado(self, nome: str, texto: str = "") -> None:
        pass

    def fechar(self) -> None:
        pass


class Hud:
    def __init__(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
        self.fila: queue.Queue = queue.Queue()
        self.nome, self.texto, self.inicio = "ocioso", "", time.time()
        r = self.raiz = tk.Tk()
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.attributes("-transparentcolor", CHAVE)
        r.configure(bg=CHAVE)
        self.k = k = r.winfo_fpixels("1i") / 96
        self.largura, self.altura = int(480 * k), int(64 * k)
        self.tela = tk.Canvas(r, width=self.largura, height=self.altura, bg=CHAVE, highlightthickness=0)
        self.tela.pack()
        self.f_titulo = tkfont.Font(family="Segoe UI", size=-int(15 * k), weight="bold")
        self.f_texto = tkfont.Font(family="Segoe UI", size=-int(14 * k))
        x = (r.winfo_screenwidth() - self.largura) // 2
        y = r.winfo_screenheight() - self.altura - int(72 * k)
        r.geometry(f"{self.largura}x{self.altura}+{x}+{y}")
        r.update_idletasks()
        self._atravessar_cliques()
        self._alpha = None
        self._quadro = 0
        r.after(33, self._tique)

    def _atravessar_cliques(self) -> None:
        u = ctypes.windll.user32
        hwnd = u.GetParent(self.raiz.winfo_id()) or self.raiz.winfo_id()
        estilo = u.GetWindowLongW(hwnd, -20)
        # LAYERED | TRANSPARENT (cliques passam) | NOACTIVATE (nunca pega o foco)
        u.SetWindowLongW(hwnd, -20, estilo | 0x80000 | 0x20 | 0x08000000)

    # --------------------------------------------------- chamadas de outras threads
    def estado(self, nome: str, texto: str = "") -> None:
        self.fila.put((nome, texto))

    def fechar(self) -> None:
        self.fila.put(None)

    def rodar(self) -> None:
        self.raiz.mainloop()

    # ------------------------------------------------------------------ desenho
    def _encurtar(self, texto: str, largura: int) -> str:
        if self.f_texto.measure(texto) <= largura:
            return texto
        while texto and self.f_texto.measure(texto + "…") > largura:
            texto = texto[:-1]
        return texto.rstrip() + "…"

    def _tique(self) -> None:
        try:
            while True:
                item = self.fila.get_nowait()
                if item is None:
                    self.raiz.destroy()
                    return
                if item[0] != self.nome:
                    self.inicio = time.time()
                self.nome, self.texto = item
        except queue.Empty:
            pass
        self._quadro += 1
        if self._quadro % 60 == 0:  # outras janelas "sempre no topo" podem ter passado por cima
            self.raiz.attributes("-topmost", True)
            self.raiz.lift()
        self._desenhar()
        self.raiz.after(33, self._tique)

    def _desenhar(self) -> None:
        c, k, a = self.tela, self.k, self.altura
        t = time.time() - self.inicio
        cor = CORES.get(self.nome, CORES["ocioso"])
        ocioso = self.nome == "ocioso"
        alpha = 0.55 if ocioso else 0.94
        if alpha != self._alpha:
            self.raiz.attributes("-alpha", alpha)
            self._alpha = alpha

        titulo = TITULOS.get(self.nome, "Jarvis")
        if ocioso:
            largura = a + self.f_titulo.measure(titulo) + int(26 * k)
        else:
            largura = self.largura
        x0 = (self.largura - largura) // 2
        c.delete("all")
        # pílula: dois círculos nas pontas e um retângulo no meio
        c.create_oval(x0, 0, x0 + a, a, fill=FUNDO, outline="")
        c.create_oval(x0 + largura - a, 0, x0 + largura, a, fill=FUNDO, outline="")
        c.create_rectangle(x0 + a // 2, 0, x0 + largura - a // 2, a, fill=FUNDO, outline="")

        cx, cy, r = x0 + a // 2, a // 2, 9 * k
        if self.nome == "ouvindo":      # anel pulsando
            p = (math.sin(t * 5) + 1) / 2
            c.create_oval(cx - r - 6 * k * p, cy - r - 6 * k * p, cx + r + 6 * k * p, cy + r + 6 * k * p, outline=cor, width=2)
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=cor, outline="")
        elif self.nome == "pensando":   # três pontos girando
            for i in range(3):
                ang = t * 4 + i * 2.094
                px, py = cx + math.cos(ang) * 11 * k, cy + math.sin(ang) * 11 * k
                c.create_oval(px - 3.5 * k, py - 3.5 * k, px + 3.5 * k, py + 3.5 * k, fill=cor, outline="")
        elif self.nome in ("falando", "aviso"):  # barras de equalizador
            for i in range(5):
                h = (5 + 11 * abs(math.sin(t * 7 + i * 1.3))) * k
                bx = cx + (i - 2) * 6 * k
                c.create_rectangle(bx - 2 * k, cy - h, bx + 2 * k, cy + h, fill=cor, outline="")
        else:
            c.create_oval(cx - r * 0.7, cy - r * 0.7, cx + r * 0.7, cy + r * 0.7, fill=cor, outline="")

        tx = x0 + a
        if ocioso or not self.texto:
            c.create_text(tx, cy, text=titulo, anchor="w", fill=cor if not ocioso else TEXTO, font=self.f_titulo)
        else:
            c.create_text(tx, cy - 11 * k, text=titulo, anchor="w", fill=cor, font=self.f_titulo)
            espaco = largura - a - int(28 * k)
            c.create_text(tx, cy + 10 * k, text=self._encurtar(self.texto, espaco), anchor="w", fill=TEXTO, font=self.f_texto)
