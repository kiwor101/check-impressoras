# Build e instalador

Este projeto pode ser empacotado como `.exe` para Windows usando PyInstaller.

## Gerar instalador

No PowerShell, dentro da pasta do projeto:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_installer.ps1 -Version "1.1.0"
```

O instalador sera gerado em:

```txt
release/
```

Exemplo:

```txt
release/Check-Impressoras-Setup-1.1.0-win-x64.exe
```

## O que o instalador faz

- Mostra uma tela de instalacao.
- Permite escolher a pasta de instalacao.
- Permite escolher se cria atalho `Check Impressoras` na Area de Trabalho.
- Permite escolher se cria atalho no Menu Iniciar.
- Usa o icone do aplicativo.
- Permite abrir o app ao final da instalacao.

## Dados e logs

Na maquina instalada, os dados ficam em:

```txt
%LOCALAPPDATA%\Check Impressoras
```

Essa pasta guarda:

- `ips.txt`
- `relatorio_impressoras.csv`
- `relatorio_impressoras.html`
- `relatorio_impressoras.xlsx`
- `historico_impressoras.csv`
- `check_impressoras.log`
- `backups/`

## Windows 32 e 64 bits

O executavel gerado pelo PyInstaller segue a arquitetura do Python usado no build.

- Python 64-bit gera instalador `win-x64`.
- Python 32-bit gera instalador `win-x86`.

Para gerar as duas versoes, rode o mesmo `build_installer.ps1` uma vez com Python 64-bit e outra vez com Python 32-bit.
