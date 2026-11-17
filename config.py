"""Configuração do assistente. Tudo pode ser sobrescrito no arquivo .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")


def _liga(nome: str, padrao: str = "1") -> bool:
    return os.getenv(nome, padrao).strip().lower() in ("1", "sim", "true", "on")


# --- Palavra de ativação
# Dois detectores trabalham juntos:
#  1. rápido (openWakeWord): reconhece "Jarvis" dito à inglesa ("djárvis") e bipa na hora;
#  2. por transcrição (Whisper): pega "Jarvis" em qualquer sotaque, inclusive na mesma frase
#     do pedido ("Jarvis, que horas são?"). Responde um pouco depois porque espera a frase acabar.
WAKE_PALAVRA = os.getenv("WAKE_PALAVRA", "jarvis").strip().lower()
WAKE_MODELO = os.getenv("WAKE_MODELO", "hey_jarvis")
WAKE_LIMIAR = float(os.getenv("WAKE_LIMIAR", "0.5"))
WAKE_TRANSCRICAO = _liga("WAKE_TRANSCRICAO")

# --- Transcrição local (faster-whisper): tiny, base, small. Maior = mais preciso e mais lento.
WHISPER_MODELO = os.getenv("WHISPER_MODELO", "small")
# No pacote portátil o modelo já vem na pasta, então não precisa de internet.
_whisper_local = RAIZ / "modelos" / f"whisper-{WHISPER_MODELO}"
WHISPER_CAMINHO = str(_whisper_local) if _whisper_local.is_dir() else WHISPER_MODELO

# --- Voz local (Piper)
PIPER_VOZ = os.getenv("PIPER_VOZ", "pt_BR-faber-medium")
PASTA_VOZES = RAIZ / "vozes"

# --- IA para perguntas abertas. Qualquer servidor compatível com a API da OpenAI serve.
#  ollama: roda no próprio PC, de graça e offline (instale com "Instalar IA local.bat")
#  groq:   nuvem com plano gratuito, bem mais rápida e esperta; exige GROQ_API_KEY
#  nenhum: só comandos locais
PROVEDORES = {
    "ollama": {"url": "http://127.0.0.1:11434/v1", "modelo": "qwen2.5:3b", "chave": ""},
    "groq": {"url": "https://api.groq.com/openai/v1", "modelo": "llama-3.3-70b-versatile", "chave": os.getenv("GROQ_API_KEY", "")},
}
IA_PROVEDOR = os.getenv("IA_PROVEDOR", "auto").strip().lower()
if IA_PROVEDOR == "auto":
    IA_PROVEDOR = "groq" if os.getenv("GROQ_API_KEY") else "ollama"
_p = PROVEDORES.get(IA_PROVEDOR, {"url": "", "modelo": "", "chave": ""})
IA_URL = os.getenv("IA_URL", _p["url"]).rstrip("/")
IA_MODELO = os.getenv("IA_MODELO", _p["modelo"])
IA_CHAVE = os.getenv("IA_CHAVE", _p["chave"])
IA_FERRAMENTAS = _liga("IA_FERRAMENTAS")

# --- Interface
HUD = _liga("HUD")

ARQUIVO_AGENDA = RAIZ / "lembretes.json"
TAXA = 16000  # Hz, exigido pelo wake word e pelo Whisper
BLOCO = 1280  # 80 ms
