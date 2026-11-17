"""Perguntas abertas vão para uma IA gratuita: local (Ollama) ou em nuvem com plano grátis (Groq).

Fala o protocolo de chat da OpenAI, que ambos aceitam, usando só a biblioteca padrão.
"""
import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime

import config
from . import pc
from .agenda import Agenda, falar_duracao

SISTEMA = """Você é o Jarvis, um assistente de voz que roda no computador pessoal do usuário, no Brasil. \
Tudo o que você escreve é lido em voz alta, então responda sempre em português do Brasil, falado e \
natural, em uma a três frases curtas, sem markdown, listas, emojis, links ou símbolos. Escreva números \
e siglas do jeito que se fala. O texto do usuário vem de transcrição automática e pode ter erros; \
interprete pelo sentido mais provável. Use uma ferramenta somente quando o usuário pedir claramente \
uma ação no computador (abrir algo, tocar, volume, timer, lembrete); para perguntas e conversa, \
responda direto, sem ferramenta. Se não souber, diga que não sabe."""


def _f(nome: str, descricao: str, props: dict, obrigatorios: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": nome,
            "description": descricao,
            "parameters": {"type": "object", "properties": props, "required": obrigatorios},
        },
    }


FERRAMENTAS = [
    _f("abrir_app", "Abre um programa instalado ou um site conhecido pelo nome, como chrome, spotify ou youtube.",
       {"nome": {"type": "string"}}, ["nome"]),
    _f("abrir_site", "Abre uma URL http ou https no navegador.", {"url": {"type": "string"}}, ["url"]),
    _f("tocar", "Busca uma música ou vídeo para tocar.",
       {"termo": {"type": "string"}, "onde": {"type": "string", "enum": ["youtube", "spotify"]}}, ["termo", "onde"]),
    _f("midia", "Controla a mídia tocando ou o volume. A ação volume exige valor de 0 a 100.",
       {"acao": {"type": "string", "enum": ["play_pause", "proxima", "anterior", "volume", "mudo", "tirar_mudo"]},
        "valor": {"type": "integer"}}, ["acao"]),
    _f("criar_timer", "Inicia um timer que avisa em voz alta ao terminar.", {"segundos": {"type": "integer"}}, ["segundos"]),
    _f("criar_lembrete", "Agenda um lembrete falado. quando é data e hora local no formato AAAA-MM-DDTHH:MM.",
       {"quando": {"type": "string"}, "texto": {"type": "string"}}, ["quando", "texto"]),
]


class ErroIA(Exception):
    pass


