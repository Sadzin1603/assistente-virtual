# Jarvis

Assistente de voz para Windows no estilo Alexa: diga **"Jarvis"** e faça o pedido, sem tocar no teclado.

- **Voz 100% local**: palavra de ativação (openWakeWord + Whisper), transcrição (faster-whisper) e fala (Piper) rodam no próprio PC.
- **Comandos locais**: abrir programas e sites, volume, mídia, timers, lembretes, hora, bloquear, desligar. Funcionam offline.
- **IA gratuita para perguntas abertas**: local com [Ollama](https://ollama.com) ou na nuvem com o plano grátis da [Groq](https://console.groq.com).
- **HUD**: um indicador sempre por cima das janelas mostra se ele está ouvindo, pensando ou falando.
- **Atualização automática**: o pacote portátil confere este repositório toda vez que abre.

## Instalar (pacote portátil)

1. Baixe `Jarvis-Portatil.zip` em [Releases](../../releases/latest).
2. Extraia em uma pasta de caminho curto, por exemplo `C:\Jarvis`.
3. Abra `Diagnostico.bat` e depois `Iniciar.bat`.

Não precisa instalar Python nem ter internet para a voz. As próximas versões chegam sozinhas.

## Como falar

Diga "Jarvis", espere o bipe de duas notas e fale. Ou diga tudo de uma vez: "Jarvis, que horas são?".
Um bipe grave indica que ele voltou a esperar o nome.

O bipe sai na hora quando o nome é dito à inglesa ("djárvis"). Em outras pronúncias ele é reconhecido
pela transcrição, que espera a frase terminar, então a reação vem um pouco depois.

| Diga | O que acontece |
|---|---|
| "que horas são?" / "que dia é hoje?" | responde |
| "abre o Chrome" / "abre o YouTube" | abre o programa (Menu Iniciar) ou o site |
| "pesquisa por receita de pão" | busca no Google |
| "toca Legião Urbana no YouTube" / "... no Spotify" | abre a busca |
| "pausa" / "próxima música" / "volta a música" | teclas de mídia |
| "aumenta o volume" / "volume em 30" / "muta" | volume do sistema |
| "timer de 10 minutos" / "quanto tempo falta?" / "cancela o timer" | timer com aviso falado |
| "me lembra de tirar o lixo em 20 minutos" / "... às 18:30" | lembrete (fica salvo em `lembretes.json`) |
| "bloqueia a tela" / "tira um print" | |
| "desliga o computador" / "cancela o desligamento" | desliga em 1 minuto |
| "encerrar assistente" | fecha o programa |
| qualquer outra coisa | vai para a IA |

## IA gratuita

| Opção | Como ligar | Prós e contras |
|---|---|---|
| Local (Ollama) | abra `Instalar IA local.bat` uma vez | offline e sem conta; alguns segundos por resposta; usa cerca de 3 GB de RAM |
| Nuvem (Groq) | chave grátis em `GROQ_API_KEY` no `.env` | rápida e mais esperta; precisa de internet e tem limite diário |

Qualquer servidor compatível com a API da OpenAI funciona: defina `IA_URL`, `IA_MODELO` e `IA_CHAVE`.

## Configuração (`.env`)

| Variável | Padrão | Para quê |
|---|---|---|
| `IA_PROVEDOR` | `auto` | `ollama`, `groq` ou `nenhum`; `auto` usa a Groq se houver chave |
| `IA_MODELO` | `qwen2.5:3b` | modelo da IA |
| `WAKE_PALAVRA` | `jarvis` | nome reconhecido pela transcrição |
| `WAKE_LIMIAR` | `0.5` | sensibilidade do detector rápido: suba se disparar sozinho |
| `WAKE_TRANSCRICAO` | `1` | `0` desliga o detector por transcrição (economiza CPU) |
| `WHISPER_MODELO` | `small` | `base` é mais rápido e erra mais |
| `HUD` | `1` | `0` esconde o indicador na tela |
| `AUTO_ATUALIZAR` | `1` | `0` desliga a atualização automática |

## Desenvolvimento

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py --texto                  modo texto
.venv\Scripts\python autoteste.py                     diagnóstico
.venv\Scripts\python -m unittest discover -s tests    testes
powershell -ExecutionPolicy Bypass -File empacotar.ps1    gera dist\Jarvis-Portatil.zip
```

Cada `git push` na `main` vira atualização para quem usa o pacote portátil. Mudanças no Python embutido
ou nos modelos exigem publicar um zip novo em Releases.

```
main.py                 laço principal (voz ou texto)
lancador.py             entrada dos .bat: confere o pacote, atualiza e inicia
atualizar.py            atualização automática pelo GitHub
config.py               configurações lidas do .env
assistente/comandos.py  comandos locais por padrões de frase
assistente/pc.py        ações no Windows
assistente/agenda.py    timers e lembretes
assistente/voz.py       palavra de ativação, transcrição e fala
assistente/audio.py     microfone e detecção de fala
assistente/cerebro.py   conversa com a IA e ferramentas
assistente/hud.py       indicador sempre por cima
empacote/               arquivos que vão para a raiz do pacote portátil
```
