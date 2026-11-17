"""Instala a IA local gratuita: o Ollama e o modelo configurado."""
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import config

MODELO = config.IA_MODELO if config.IA_PROVEDOR == "ollama" else config.PROVEDORES["ollama"]["modelo"]


def achar_ollama() -> str | None:
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    return shutil.which("ollama") or (str(local) if local.exists() else None)


def servidor_no_ar() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434", timeout=2).read()
        return True
    except OSError:
        return False


def main() -> int:
    ollama = achar_ollama()
    if not ollama:
        print("Instalando o Ollama (programa gratuito que roda a IA no seu PC)...")
        subprocess.run(["winget", "install", "-e", "--id", "Ollama.Ollama",
                        "--accept-source-agreements", "--accept-package-agreements"])
        ollama = achar_ollama()
    if not ollama:
        print("\nNão consegui instalar sozinho. Baixe em https://ollama.com/download, instale e rode este arquivo de novo.")
        return 1

    if not servidor_no_ar():
        subprocess.Popen([ollama, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NO_WINDOW)
        for _ in range(20):
            if servidor_no_ar():
                break
            time.sleep(1)

    print(f"\nBaixando o modelo {MODELO} (alguns GB; só na primeira vez)...")
    if subprocess.run([ollama, "pull", MODELO]).returncode != 0:
        print("O download do modelo falhou. Confira a internet e rode de novo.")
        return 1

    print("\nTestando...")
    from assistente.cerebro import Cerebro
    resposta = Cerebro(None).perguntar("Diga apenas: funcionando.")
    print("Resposta da IA:", resposta)
    print("\nPronto. A IA local já funciona no assistente." if resposta else "\nA IA não respondeu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
