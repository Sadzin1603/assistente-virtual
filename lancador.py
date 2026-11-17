"""Ponto de entrada dos .bat: confere o pacote, atualiza pelo GitHub e inicia.

    lancador.py [--diagnostico | --instalar-ia] [--sem-atualizar] [opções do main.py]
"""
import os
import runpy
import shutil
import sys
import traceback
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parent


def pacote_completo() -> bool:
    """No pacote portátil, confere se a extração do zip trouxe todos os arquivos."""
    manifesto = RAIZ / "runtime" / "manifesto.txt"
    if not manifesto.exists():
        return True
    lista = [p for p in manifesto.read_text(encoding="utf-8-sig").splitlines() if p]
    faltando = [p for p in lista if not (RAIZ / p).exists()]
    if not faltando:
        return True
    print(f"O pacote está incompleto: faltam {len(faltando)} de {len(lista)} arquivos.")
    print("Exemplo:", faltando[0])
    if max(len(str(RAIZ / p)) for p in faltando) >= 250:
        print("\nCausa: o caminho da pasta é longo demais para o Windows.")
        print("Extraia o zip de novo em uma pasta curta, por exemplo C:\\Jarvis")
    else:
        print("\nExtraia o zip de novo. Se repetir, veja se o antivírus removeu arquivos da pasta.")
    return False


def main() -> int:
    os.chdir(RAIZ)
    sys.path.insert(0, str(RAIZ))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    warnings.filterwarnings("ignore")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    if (RAIZ / "modelos").is_dir():
        os.environ.setdefault("HF_HUB_OFFLINE", "1")  # os modelos já vieram no pacote

    args = sys.argv[1:]
    if not pacote_completo():
        return 1
    if "--sem-atualizar" in args:
        args.remove("--sem-atualizar")
    else:
        try:
            import atualizar
            atualizar.verificar_e_atualizar(RAIZ)
        except Exception as erro:
            print(f"Atualização automática falhou ({erro}); seguindo com a versão instalada.")
    if not (RAIZ / ".env").exists() and (RAIZ / ".env.example").exists():
        shutil.copy(RAIZ / ".env.example", RAIZ / ".env")

    alvo = "main.py"
    if "--diagnostico" in args:
        args.remove("--diagnostico")
        alvo = "autoteste.py"
    elif "--instalar-ia" in args:
        args.remove("--instalar-ia")
        alvo = "instalar_ia.py"
    sys.argv = [alvo] + args
    try:
        runpy.run_path(str(RAIZ / alvo), run_name="__main__")
    except SystemExit as saida:
        return saida.code if isinstance(saida.code, int) else 0
    except KeyboardInterrupt:
        print("\nEncerrado.")
    except Exception:
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
