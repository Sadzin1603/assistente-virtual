"""Ações no Windows: abrir programas e sites, volume, mídia, energia."""
import ctypes
import difflib
import os
import subprocess
import unicodedata
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus, urlparse

SITES = {
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "email": "https://mail.google.com",
    "google": "https://www.google.com",
    "whatsapp": "https://web.whatsapp.com",
    "netflix": "https://www.netflix.com",
    "github": "https://github.com",
    "claude": "https://claude.ai",
    "instagram": "https://www.instagram.com",
    "twitch": "https://www.twitch.tv",
    "maps": "https://maps.google.com",
    "mapa": "https://maps.google.com",
    "agenda": "https://calendar.google.com",
    "drive": "https://drive.google.com",
}

# Nome falado -> alvo resolvido pelo próprio Windows (App Paths ou protocolo).
APPS = {
    "bloco de notas": "notepad",
    "notepad": "notepad",
    "calculadora": "calc",
    "explorador de arquivos": "explorer",
    "explorador": "explorer",
    "arquivos": "explorer",
    "paint": "mspaint",
    "gerenciador de tarefas": "taskmgr",
    "configuracoes": "ms-settings:",
    "terminal": "wt",
    "chrome": "chrome",
    "navegador": "https://www.google.com",
    "edge": "msedge",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "spotify": "spotify:",
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
}

VK_MUDO, VK_PROXIMA, VK_ANTERIOR, VK_PLAY_PAUSE = 0xAD, 0xB0, 0xB1, 0xB3
VK_WIN, VK_PRINT = 0x5B, 0x2C


def _norm(s: str) -> str:
    s = "".join(unicodedata.normalize("NFD", c)[0] for c in s.lower())
    return " ".join(s.split())


def _tecla(*codigos: int) -> None:
    user32 = ctypes.windll.user32
    for c in codigos:
        user32.keybd_event(c, 0, 0, 0)
    for c in reversed(codigos):
        user32.keybd_event(c, 0, 2, 0)


def _atalhos_menu_iniciar() -> dict[str, Path]:
    pastas = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
    ]
    achados = {}
    for pasta in pastas:
        if pasta.is_dir():
            for lnk in pasta.rglob("*.lnk"):
                achados.setdefault(_norm(lnk.stem), lnk)
    return achados


def abrir(nome: str) -> str | None:
    """Abre um site conhecido, um app conhecido ou um atalho do Menu Iniciar.

    Só abre alvos dessas três listas, nunca um comando arbitrário.
    Devolve o nome do que abriu, ou None se não encontrou.
    """
    chave = _norm(nome)
    for prefixo in ("o ", "a ", "os ", "as ", "meu ", "minha ", "site ", "site do ", "site da ", "aplicativo ", "programa "):
        if chave.startswith(prefixo):
            chave = chave[len(prefixo):]
    if chave in SITES:
        webbrowser.open(SITES[chave])
        return chave
    if chave in APPS:
        try:
            os.startfile(APPS[chave])
            return chave
        except OSError:
            pass
    atalhos = _atalhos_menu_iniciar()
    alvo = atalhos.get(chave)
    if alvo is None:
        contem = [n for n in atalhos if chave in n.split() or n.startswith(chave)]
        proximos = contem or difflib.get_close_matches(chave, list(atalhos), n=1, cutoff=0.8)
        if proximos:
            chave = min(proximos, key=len)
            alvo = atalhos[chave]
    if alvo is None:
        return None
    os.startfile(str(alvo))
    return chave


def abrir_site(url: str) -> bool:
    if "://" not in url:
        url = "https://" + url
    p = urlparse(url)
    if p.scheme not in ("http", "https") or "." not in p.netloc:
        return False
    webbrowser.open(url)
    return True


def pesquisar(termo: str) -> None:
    webbrowser.open("https://www.google.com/search?q=" + quote_plus(termo))


def tocar_youtube(termo: str) -> None:
    webbrowser.open("https://www.youtube.com/results?search_query=" + quote_plus(termo))


def tocar_spotify(termo: str) -> None:
    try:
        os.startfile("spotify:search:" + quote_plus(termo))
    except OSError:
        webbrowser.open("https://open.spotify.com/search/" + quote_plus(termo))


def _endpoint_volume():
    import comtypes
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    try:
        comtypes.CoInitialize()
    except OSError:
        pass
    alto_falante = AudioUtilities.GetSpeakers()
    if hasattr(alto_falante, "EndpointVolume"):
        return alto_falante.EndpointVolume
    interface = alto_falante.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
    return interface.QueryInterface(IAudioEndpointVolume)


def volume_atual() -> int:
    return round(_endpoint_volume().GetMasterVolumeLevelScalar() * 100)


def definir_volume(pct: int) -> int:
    pct = max(0, min(100, int(pct)))
    ep = _endpoint_volume()
    ep.SetMute(0, None)
    ep.SetMasterVolumeLevelScalar(pct / 100, None)
    return pct


def mudar_volume(delta: int) -> int:
    return definir_volume(volume_atual() + delta)


def mudo(ligar: bool) -> None:
    _endpoint_volume().SetMute(1 if ligar else 0, None)


def play_pause() -> None:
    _tecla(VK_PLAY_PAUSE)


def proxima() -> None:
    _tecla(VK_PROXIMA)


def anterior() -> None:
    _tecla(VK_ANTERIOR)


def captura_de_tela() -> None:
    """Win+PrintScreen: o Windows salva em Imagens\\Capturas de tela."""
    _tecla(VK_WIN, VK_PRINT)


def bloquear() -> None:
    ctypes.windll.user32.LockWorkStation()


def desligar(reiniciar: bool = False, segundos: int = 60) -> None:
    subprocess.run(["shutdown", "/r" if reiniciar else "/s", "/t", str(segundos)], check=False)


def cancelar_desligamento() -> None:
    subprocess.run(["shutdown", "/a"], check=False)
