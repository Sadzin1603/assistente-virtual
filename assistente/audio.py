"""Microfone, gravação do comando até o silêncio e bipes."""
import queue
import statistics
import time
from collections import deque

import numpy as np
import sounddevice as sd

from config import BLOCO, TAXA


def rms(bloco: np.ndarray) -> float:
    return float(np.sqrt(np.mean(bloco.astype(np.float32) ** 2)))


class Microfone:
    """Entrega blocos de 80 ms em int16. Com mudo=True os blocos são descartados."""

    def __init__(self):
        self.fila: queue.Queue[np.ndarray] = queue.Queue()
        self.mudo = False
        self.stream = sd.InputStream(
            samplerate=TAXA, channels=1, dtype="int16", blocksize=BLOCO, callback=self._chegou
        )
        self.stream.start()

    def _chegou(self, dados, _frames, _tempo, _status):
        if not self.mudo:
            self.fila.put(dados[:, 0].copy())

    def ler(self, timeout: float = 0.5) -> np.ndarray | None:
        try:
            return self.fila.get(timeout=timeout)
        except queue.Empty:
            return None

    def limpar(self) -> None:
        while not self.fila.empty():
            self.fila.get_nowait()


class Segmentador:
    """Recorta trechos de fala do áudio contínuo e acompanha o ruído ambiente."""

    SILENCIO_FIM = 0.7  # s de silêncio que encerram o trecho
    MAXIMO = 10.0       # trechos maiores são som contínuo (música, TV) e são descartados

    def __init__(self):
        self.ruidos: deque[float] = deque(maxlen=60)
        self.reset()

    def reset(self) -> None:
        self.pre: deque[np.ndarray] = deque(maxlen=4)
        self.blocos: list[np.ndarray] = []
        self.quieto = 0.0
        self.falando = False

    @property
    def ruido(self) -> float:
        return statistics.median(self.ruidos) if self.ruidos else 100.0

    @property
    def limiar(self) -> float:
        return max(self.ruido * 2.5, 250.0)

    def alimentar(self, bloco: np.ndarray) -> np.ndarray | None:
        """Recebe um bloco; devolve o trecho de fala (float32) quando ele termina."""
        nivel, seg = rms(bloco), BLOCO / TAXA
        if not self.falando:
            if nivel > self.limiar:
                self.falando, self.quieto = True, 0.0
                self.blocos = list(self.pre) + [bloco]
            else:
                self.ruidos.append(nivel)
                self.pre.append(bloco)
            return None
        self.blocos.append(bloco)
        self.quieto = 0.0 if nivel > self.limiar else self.quieto + seg
        duracao = len(self.blocos) * seg
        if self.quieto >= self.SILENCIO_FIM:
            trecho = np.concatenate(self.blocos).astype(np.float32) / 32768.0
            self.reset()
            return trecho if duracao - self.SILENCIO_FIM >= 0.3 else None
        if duracao > self.MAXIMO:
            # Som contínuo: passa a contar como ruído de fundo para não travar aqui.
            self.ruidos.extend(rms(b) for b in self.blocos[-20:])
            self.reset()
        return None


def gravar_comando(
    mic: Microfone,
    ruido: float,
    espera_inicio: float = 4.0,
    silencio_fim: float = 0.9,
    maximo: float = 12.0,
) -> np.ndarray | None:
    """Grava a fala e para quando houver silêncio. None se ninguém falou."""
    limiar = max(ruido * 2.5, 250.0)
    seg = BLOCO / TAXA
    blocos, falou, quieto, total = [], False, 0.0, 0.0
    while total < maximo:
        bloco = mic.ler(timeout=1.0)
        if bloco is None:
            break
        total += seg
        blocos.append(bloco)
        if rms(bloco) > limiar:
            falou, quieto = True, 0.0
        else:
            quieto += seg
            if falou and quieto >= silencio_fim:
                break
            if not falou and total >= espera_inicio:
                return None
    if not falou:
        return None
    return np.concatenate(blocos).astype(np.float32) / 32768.0


def bip(*frequencias: float, duracao: float = 0.09, volume: float = 0.25) -> None:
    """Toca uma ou mais notas em sequência."""
    taxa = 22050
    t = np.arange(int(taxa * duracao)) / taxa
    rampa = np.minimum(1.0, np.minimum(t, duracao - t) / 0.01)
    notas = [np.sin(2 * np.pi * f * t) * volume * rampa for f in (frequencias or (880.0,))]
    sd.play(np.concatenate(notas).astype(np.float32), taxa)
    sd.wait()
    time.sleep(0.02)


ACORDOU = (988.0, 1319.0)   # duas notas subindo: ouvi "Jarvis"
DORMIU = (523.0,)           # nota grave: voltei a esperar
AVISO = (1319.0, 1319.0)    # timer ou lembrete
