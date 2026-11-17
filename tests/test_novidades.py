"""Palavra de ativação por texto, IA via servidor falso e atualizador com GitHub simulado."""
import io
import json
import sys
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import atualizar  # noqa: E402
import config  # noqa: E402
from assistente import cerebro  # noqa: E402
from assistente.voz import separar_wake  # noqa: E402


class TestWake(unittest.TestCase):
    def test_separa_nome_e_pedido(self):
        casos = {
            "Jarvis, que horas são?": (True, "que horas são"),
            "Jarvis.": (True, ""),
            "Ei, Jarvis, abre o Chrome": (True, "abre o Chrome"),
            "Javis aumenta o volume": (True, "aumenta o volume"),
            "Que dia é hoje, Jervis?": (True, "Que dia é hoje"),
            "Járvis timer de 5 minutos": (True, "timer de 5 minutos"),
        }
        for frase, esperado in casos.items():
            self.assertEqual(separar_wake(frase), esperado, frase)

    def test_ignora_conversa_comum(self):
        for frase in ("que horas são?", "vou no jardim regar as plantas", "já vi isso ontem", "o serviço atrasou", ""):
            self.assertFalse(separar_wake(frase)[0], frase)


class ServidorFalso(BaseHTTPRequestHandler):
    respostas: list = []
    pedidos: list = []

    def do_POST(self):
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        ServidorFalso.pedidos.append(corpo)
        dados = json.dumps({"choices": [{"message": ServidorFalso.respostas.pop(0)}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(dados)

    def log_message(self, *args):
        pass


class TestCerebro(unittest.TestCase):
    def setUp(self):
        self.servidor = HTTPServer(("127.0.0.1", 0), ServidorFalso)
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        self.addCleanup(self.servidor.shutdown)
        ServidorFalso.respostas, ServidorFalso.pedidos = [], []
        url = f"http://127.0.0.1:{self.servidor.server_port}/v1"
        for nome, valor in (("IA_URL", url), ("IA_MODELO", "teste"), ("IA_CHAVE", ""), ("IA_FERRAMENTAS", True), ("IA_PROVEDOR", "ollama")):
            patch.object(config, nome, valor).start()
        self.pc = MagicMock()
        self.pc.abrir.return_value = "chrome"
        patch.object(cerebro, "pc", self.pc).start()
        self.addCleanup(patch.stopall)
        self.agenda = MagicMock()

    def test_resposta_simples(self):
        ServidorFalso.respostas = [{"role": "assistant", "content": "Camberra."}]
        self.assertEqual(cerebro.Cerebro(self.agenda).perguntar("capital da Austrália?"), "Camberra.")
        pedido = ServidorFalso.pedidos[0]
        self.assertEqual(pedido["model"], "teste")
        self.assertEqual(pedido["messages"][0]["role"], "system")
        self.assertIn("tools", pedido)

    def test_ferramenta_e_depois_resposta(self):
        ServidorFalso.respostas = [
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "abrir_app", "arguments": '{"nome": "chrome"}'}},
                {"id": "c2", "type": "function", "function": {"name": "criar_timer", "arguments": {"segundos": 300}}}]},
            {"role": "assistant", "content": "Abri o Chrome e marquei cinco minutos."},
        ]
        resposta = cerebro.Cerebro(self.agenda).perguntar("abre o navegador e marca 5 minutos")
        self.assertEqual(resposta, "Abri o Chrome e marquei cinco minutos.")
        self.pc.abrir.assert_called_once_with("chrome")
        self.agenda.timer.assert_called_once_with(300)
        retorno = [m for m in ServidorFalso.pedidos[1]["messages"] if m["role"] == "tool"]
        self.assertEqual([m["tool_call_id"] for m in retorno], ["c1", "c2"])

    def test_ferramenta_invalida_nao_derruba(self):
        ServidorFalso.respostas = [
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "apagar_tudo", "arguments": "{lixo"}}]},
            {"role": "assistant", "content": "Não consegui."},
        ]
        self.assertEqual(cerebro.Cerebro(self.agenda).perguntar("x"), "Não consegui.")

    def test_servidor_fora_do_ar(self):
        with patch.object(config, "IA_URL", "http://127.0.0.1:9/v1"):
            resposta = cerebro.Cerebro(self.agenda).perguntar("oi")
        self.assertIn("não está rodando", resposta)