class Cerebro:
    def __init__(self, agenda: Agenda):
        self.agenda = agenda
        self.ativo = bool(config.IA_URL and config.IA_MODELO)
        self.mensagens: list[dict] = []
        self.ultimo_uso = 0.0

    # ------------------------------------------------------------------ rede
    def _post(self, corpo: dict, timeout: float = 120) -> dict:
        cabecalhos = {"Content-Type": "application/json", "User-Agent": "assistente-virtual"}
        if config.IA_CHAVE:
            cabecalhos["Authorization"] = f"Bearer {config.IA_CHAVE}"
        pedido = urllib.request.Request(
            config.IA_URL + "/chat/completions", data=json.dumps(corpo).encode("utf-8"), headers=cabecalhos
        )
        try:
            with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
                return json.loads(resposta.read().decode("utf-8"))
        except urllib.error.HTTPError as erro:
            detalhe = erro.read().decode("utf-8", "replace")[:300]
            print(f"   IA devolveu HTTP {erro.code}: {detalhe}")
            if erro.code == 401:
                raise ErroIA("A chave da inteligência artificial foi recusada. Confira o arquivo de configurações.")
            if erro.code == 404:
                raise ErroIA(f"O modelo {config.IA_MODELO} não está instalado. Rode o instalador da IA local.")
            if erro.code == 429:
                raise ErroIA("A inteligência artificial atingiu o limite gratuito por agora. Tente daqui a pouco.")
            if erro.code == 400 and "tool" in detalhe.lower():
                raise ErroIA("ferramentas")
            raise ErroIA("A inteligência artificial devolveu um erro.")
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if config.IA_PROVEDOR == "ollama":
                raise ErroIA("A inteligência artificial local não está rodando. Abra o instalador da IA local.")
            raise ErroIA("Estou sem conexão com a inteligência artificial, então só faço comandos locais.")

    def aquecer(self) -> None:
        """Carrega o modelo local na memória em segundo plano, para a primeira pergunta não demorar."""
        if not self.ativo or config.IA_PROVEDOR != "ollama":
            return

        def _carregar():
            try:
                self._post({"model": config.IA_MODELO, "messages": [{"role": "user", "content": "oi"}], "max_tokens": 1}, timeout=180)
            except ErroIA:
                pass

        threading.Thread(target=_carregar, daemon=True).start()

    # ----------------------------------------------------------- ferramentas
    def _executar(self, nome: str, e: dict) -> str:
        if nome == "abrir_app":
            aberto = pc.abrir(str(e["nome"]))
            return f"Abriu {aberto}." if aberto else "Não encontrado no computador."
        if nome == "abrir_site":
            return "Aberto." if pc.abrir_site(str(e["url"])) else "URL inválida."
        if nome == "tocar":
            (pc.tocar_spotify if e.get("onde") == "spotify" else pc.tocar_youtube)(str(e["termo"]))
            return "Busca aberta."
        if nome == "midia":
            acao = e["acao"]
            if acao == "volume":
                return f"Volume em {pc.definir_volume(int(e.get('valor', 50)))}%."
            {"play_pause": pc.play_pause, "proxima": pc.proxima, "anterior": pc.anterior,
             "mudo": lambda: pc.mudo(True), "tirar_mudo": lambda: pc.mudo(False)}[acao]()
            return "Feito."
        if nome == "criar_timer":
            segundos = int(e["segundos"])
            if not 0 < segundos <= 86400:
                return "Duração inválida."
            self.agenda.timer(segundos)
            return f"Timer de {falar_duracao(segundos)} iniciado."
        if nome == "criar_lembrete":
            quando = datetime.fromisoformat(str(e["quando"]))
            if quando <= datetime.now():
                return "Esse horário já passou."
            self.agenda.lembrete(quando.timestamp(), str(e["texto"]))
            return f"Lembrete marcado para {quando:%d/%m às %H:%M}."
        return "Ferramenta desconhecida."

    # --------------------------------------------------------------- conversa
    def perguntar(self, frase: str) -> str:
        if not self.ativo:
            return "Não entendi esse comando, e a inteligência artificial está desligada."
        # Conversa nova depois de 5 minutos parado ou se ficar longa demais.
        if time.time() - self.ultimo_uso > 300 or len(self.mensagens) > 24:
            self.mensagens = []
        self.ultimo_uso = time.time()
        self.mensagens.append({"role": "user", "content": frase})
        try:
            return self._conversar(config.IA_FERRAMENTAS)
        except ErroIA as erro:
            if str(erro) == "ferramentas":  # modelo sem suporte a ferramentas: tenta só conversa
                try:
                    return self._conversar(False)
                except ErroIA as outro:
                    erro = outro
            self.mensagens = []
            return str(erro)

    def _conversar(self, com_ferramentas: bool) -> str:
        agora = datetime.now()
        sistema = {"role": "system", "content": f"{SISTEMA}\nAgora são {agora:%H:%M} de {agora:%d/%m/%Y}."}
        for _ in range(4):
            corpo = {"model": config.IA_MODELO, "messages": [sistema] + self.mensagens, "max_tokens": 400, "temperature": 0.4}
            if com_ferramentas:
                corpo["tools"] = FERRAMENTAS
            resposta = self._post(corpo)["choices"][0]["message"]
            chamadas = resposta.get("tool_calls") or []
            self.mensagens.append({"role": "assistant", "content": resposta.get("content") or "", **({"tool_calls": chamadas} if chamadas else {})})
            if not chamadas:
                return (resposta.get("content") or "").strip() or "Pronto."
            for chamada in chamadas:
                funcao = chamada.get("function", {})
                try:
                    argumentos = funcao.get("arguments") or {}
                    if isinstance(argumentos, str):
                        argumentos = json.loads(argumentos or "{}")
                    saida = self._executar(funcao.get("name", ""), argumentos)
                except Exception as falha:
                    saida = f"Falhou: {falha}"
                print(f"   ferramenta {funcao.get('name')}: {saida}")
                self.mensagens.append({"role": "tool", "tool_call_id": chamada.get("id", ""), "content": saida})
        return "Não consegui concluir isso."
