# Monta o pacote portatil: Python embutido + bibliotecas + modelos, sem instalar nada no PC de destino.
# Uso:  powershell -ExecutionPolicy Bypass -File empacotar.ps1
$ErrorActionPreference = 'Stop'
$raiz = $PSScriptRoot
$nome = 'Jarvis'
$dist = Join-Path $raiz "dist\$nome"
$rt = Join-Path $dist 'runtime'
$venvPy = Join-Path $raiz '.venv\Scripts\python.exe'
$versao = (& $venvPy -c "import platform; print(platform.python_version())").Trim()
$base = (& $venvPy -c "import sys; print(sys.base_prefix)").Trim()
$tag = 'python' + ($versao.Split('.')[0..1] -join '')

Write-Host "1/6 Limpando dist"
if (Test-Path (Join-Path $raiz 'dist')) { Remove-Item (Join-Path $raiz 'dist') -Recurse -Force }
New-Item -ItemType Directory -Force $rt | Out-Null

Write-Host "2/6 Python embutido $versao"
$zipPy = Join-Path $raiz "dist\python-embed.zip"
Invoke-WebRequest "https://www.python.org/ftp/python/$versao/python-$versao-embed-amd64.zip" -OutFile $zipPy -UseBasicParsing
Expand-Archive $zipPy -DestinationPath $rt
Remove-Item $zipPy
# Caminhos de import: bibliotecas do pacote e a pasta do app (um nivel acima).
Set-Content -Encoding ascii (Join-Path $rt "$tag._pth") "$tag.zip`r`n.`r`npkgs`r`n..`r`nimport site"

Write-Host "3/6 Bibliotecas"
$origem = Join-Path $raiz '.venv\Lib\site-packages'
robocopy $origem (Join-Path $rt 'pkgs') /E /XD __pycache__ /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy falhou ($LASTEXITCODE)" }

# tkinter (para o HUD) nao vem no Python embutido: copia da instalacao completa.
foreach ($f in '_tkinter.pyd', 'tcl86t.dll', 'tk86t.dll', 'zlib1.dll') {
    $src = Join-Path $base "DLLs\$f"
    if (Test-Path $src) { Copy-Item $src $rt }
}
robocopy (Join-Path $base 'Lib\tkinter') (Join-Path $rt 'pkgs\tkinter') /E /XD __pycache__ test /NFL /NDL /NJH /NJS /NP | Out-Null
robocopy (Join-Path $base 'tcl') (Join-Path $rt 'tcl') /E /XD demos tzdata msgs /NFL /NDL /NJH /NJS /NP | Out-Null
if (-not (Test-Path (Join-Path $rt '_tkinter.pyd'))) { throw 'tkinter nao encontrado na instalacao do Python' }

# Runtime do Visual C++ ao lado do python.exe, para PCs que nao o tem instalado.
foreach ($dll in 'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll', 'vcruntime140.dll', 'vcruntime140_1.dll') {
    $src = Join-Path $env:WINDIR "System32\$dll"
    $dst = Join-Path $rt $dll
    if ((Test-Path $src) -and -not (Test-Path $dst)) { Copy-Item $src $dst }
}

Write-Host "4/6 Modelos"
$whisper = (& $venvPy -c "import config; print(config.WHISPER_MODELO)").Trim()
& $venvPy -W ignore -c "import sys; from faster_whisper import download_model; download_model(sys.argv[1], output_dir=sys.argv[2])" $whisper (Join-Path $dist "modelos\whisper-$whisper")
if ($LASTEXITCODE -ne 0) { throw 'download do Whisper falhou' }
Get-ChildItem (Join-Path $dist "modelos\whisper-$whisper") -Directory -Force -Filter '.cache' | Remove-Item -Recurse -Force
robocopy (Join-Path $raiz 'vozes') (Join-Path $dist 'vozes') /E /NFL /NDL /NJH /NJS /NP | Out-Null
if (-not (Get-ChildItem (Join-Path $dist 'vozes') -Filter '*.onnx')) { throw 'voz do Piper ausente: rode autoteste.py antes' }
if (-not (Get-ChildItem (Join-Path $rt 'pkgs\openwakeword\resources\models') -Filter '*.onnx')) { throw 'modelos de wake word ausentes: rode autoteste.py antes' }

Write-Host "5/6 Aplicativo"
foreach ($f in 'main.py', 'config.py', 'autoteste.py', 'lancador.py', 'atualizar.py', 'instalar_ia.py', 'requirements.txt', '.env.example', 'README.md') {
    Copy-Item (Join-Path $raiz $f) $dist
}
robocopy (Join-Path $raiz 'assistente') (Join-Path $dist 'assistente') *.py /NFL /NDL /NJH /NJS /NP | Out-Null
robocopy (Join-Path $raiz 'empacote') $dist /E /NFL /NDL /NJH /NJS /NP | Out-Null
# Versao instalada = commit atual, para o atualizador saber de onde partir.
$sha = (cmd /c "git -C `"$raiz`" rev-parse HEAD 2>nul") -join ''
if ($sha -match '^[0-9a-f]{40}$') { Set-Content -Encoding ascii -NoNewline (Join-Path $dist 'versao.txt') $sha }
else { Write-Host '    aviso: sem commit git; o pacote vai se atualizar na primeira abertura' }

# Lista dos arquivos pesados, para o lancador detectar extracao incompleta (caminho longo, antivirus).
$todos = Get-ChildItem (Join-Path $dist 'runtime'), (Join-Path $dist 'modelos'), (Join-Path $dist 'vozes') -Recurse -File |
    ForEach-Object { $_.FullName.Substring($dist.Length + 1) }
Set-Content -Encoding utf8 (Join-Path $dist 'runtime\manifesto.txt') $todos
$maior = ($todos | Measure-Object -Property Length -Maximum).Maximum
Write-Host "    $($todos.Count) arquivos; maior caminho interno: $maior caracteres"

Write-Host "6/6 Compactando"
$zip = Join-Path $raiz "dist\$nome-Portatil.zip"
tar -a -c -f $zip -C (Join-Path $raiz 'dist') $nome
if ($LASTEXITCODE -ne 0) { throw 'falha ao compactar' }
"{0}  ({1:N0} MB)" -f $zip, ((Get-Item $zip).Length / 1MB)
