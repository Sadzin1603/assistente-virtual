"""Atualização automática: baixa do GitHub a versão mais nova do código.

Só troca o código do aplicativo. O Python embutido, os modelos, o .env e os lembretes ficam
como estão. Usa apenas a biblioteca padrão, para funcionar mesmo se algo do pacote quebrar.
"""
import io
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

REPO = "Sadzin1603/assistente-virtual"
RAMO = "main"
RAIZ = Path(__file__).resolve().parent
ARQUIVOS_RAIZ = {
    "main.py", "config.py", "autoteste.py", "lancador.py", "atualizar.py", "instalar_ia.py",
    "requirements.txt", ".env.example", "README.md",
}


def destino(rel: str) -> str | None:
    """Onde um arquivo do repositório fica na pasta instalada (None = não é instalado)."""
    partes = PurePosixPath(rel).parts
    if not partes or ".." in partes or PurePosixPath(rel).is_absolute():
        return None
    if len(partes) == 1 and rel in ARQUIVOS_RAIZ:
        return rel
    if len(partes) == 2 and partes[0] == "assistente" and rel.endswith(".py"):
        return rel
    if len(partes) == 2 and partes[0] == "empacote":
        return partes[1]
    return None


def _ler_env(raiz: Path, chave: str, padrao: str) -> str:
    try:
        for linha in (raiz / ".env").read_text(encoding="utf-8").splitlines():
            nome, _, valor = linha.partition("=")
            if nome.strip() == chave:
                return valor.strip()
    except OSError:
        pass
    return padrao


def _baixar(url: str, timeout: float, aceitar: str = "*/*") -> bytes:
    pedido = urllib.request.Request(url, headers={"User-Agent": "assistente-virtual-atualizador", "Accept": aceitar})
    with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
        return resposta.read()


def verificar_e_atualizar(raiz: Path = RAIZ, log=print) -> bool:
    """Devolve True se instalou uma versão nova. Qualquer falha de rede é ignorada."""
    if (raiz / ".git").exists():
        return False  # pasta de desenvolvimento: atualize com git pull
    if _ler_env(raiz, "AUTO_ATUALIZAR", "1") in ("0", "nao", "não", "false", "off"):
        return False
    arquivo_versao = raiz / "versao.txt"
    atual = arquivo_versao.read_text(encoding="utf-8").strip() if arquivo_versao.exists() else ""
    try:
        novo = _baixar(
            f"https://api.github.com/repos/{REPO}/commits/{RAMO}", 5, "application/vnd.github.sha"
        ).decode("ascii").strip()
    except Exception:
        return False  # sem internet ou GitHub fora do ar: segue com a versão instalada
    if not novo or novo == atual or len(novo) != 40 or not all(c in "0123456789abcdef" for c in novo):
        return False

    log(f"Atualizando para a versão {novo[:7]}...")
    try:
        pacote = zipfile.ZipFile(io.BytesIO(_baixar(f"https://codeload.github.com/{REPO}/zip/{novo}", 60)))
    except Exception as erro:
        log(f"Não consegui baixar a atualização ({erro}); usando a versão instalada.")
        return False

    requisitos_antes = (raiz / "requirements.txt").read_bytes() if (raiz / "requirements.txt").exists() else b""
    novos: dict[str, bytes] = {}
    for item in pacote.infolist():
        if item.is_dir():
            continue
        rel = destino(item.filename.split("/", 1)[1] if "/" in item.filename else "")
        if rel:
            novos[rel] = pacote.read(item)
    if "main.py" not in novos:
        log("Atualização com formato inesperado; ignorada.")
        return False

    for rel, dados in novos.items():
        alvo = raiz / rel
        # Um .bat em execução não pode ser trocado; os existentes ficam como estão.
        if alvo.suffix.lower() == ".bat" and alvo.exists():
            continue
        alvo.parent.mkdir(parents=True, exist_ok=True)
        temporario = alvo.with_name(alvo.name + ".novo")
        temporario.write_bytes(dados)
        temporario.replace(alvo)
    for antigo in (raiz / "assistente").glob("*.py"):  # módulos removidos do repositório
        if f"assistente/{antigo.name}" not in novos:
            antigo.unlink()

    if novos.get("requirements.txt", requisitos_antes) != requisitos_antes:
        pacotes = raiz / "runtime" / "pkgs"
        if pacotes.is_dir():
            log("Instalando bibliotecas novas...")
            resultado = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                 "--target", str(pacotes), "-r", str(raiz / "requirements.txt")]
            )
            if resultado.returncode != 0:
                log("Falhou ao instalar bibliotecas novas; algo pode não funcionar até baixar o pacote completo de novo.")

    arquivo_versao.write_text(novo, encoding="utf-8")
    log("Atualizado.")
    return True


if __name__ == "__main__":
    verificar_e_atualizar()
