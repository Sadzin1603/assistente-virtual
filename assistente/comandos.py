"""Comandos resolvidos localmente, sem internet e sem IA.

interpretar() devolve uma Resposta, ou None quando a frase não é um comando
conhecido (aí ela segue para a IA).
"""
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import pc
from .agenda import Agenda, falar_duracao


@dataclass
class Resposta:
    texto: str
    sair: bool = False


NUMEROS = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6,
    "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13,
    "quatorze": 14, "catorze": 14, "quinze": 15, "dezesseis": 16, "dezessete": 17,
    "dezoito": 18, "dezenove": 19, "vinte": 20, "trinta": 30, "quarenta": 40,
    "cinquenta": 50, "sessenta": 60, "noventa": 90, "meia": 0.5, "meio": 0.5,
}
UNIDADES = {"segundo": 1, "minuto": 60, "hora": 3600}
_QTD = r"(\d+|[a-z]+(?: e [a-z]+)?)"
_DURACAO = re.compile(_QTD + r" (segundo|minuto|hora)s?( e meia)?")
_HORARIO = re.compile(r"\b(?:as|a) (\d{1,2})(?:(?::| ?h ?| e )(\d{1,2}))?(?: ?h| horas?)?(?: e (meia))?( da tarde| da noite| da manha)?$")
_DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def limpar(frase: str) -> str:
    """Minúsculas, sem pontuação (mantém ':' das horas), mantendo os acentos."""
    frase = re.sub(r"[^\w: ]", " ", frase.lower().replace("_", " "))
    return " ".join(frase.split())


def sem_acento(s: str) -> str:
    """Remove acentos preservando o tamanho, para os índices baterem com o original."""
    return "".join(unicodedata.normalize("NFD", c)[0] for c in s)


def _numero(txt: str) -> float | None:
    if txt.isdigit():
        return float(txt)
    partes = txt.split(" e ")
    if all(p in NUMEROS for p in partes):
        return float(sum(NUMEROS[p] for p in partes))
    if partes[-1] in NUMEROS:  # "timer de cinco": o "de" entrou junto
        return float(NUMEROS[partes[-1]])
    return None


def duracao(norm: str) -> tuple[float, int, int] | None:
    """Soma as durações da frase. Devolve (segundos, início, fim do trecho)."""
    total, ini, fim = 0.0, None, None
    for m in _DURACAO.finditer(norm):
        n = _numero(m.group(1))
        if n is None:
            continue
        base = UNIDADES[m.group(2)]
        total += n * base + (base / 2 if m.group(3) else 0)
        ini = m.start() if ini is None else ini
        fim = m.end()
    return (total, ini, fim) if total > 0 else None


def horario(norm: str) -> tuple[float, int] | None:
    """Horário no fim da frase ('às 15:30', 'às 3 da tarde'). Devolve (epoch, início)."""
    m = _HORARIO.search(norm)
    if not m:
        return None
    h, minuto = int(m.group(1)), int(m.group(2) or 0)
    if m.group(3):
        minuto = 30
    periodo = (m.group(4) or "").strip()
    if periodo in ("da tarde", "da noite") and h < 12:
        h += 12
    if h > 23 or minuto > 59:
        return None
    agora = datetime.now()
    alvo = agora.replace(hour=h, minute=minuto, second=0, microsecond=0)
    if alvo <= agora:
        alvo += timedelta(days=1)
    return alvo.timestamp(), m.start()


