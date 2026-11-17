"""Jarvis: assistente de voz local para Windows.

    python main.py            modo voz (diga "Jarvis" e faça o pedido)
    python main.py --texto    modo texto, para testar sem microfone
    python main.py --sem-hud  modo voz sem o indicador na tela
"""
import argparse
import queue
import sys
import threading
import time

import config
from assistente.agenda import Agenda
from assistente.cerebro import Cerebro
from assistente.comandos import interpretar


def modo_texto(responder, avisos: queue.Queue, falar_alto: bool) -> None:
    voz = None
    if falar_alto:
        from assistente.voz import Voz
        voz = Voz()
    print("Modo texto. Digite o pedido (Ctrl+C para sair).")
    while True:
        while not avisos.empty():
            aviso = avisos.get()
            print(f"[aviso] {aviso}")
            if voz:
                voz.falar(aviso)
        try:
            frase = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not frase:
            continue
        texto, sair = responder(frase)
        print(texto or "(feito)")
        if voz:
            voz.falar(texto)
        if sair:
            break


def modo_voz(responder, avisos: queue.Queue, hud) -> None:
    from assistente.audio import ACORDOU, AVISO, DORMIU, Microfone, Segmentador, bip, gravar_comando
    from assistente.voz import Despertador, Ouvido, Voz, separar_wake

    hud.estado("pensando", "Carregando modelos de voz…")
    print("Carregando modelos de voz...")
    voz, ouvido, despertador = Voz(), Ouvido(), Despertador()
    mic = Microfone()
    seg = Segmentador()
    nome = config.WAKE_PALAVRA.capitalize()

    def falar(texto: str) -> None:
        mic.mudo = True  # não ouvir a própria voz
        try:
            voz.falar(texto)
            time.sleep(0.15)
        finally:
            mic.limpar()
            mic.mudo = False

    def sinal(notas) -> None:
        mic.mudo = True
        bip(*notas)
        mic.mudo = False

    def atender(pedido: str | None) -> bool:
        """Conduz uma conversa. pedido já vem pronto quando foi dito junto com o nome. True = encerrar."""
        espera = 4.0
        while True:
            if pedido is None:
                hud.estado("ouvindo")
                audio = gravar_comando(mic, seg.ruido, espera_inicio=espera)
                if audio is None:
                    break
                hud.estado("pensando")
                frase = ouvido.transcrever(audio)
                achou, resto = separar_wake(frase)  # "Jarvis, ..." repetido no pedido
                if achou and resto:
                    frase = resto
            else:
                frase, pedido = pedido, None
            if not frase:
                break
            print(f"Você: {frase}")
            hud.estado("pensando", frase)
            texto, sair = responder(frase)
            print(f"{nome}: {texto or '(feito)'}")
            if texto:
                hud.estado("falando", texto)
                falar(texto)
            if sair:
                return True
            if not texto.rstrip().endswith("?"):
                break
            sinal(ACORDOU)  # o assistente perguntou algo: ouve a resposta sem precisar do nome
            espera = 6.0
        sinal(DORMIU)
        hud.estado("ocioso")
        despertador.reset()
        mic.limpar()
        seg.reset()
        return False

    hud.estado("falando", "Pronto.")
    falar("Pronto.")
    hud.estado("ocioso")
    print(f'Ouvindo. Diga "{nome}" e faça o pedido. Ctrl+C encerra.')
    while True:
        while not avisos.empty():
            aviso = avisos.get()
            print(f"[aviso] {aviso}")
            hud.estado("aviso", aviso)
            sinal(AVISO)
            falar(aviso)
            hud.estado("ocioso")
            despertador.reset()
        bloco = mic.ler()
        if bloco is None:
            continue

        # Detector rápido: bipa assim que ouve o nome.
        if despertador.detectou(bloco):
            seg.reset()
            sinal(ACORDOU)
            if atender(None):
                return
            continue

        # Detector por transcrição: espera a frase acabar e procura o nome nela.
        trecho = seg.alimentar(bloco)
        if trecho is None or not config.WAKE_TRANSCRICAO:
            continue
        achou, pedido = separar_wake(ouvido.transcrever(trecho))
        if not achou:
            continue
        despertador.reset()
        sinal(ACORDOU)
        if atender(pedido or None):
            return


def main() -> None:
    parser = argparse.ArgumentParser(description="Jarvis, assistente de voz local")
    parser.add_argument("--texto", action="store_true", help="digitar em vez de falar")
    parser.add_argument("--mudo", action="store_true", help="no modo texto, não falar as respostas")
    parser.add_argument("--sem-hud", action="store_true", help="não mostrar o indicador na tela")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    avisos: queue.Queue[str] = queue.Queue()
    agenda = Agenda(config.ARQUIVO_AGENDA, avisos.put)
    cerebro = Cerebro(agenda)

    def responder(frase: str):
        local = interpretar(frase, agenda)
        if local is not None:
            return local.texto, local.sair
        print("   (consultando a IA...)")
        return cerebro.perguntar(frase), False

    if args.texto:
        modo_texto(responder, avisos, falar_alto=not args.mudo)
        return

    cerebro.aquecer()
    from assistente.hud import SemHud
    hud = SemHud()
    if config.HUD and not args.sem_hud:
        try:
            from assistente.hud import Hud
            hud = Hud()
        except Exception as erro:  # sem tkinter ou sem área de trabalho
            print(f"HUD indisponível ({erro}); seguindo sem ele.")

    if isinstance(hud, SemHud):
        try:
            modo_voz(responder, avisos, hud)
        except KeyboardInterrupt:
            print("\nEncerrado.")
        return

    # O Tk precisa da thread principal; o assistente roda em outra.
    falha: list[BaseException] = []

    def trabalhar():
        try:
            modo_voz(responder, avisos, hud)
        except BaseException as erro:
            falha.append(erro)
        finally:
            hud.fechar()

    threading.Thread(target=trabalhar, daemon=True).start()
    try:
        hud.rodar()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    if falha:
        raise falha[0]


if __name__ == "__main__":
    main()
