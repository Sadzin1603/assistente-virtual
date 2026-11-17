"""Testa os comandos locais com o controle do PC simulado (nada é aberto de verdade)."""
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assistente import comandos  # noqa: E402
from assistente.agenda import Agenda  # noqa: E402


class TestComandos(unittest.TestCase):
    def setUp(self):
        self.pc = MagicMock()
        self.pc.mudar_volume.return_value = 60
        self.pc.definir_volume.side_effect = lambda v: v
        self.pc.abrir.side_effect = lambda nome: nome if "chrome" in nome else None
        patch.object(comandos, "pc", self.pc).start()
        self.addCleanup(patch.stopall)
        self.avisos = []
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.agenda = Agenda(Path(pasta.name) / "agenda.json", self.avisos.append)

    def r(self, frase):
        return comandos.interpretar(frase, self.agenda)

    def test_hora_e_data(self):
        self.assertIn("horas", self.r("Que horas são?").texto)
        self.assertIn(str(datetime.now().year), self.r("Que dia é hoje?").texto)

    def test_volume(self):
        self.assertEqual(self.r("Aumenta o volume.").texto, "Volume em 60 por cento.")
        self.pc.mudar_volume.assert_called_with(10)
        self.r("abaixa o som")
        self.pc.mudar_volume.assert_called_with(-10)
        self.assertEqual(self.r("Coloca o volume em 35").texto, "Volume em 35 por cento.")
        self.r("Muta o som")
        self.pc.mudo.assert_called_with(True)
        self.r("tira do mudo")
        self.pc.mudo.assert_called_with(False)

    def test_midia(self):
        self.r("Pausa a música.")
        self.pc.play_pause.assert_called_once()
        self.r("próxima música")
        self.pc.proxima.assert_called_once()
        self.r("volta a música")
        self.pc.anterior.assert_called_once()
        self.r("Toca Legião Urbana no YouTube")
        self.pc.tocar_youtube.assert_called_with("legião urbana")
        self.r("toca lo-fi no spotify")
        self.pc.tocar_spotify.assert_called_with("lo fi")

    def test_abrir_e_pesquisar(self):
        self.assertEqual(self.r("Abre o Chrome.").texto, "Abrindo o chrome.")
        self.assertIsNone(self.r("abre o programa inexistente"))
        self.r("Pesquisa por receita de pão no Google")
        self.pc.pesquisar.assert_called_with("receita de pão")

    def test_energia(self):
        self.r("bloqueia a tela")
        self.pc.bloquear.assert_called_once()
        self.r("Desliga o computador")
        self.pc.desligar.assert_called_once_with()
        self.r("cancela o desligamento")
        self.pc.cancelar_desligamento.assert_called_once()
        self.r("tira um print")
        self.pc.captura_de_tela.assert_called_once()

    def test_timer(self):
        self.assertEqual(self.r("Coloca um timer de 5 minutos").texto, "Timer de 5 minutos iniciado.")
        self.assertEqual(self.r("timer de uma hora e meia").texto, "Timer de 1 hora e 30 minutos iniciado.")
        self.assertEqual(self.r("timer de vinte e cinco segundos").texto, "Timer de 25 segundos iniciado.")
        self.assertEqual(len(self.agenda.pendentes("timer")), 3)
        self.assertIn("Faltam", self.r("quanto tempo falta?").texto)
        self.assertEqual(self.r("cancela o timer").texto, "Timer cancelado.")
        self.assertEqual(self.agenda.pendentes(), [])

    def test_timer_dispara(self):
        self.r("timer de 1 segundo")
        time.sleep(2)
        self.assertEqual(self.avisos, ["Seu timer de 1 segundo terminou."])

    def test_lembrete(self):
        resp = self.r("Me lembra de tirar o lixo em 10 minutos")
        self.assertIn("tirar o lixo", resp.texto)
        item = self.agenda.pendentes("lembrete")[0]
        self.assertEqual(item["aviso"], "Lembrete: tirar o lixo.")
        self.assertAlmostEqual(item["quando"], time.time() + 600, delta=5)

        self.r("me lembra da reunião às 15:30")
        item = self.agenda.pendentes("lembrete")[-1] if len(self.agenda.pendentes("lembrete")) > 1 else None
        horas = {datetime.fromtimestamp(i["quando"]).strftime("%H:%M") for i in self.agenda.pendentes("lembrete")}
        self.assertIn("15:30", horas)
        self.assertIsNotNone(item)

        self.r("me avisa de ligar pro banco às 3 da tarde")
        horas = {datetime.fromtimestamp(i["quando"]).strftime("%H:%M") for i in self.agenda.pendentes("lembrete")}
        self.assertIn("15:00", horas)

    def test_controle(self):
        self.assertEqual(self.r("cancela").texto, "")
        self.assertTrue(self.r("encerrar assistente").sair)

    def test_pergunta_aberta_vai_para_ia(self):
        for frase in ("Qual a capital da Austrália?", "me conta uma piada", "quanto é 15 por cento de 80"):
            self.assertIsNone(self.r(frase), frase)
        self.pc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
