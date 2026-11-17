"""Diagnóstico: confere cada peça de voz sem precisar falar nada.

    python autoteste.py
"""
import sys
import time

import numpy as np

import config

sys.stdout.reconfigure(encoding="utf-8")


def etapa(nome):
    print(f"\n== {nome}")
    return time.time()


def reamostrar(audio_int16: np.ndarray, de: int, para: int) -> np.ndarray:
    x = audio_int16.astype(np.float32) / 32768.0
    n = int(len(x) * para / de)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def main() -> int:
    falhas = 0

    t = etapa("Fala (Piper)")
    from assistente.voz import Despertador, Ouvido, Voz
    voz = Voz()
    if voz.piper is None:
        print("FALHA: Piper não carregou (cairia na voz do Windows).")
        return 1
    frases = ["Que horas são?", "Coloca um timer de cinco minutos.", "Aumenta o volume."]
    audios = [voz.sintetizar(f) for f in frases]
    print(f"ok, {len(audios)} frases sintetizadas em {time.time() - t:.1f}s (inclui carregar a voz)")

    t = etapa(f"Transcrição (Whisper {config.WHISPER_MODELO})")
    ouvido = Ouvido()
    print(f"modelo carregado em {time.time() - t:.1f}s")
    for frase, (audio, taxa) in zip(frases, audios):
        t = time.time()
        texto = ouvido.transcrever(reamostrar(audio, taxa, config.TAXA))
        print(f"  dito: {frase!r} -> ouvido: {texto!r}  ({time.time() - t:.1f}s para {len(audio) / taxa:.1f}s de áudio)")
        if not texto:
            falhas += 1

    t = etapa(f"Palavra de ativação ({config.WAKE_MODELO})")
    despertador = Despertador()
    silencio = np.zeros(config.BLOCO, dtype=np.int16)
    disparou = any(despertador.detectou(silencio) for _ in range(25))
    print(f"modelo carregado em {time.time() - t:.1f}s; disparo falso no silêncio: {disparou}")
    falhas += disparou

    etapa("Microfone")
    try:
        from assistente.audio import Microfone, rms
        mic = Microfone()
        niveis = [rms(b) for b in (mic.ler(1.0) for _ in range(15)) if b is not None]
        mic.stream.stop()
        import sounddevice as sd
        print(f"dispositivo: {sd.query_devices(kind='input')['name']}")
        print(f"{len(niveis)} blocos lidos, nível médio {np.mean(niveis):.0f}" if niveis else "FALHA: nenhum áudio chegou")
        falhas += not niveis
    except Exception as erro:
        print(f"FALHA: {erro}")
        falhas += 1

    etapa("Volume do sistema")
    try:
        from assistente import pc
        v = pc.volume_atual()
        print(f"volume atual: {v}%")
    except Exception as erro:
        print(f"FALHA: {erro}")
        falhas += 1

    etapa(f'Nome "{config.WAKE_PALAVRA}" por transcrição')
    from assistente.voz import separar_wake
    audio, taxa = voz.sintetizar(f"{config.WAKE_PALAVRA.capitalize()}, que horas são?")
    texto = ouvido.transcrever(reamostrar(audio, taxa, config.TAXA))
    achou, pedido = separar_wake(texto)
    print(f"ouvido: {texto!r} -> ativou: {achou}, pedido: {pedido!r}")
    falhas += not achou

    etapa("HUD (indicador na tela)")
    try:
        import tkinter
        print(f"disponível (Tk {tkinter.TkVersion})" + ("" if config.HUD else ", mas desligado no .env"))
    except Exception as erro:
        print(f"indisponível: {erro}. O assistente funciona sem ele.")

    etapa(f"IA ({config.IA_PROVEDOR}: {config.IA_MODELO or 'desligada'})")
    if not config.IA_URL:
        print("desligada: só comandos locais funcionam")
    else:
        from assistente.cerebro import Cerebro
        t = time.time()
        resposta = Cerebro(None).perguntar("Responda só com a palavra: funcionando")
        print(f"resposta em {time.time() - t:.1f}s: {resposta}")
        print("(a IA é opcional; os comandos locais funcionam sem ela)")

    print("\nTudo certo." if not falhas else f"\n{falhas} problema(s) acima.")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
