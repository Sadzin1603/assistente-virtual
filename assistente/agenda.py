"""Timers e lembretes. Ficam salvos em disco para sobreviver a um reinício."""
import json
import threading
import time
from pathlib import Path
from typing import Callable


def falar_duracao(segundos: float) -> str:
    s = int(round(segundos))
    h, resto = divmod(s, 3600)
    m, s = divmod(resto, 60)
    partes = []
    if h:
        partes.append(f"{h} hora" + ("s" if h > 1 else ""))
    if m:
        partes.append(f"{m} minuto" + ("s" if m > 1 else ""))
    if s and not h:
        partes.append(f"{s} segundo" + ("s" if s > 1 else ""))
    return " e ".join(partes) or "0 segundos"


class Agenda:
    def __init__(self, arquivo: Path, ao_disparar: Callable[[str], None]):
        self.arquivo = arquivo
        self.ao_disparar = ao_disparar
        self.trava = threading.Lock()
        self.itens: list[dict] = []
        self._carregar()
        threading.Thread(target=self._vigiar, daemon=True).start()

    def _carregar(self) -> None:
        try:
            self.itens = json.loads(self.arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.itens = []

    def _salvar(self) -> None:
        self.arquivo.write_text(json.dumps(self.itens, ensure_ascii=False, indent=1), encoding="utf-8")

    def timer(self, segundos: float) -> None:
        aviso = f"Seu timer de {falar_duracao(segundos)} terminou."
        self._adicionar("timer", time.time() + segundos, aviso)

    def lembrete(self, quando: float, texto: str) -> None:
        self._adicionar("lembrete", quando, f"Lembrete: {texto}.")

    def _adicionar(self, tipo: str, quando: float, aviso: str) -> None:
        with self.trava:
            self.itens.append({"tipo": tipo, "quando": quando, "aviso": aviso})
            self._salvar()

    def cancelar(self, tipo: str | None = None) -> int:
        with self.trava:
            antes = len(self.itens)
            self.itens = [i for i in self.itens if tipo and i["tipo"] != tipo]
            self._salvar()
            return antes - len(self.itens)

    def pendentes(self, tipo: str | None = None) -> list[dict]:
        with self.trava:
            return sorted((i for i in self.itens if not tipo or i["tipo"] == tipo), key=lambda i: i["quando"])

    def _vigiar(self) -> None:
        while True:
            time.sleep(0.5)
            agora = time.time()
            with self.trava:
                vencidos = [i for i in self.itens if i["quando"] <= agora]
                if vencidos:
                    self.itens = [i for i in self.itens if i["quando"] > agora]
                    self._salvar()
            for item in vencidos:
                self.ao_disparar(item["aviso"])