def zip_do_repo(arquivos: dict[str, str]) -> bytes:
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w") as z:
        for nome, conteudo in arquivos.items():
            z.writestr("assistente-virtual-abc/" + nome, conteudo)
    return memoria.getvalue()


class TestAtualizar(unittest.TestCase):
    SHA = "a" * 40

    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.raiz = Path(pasta.name)
        (self.raiz / "assistente").mkdir()
        (self.raiz / "main.py").write_text("velho")
        (self.raiz / "assistente" / "removido.py").write_text("x")
        (self.raiz / "Iniciar.bat").write_text("bat original")
        (self.raiz / ".env").write_text("SEGREDO=1")
        self.repo = {
            "main.py": "novo", "config.py": "c", "assistente/voz.py": "v", "empacote/Iniciar.bat": "bat novo",
            "empacote/Novo.bat": "n", "empacote/LEIA-ME.txt": "leia", "tests/test_x.py": "t", "empacotar.ps1": "p",
            ".gitignore": "g", "../fora.py": "malicioso", "assistente/sub/x.py": "x",
        }

    def baixar(self, url, timeout, aceitar="*/*"):
        return self.SHA.encode() if "api.github.com" in url else zip_do_repo(self.repo)

    def test_destinos(self):
        self.assertEqual(atualizar.destino("main.py"), "main.py")
        self.assertEqual(atualizar.destino("empacote/Iniciar.bat"), "Iniciar.bat")
        self.assertEqual(atualizar.destino("assistente/hud.py"), "assistente/hud.py")
        for fora in ("tests/a.py", "../x.py", "/abs.py", ".env", "empacotar.ps1", "assistente/../../x.py", "runtime/python.exe"):
            self.assertIsNone(atualizar.destino(fora), fora)

    def test_atualiza_so_o_codigo(self):
        with patch.object(atualizar, "_baixar", self.baixar):
            self.assertTrue(atualizar.verificar_e_atualizar(self.raiz, log=lambda m: None))
            self.assertEqual((self.raiz / "main.py").read_text(), "novo")
            self.assertEqual((self.raiz / "assistente" / "voz.py").read_text(), "v")
            self.assertEqual((self.raiz / "Iniciar.bat").read_text(), "bat original")  # .bat existente é preservado
            self.assertEqual((self.raiz / "Novo.bat").read_text(), "n")
            self.assertEqual((self.raiz / ".env").read_text(), "SEGREDO=1")
            self.assertFalse((self.raiz / "assistente" / "removido.py").exists())
            self.assertFalse((self.raiz / "tests").exists())
            self.assertFalse((self.raiz.parent / "fora.py").exists())
            self.assertEqual((self.raiz / "versao.txt").read_text(), self.SHA)
            self.assertFalse(atualizar.verificar_e_atualizar(self.raiz, log=lambda m: None))  # já está na versão

    def test_sem_internet_ou_desligado(self):
        def sem_rede(*a, **k):
            raise OSError("sem rede")
        with patch.object(atualizar, "_baixar", sem_rede):
            self.assertFalse(atualizar.verificar_e_atualizar(self.raiz, log=lambda m: None))
        (self.raiz / ".env").write_text("AUTO_ATUALIZAR=0")
        with patch.object(atualizar, "_baixar", self.baixar):
            self.assertFalse(atualizar.verificar_e_atualizar(self.raiz, log=lambda m: None))
        self.assertEqual((self.raiz / "main.py").read_text(), "velho")

    def test_pasta_git_nao_e_tocada(self):
        (self.raiz / ".git").mkdir()
        with patch.object(atualizar, "_baixar", self.baixar):
            self.assertFalse(atualizar.verificar_e_atualizar(self.raiz, log=lambda m: None))


if __name__ == "__main__":
    unittest.main()
