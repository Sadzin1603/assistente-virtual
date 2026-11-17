"""Entrada e saída de voz, tudo local: palavra de ativação, transcrição e fala."""
import difflib
import re
import unicodedata

import numpy as np
import sounddevice as sd

import config

# Frases que o Whisper inventa quando só há ruído.
_ALUCINACOES = ("legendas pela comunidade", "amara.org", "inscreva-se", "obrigado por assistir", "legendado por")


class Despertador:
    """Palavra de ativação com openWakeWord (roda em ONNX, leve na CPU)."""

    def __init__(self):
        import openwakeword
        from openwakeword.model import Model

        openwakeword.utils.download_models([config.WAKE_MODELO])
        self.modelo = Model(wakeword_models=[config.WAKE_MODELO], inference_framework="onnx")

    def detectou(self, bloco: np.ndarray) -> bool:
        notas = self.modelo.predict(bloco)
        return max(notas.values()) >= config.WAKE_LIMIAR

    def reset(self) -> None:
        self.modelo.reset()


class Ouvido:
    """Transcrição com faster-whisper em CPU."""

    def __init__(self):
        from faster_whisper import WhisperModel

        self.modelo = WhisperModel(config.WHISPER_CAMINHO, device="cpu", compute_type="int8")

    def transcrever(self, audio: np.ndarray) -> str:
        # hotwords faz o Whisper escrever o nome do assistente certo em vez de "Javis", "Jervis"...
        trechos, _ = self.modelo.transcribe(
            audio, language="pt", beam_size=1, vad_filter=True, condition_on_previous_text=False,
            hotwords=config.WAKE_PALAVRA.capitalize(),
        )
        texto = " ".join(t.text.strip() for t in trechos).strip()
        if any(a in texto.lower() for a in _ALUCINACOES):
            return ""
        return texto


def separar_wake(texto: str) -> tuple[bool, str]:
    """Procura a palavra de ativação no começo ou no fim da frase.

    Devolve (achou, pedido). "Jarvis, que horas são?" -> (True, "que horas são");
    "Jarvis" -> (True, ""); "que horas são" -> (False, "que horas são").
    """
    palavras = re.sub(r"[^\w: ]", " ", texto).split()
    alvo = config.WAKE_PALAVRA

    def parece(p: str) -> bool:
        p = "".join(unicodedata.normalize("NFD", c)[0] for c in p.lower())
        return difflib.SequenceMatcher(None, p, alvo).ratio() >= 0.8

    for i, p in enumerate(palavras[:3]):  # "Jarvis ...", "ei Jarvis ...", "ok, Jarvis ..."
        if parece(p):
            return True, " ".join(palavras[i + 1:])
    if palavras and parece(palavras[-1]):  # "... , Jarvis"
        return True, " ".join(palavras[:-1])
    return False, texto.strip()


def _para_fala(texto: str) -> str:
    texto = re.sub(r"https?://\S+", "", texto)
    texto = re.sub(r"[*_#`>|]", "", texto)
    return " ".join(texto.split())


class Voz:
    """Fala com Piper; se a voz não carregar, usa a voz do Windows (SAPI)."""

    def __init__(self):
        self.piper = None
        try:
            from piper import PiperVoice
            from piper.download_voices import download_voice

            config.PASTA_VOZES.mkdir(exist_ok=True)
            modelo = config.PASTA_VOZES / f"{config.PIPER_VOZ}.onnx"
            if not modelo.exists():
                print(f"Baixando a voz {config.PIPER_VOZ}...")
                download_voice(config.PIPER_VOZ, config.PASTA_VOZES)
            self.piper = PiperVoice.load(str(modelo))
        except Exception as erro:  # sem rede, voz inexistente etc.
            print(f"Piper indisponível ({erro}); usando a voz do Windows.")

    def falar(self, texto: str) -> None:
        texto = _para_fala(texto)
        if not texto:
            return
        if self.piper is None:
            import comtypes.client

            comtypes.client.CreateObject("SAPI.SpVoice").Speak(texto)
            return
        pedacos, taxa = [], 22050
        for pedaco in self.piper.synthesize(texto):
            taxa = pedaco.sample_rate
            pedacos.append(np.frombuffer(pedaco.audio_int16_bytes, dtype=np.int16))
        if pedacos:
            sd.play(np.concatenate(pedacos), taxa)
            sd.wait()

    def sintetizar(self, texto: str) -> tuple[np.ndarray, int]:
        """Áudio int16 sem tocar (usado no autoteste)."""
        pedacos = list(self.piper.synthesize(_para_fala(texto)))
        return np.concatenate([np.frombuffer(p.audio_int16_bytes, dtype=np.int16) for p in pedacos]), pedacos[0].sample_rate