def interpretar(frase: str, agenda: Agenda) -> Resposta | None:
    orig = limpar(frase)
    t = sem_acento(orig)
    if not t:
        return Resposta("")

    def tem(padrao: str):
        return re.search(padrao, t)

    # --- controle do próprio assistente
    if tem(r"^(para|pare|cancela|cancelar|esquece|deixa|deixa pra la|nada|nada nao|obrigado|obrigada|valeu)$"):
        return Resposta("")
    if tem(r"\b(encerra|encerrar|fecha|fechar|desliga|desligar) (o )?assistente\b|^(tchau|ate logo|ate mais)$"):
        return Resposta("Até logo.", sair=True)

    # --- hora e data
    if tem(r"\bque horas?\b|\bhoras sao\b|\bhora certa\b"):
        a = datetime.now()
        return Resposta(f"São {a.hour} horas e {a.minute} minutos." if a.minute else f"São {a.hour} horas.")
    if tem(r"\bque dia e hoje\b|\bdata de hoje\b|\bdia e hoje\b|\bqual a data\b"):
        a = datetime.now()
        return Resposta(f"Hoje é {_DIAS[a.weekday()]}, {a.day} de {_MESES[a.month - 1]} de {a.year}.")

    # --- energia e tela
    if tem(r"\bcancela\w* (o )?(desligamento|reinicio)\b"):
        pc.cancelar_desligamento()
        return Resposta("Desligamento cancelado.")
    if tem(r"\b(desliga|desligar|desligue) (o )?(computador|pc|notebook)\b"):
        pc.desligar()
        return Resposta("Desligando em um minuto. Para desistir, diga: cancela o desligamento.")
    if tem(r"\b(reinicia|reiniciar|reinicie) (o )?(computador|pc|notebook)\b"):
        pc.desligar(reiniciar=True)
        return Resposta("Reiniciando em um minuto. Para desistir, diga: cancela o desligamento.")
    if tem(r"\b(bloqueia|bloquear|bloqueie|trava|travar) (a )?(tela|o computador|o pc|computador|pc)\b"):
        pc.bloquear()
        return Resposta("Tela bloqueada.")
    if tem(r"\b(tira|tirar|tire|faz|faca) (um |uma )?(print|captura)\b|\bcaptura de tela\b"):
        pc.captura_de_tela()
        return Resposta("Captura salva na pasta de imagens.")

    # --- timers e lembretes (antes de mídia: "para o timer" não é "para a música")
    if tem(r"\b(cancela|cancelar|para|parar|remove|apaga)\w* (o |os |todos os )?(timer|timers|taner|taimer|cronometro|alarme|temporizador)"):
        n = agenda.cancelar("timer")
        return Resposta("Timer cancelado." if n else "Não há timer ativo.")
    if tem(r"\b(cancela|cancelar|apaga|remove)\w* (o |os |todos os )?lembretes?\b"):
        n = agenda.cancelar("lembrete")
        return Resposta(f"{n} lembrete(s) cancelado(s)." if n else "Não há lembretes.")
    if tem(r"\bquanto (tempo )?falta\b|\bquanto tempo (do|no|de) timer\b"):
        ativos = agenda.pendentes("timer")
        if not ativos:
            return Resposta("Não há timer ativo.")
        return Resposta(f"Faltam {falar_duracao(ativos[0]['quando'] - time.time())}.")
    if tem(r"\b(quais|meus|lista\w*) (sao )?(os )?(meus )?lembretes\b"):
        itens = agenda.pendentes("lembrete")
        if not itens:
            return Resposta("Você não tem lembretes.")
        falas = [f"{i['aviso'][10:-1]}, às {datetime.fromtimestamp(i['quando']):%H:%M}" for i in itens[:5]]
        return Resposta("Seus lembretes: " + "; ".join(falas) + ".")

    m = tem(r"\b(?:me )?(?:lembra|lembre|lembrar|avisa|avise)(?: me)?(?: de| que| para| pra)? ")
    if m:
        resto_ini = m.end()
        quando, corte = None, None
        d = duracao(t[resto_ini:])
        if d:
            quando = time.time() + d[0]
            antes = re.search(r"(?:^| )(?:em|daqui a|daqui|dentro de) ?$", t[resto_ini:resto_ini + d[1]])
            corte = resto_ini + (antes.start() if antes else d[1])
            sobra = orig[resto_ini + d[2]:].strip()
        else:
            h = horario(t[resto_ini:])
            if h:
                quando, corte, sobra = h[0], resto_ini + h[1], ""
        if quando:
            texto = (orig[resto_ini:corte].strip() + " " + sobra).strip()
            texto = re.sub(r"^(de|que|para|pra) ", "", texto) or "o que você pediu"
            agenda.lembrete(quando, texto)
            hora = datetime.fromtimestamp(quando)
            return Resposta(f"Certo, vou lembrar de {texto} às {hora:%H:%M}.")
        return None  # sem horário claro: a IA resolve

    # "taner"/"taimer": como o Whisper costuma escrever "timer"
    if tem(r"\b(timer|taner|taimer|tymer|cronometro|alarme|temporizador|conta|contar|cronometra)\b") or tem(r"^(me avisa|avisa) (em|daqui)"):
        d = duracao(t)
        if d:
            agenda.timer(d[0])
            return Resposta(f"Timer de {falar_duracao(d[0])} iniciado.")
        h = horario(t)
        if h and tem(r"\balarme\b"):
            agenda.lembrete(h[0], "alarme")
            return Resposta(f"Alarme marcado para as {datetime.fromtimestamp(h[0]):%H:%M}.")

    # --- volume
    m = tem(r"\bvolume (?:em|para|pra|no|a) (\d{1,3})\b|\b(\d{1,3}) ?(?:por cento|%) (?:de|do) volume\b")
    if m:
        v = pc.definir_volume(int(m.group(1) or m.group(2)))
        return Resposta(f"Volume em {v} por cento.")
    # Radicais em vez de formas exatas: o Whisper troca "aumenta" por "aumento" etc.
    if tem(r"\b(aument\w*|sobe|subir|suba|levant\w*) (um pouco )?(o )?(volume|som)\b|\bmais alto\b"):
        return Resposta(f"Volume em {pc.mudar_volume(10)} por cento.")
    if tem(r"\b(abaix|baix|diminu|reduz)\w* (um pouco )?(o )?(volume|som)\b|\bmais baixo\b"):
        return Resposta(f"Volume em {pc.mudar_volume(-10)} por cento.")
    if tem(r"\b(tira|tirar|tire) (do |o )?(mudo|mute)\b|\b(desmuta|desmutar|ativa o som|liga o som)\b"):
        pc.mudo(False)
        return Resposta("Som ligado.")
    if tem(r"\b(muta|mutar|silencia|silenciar|mudo|sem som|desliga o som)\b"):
        pc.mudo(True)
        return Resposta("")

    # --- mídia
    if tem(r"\b(proxima|proximo|pula|pular|avanca)\b.*\b(musica|faixa|video)?\b") and tem(r"\b(proxima|proximo|pula|pular|avanca)\b"):
        pc.proxima()
        return Resposta("")
    if tem(r"\b(musica|faixa) anterior\b|\b(volta|voltar) (a |uma )?(musica|faixa)\b"):
        pc.anterior()
        return Resposta("")
    if tem(r"^(pausa|pausar|pause|continua|continuar|retoma|retomar|despausa|play|da play)( (a|o|na|no))?( (musica|video|som))?$|^(para|parar|pare) (a |o )?(musica|video|som)$"):
        pc.play_pause()
        return Resposta("")
    m = tem(r"^(?:toca|tocar|toque|coloca|colocar|bota|poe)(?: a musica| o video| musica| video)? (.+?)(?: (?:no|do) (youtube|spotify))?$")
    if m:
        termo = orig[m.start(1):m.end(1)]
        if m.group(2) == "spotify":
            pc.tocar_spotify(termo)
            return Resposta(f"Buscando {termo} no Spotify.")
        pc.tocar_youtube(termo)
        return Resposta(f"Buscando {termo} no YouTube.")

    # --- pesquisar e abrir
    m = tem(r"^(?:pesquisa|pesquisar|pesquise|procura|procurar|busca|buscar)(?: por| sobre)? (.+?)(?: (?:no|na) (?:google|internet|web))?$")
    if m:
        termo = orig[m.start(1):m.end(1)]
        pc.pesquisar(termo)
        return Resposta(f"Pesquisando {termo}.")
    m = tem(r"^(?:abre|abrir|abra|inicia|iniciar|inicie|executa|executar|entra no|entra na) (.+)$")
    if m:
        aberto = pc.abrir(orig[m.start(1):m.end(1)])
        if aberto:
            return Resposta(f"Abrindo {aberto}.")

    return None
