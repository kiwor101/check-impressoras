# Check Impressoras

Aplicativo Windows para consultar impressoras **HP Laser MFP 432** na rede e exibir, em uma unica tela, os niveis de:

- Cartucho de toner
- Unidade de imagem

O objetivo do projeto e eliminar a rotina manual de abrir a pagina web de cada impressora IP por IP.

## Status

**Projeto encerrado.**

Versao final entregue: **1.1.0**

Instalador final:

```txt
release/Check-Impressoras-Setup-1.1.0-win-x64.exe
```

## Principais recursos

- Interface grafica para cadastro de impressoras.
- Cadastro por IP, setor e grupo.
- Separacao entre `Assistencial 24h` e `Administrativo`.
- Importacao e exportacao da lista de IPs.
- Pesquisa automatica na rede local.
- Resultado exibido dentro do proprio app.
- Relatorios em HTML, CSV e Excel formatado.
- Historico acumulado das pesquisas.
- Backup automatico da lista de impressoras.
- Validacao de IP local e bloqueio de duplicados.
- Instalador Windows com tela de instalacao.
- Atalho `Check Impressoras` na Area de Trabalho e/ou Menu Iniciar.
- Icone proprio do aplicativo.

## Regras de prioridade

O app usa o menor valor entre toner e unidade de imagem para definir a cor da linha.

| Cor | Condicao |
| --- | --- |
| Verde | 30% ou mais |
| Amarelo | 10% a 29% |
| Vermelho | 0% a 9% ou erro de acesso |

Linhas amarelas e vermelhas aparecem no topo de cada grupo.

## Instalacao

Use o instalador:

```txt
release/Check-Impressoras-Setup-1.1.0-win-x64.exe
```

Durante a instalacao, o usuario pode escolher:

- Pasta de instalacao.
- Criar atalho na Area de Trabalho.
- Criar atalho no Menu Iniciar.
- Abrir o app ao finalizar.

O usuario final nao precisa instalar Python.

## Uso

1. Abra o atalho `Check Impressoras`.
2. Va ate a aba `Cadastro`.
3. Informe `IP`, `Setor` e `Grupo`.
4. Clique em `Adicionar`.
5. Clique em `Iniciar pesquisa`.
6. Veja os resultados na aba `Resultado da pesquisa`.

Na aba de resultados, dois cliques em uma impressora abrem a pagina web dela no navegador.

## Importar e exportar lista

A lista pode ser importada/exportada pela interface.

Formato aceito:

```txt
IP;Setor;Grupo
```

Exemplo:

```txt
192.168.1.15;NIR;Assistencial 24h
192.168.0.200;Financeiro;Administrativo
```

Se o grupo nao for informado, o app considera `Assistencial 24h`.

## Dados gerados

Em uma instalacao normal, os dados ficam em:

```txt
%LOCALAPPDATA%\Check Impressoras
```

Arquivos gerados:

| Arquivo | Uso |
| --- | --- |
| `ips.txt` | Lista cadastrada de impressoras |
| `relatorio_impressoras.html` | Relatorio em navegador |
| `relatorio_impressoras.csv` | Planilha simples |
| `relatorio_impressoras.xlsx` | Planilha Excel formatada |
| `historico_impressoras.csv` | Historico acumulado |
| `check_impressoras.log` | Log de execucao |
| `backups/` | Backups automaticos do cadastro |

## Como funciona

O app consulta endpoints internos da pagina web da impressora:

```txt
/sws/app/information/home/home.json
/sws/app/information/supplies/supplies.json
```

Campos utilizados:

| Informacao | Campo |
| --- | --- |
| Cartucho de toner | `toner_black.remaining` |
| Unidade de imagem | `drum_black.remaining` |

## Seguranca

- Aceita apenas IPv4 de rede local.
- Bloqueia IP duplicado no cadastro.
- Limita o tamanho da resposta recebida da impressora.
- Trata textos exportados para CSV/Excel para evitar interpretacao como formula.
- Dados e logs ficam no perfil local do usuario.

## Desenvolvimento

Para rodar pelo codigo-fonte:

```powershell
python .\check_impressoras_gui.py
```

Para rodar a pesquisa sem interface:

```powershell
python .\check_impressoras.py
```

Para gerar o instalador:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_installer.ps1 -Version "1.1.0"
```

Mais detalhes em:

```txt
BUILD.md
```

## Windows 32 e 64 bits

O instalador atual foi gerado para Windows 64 bits:

```txt
Check-Impressoras-Setup-1.1.0-win-x64.exe
```

Para gerar uma versao 32 bits, execute o build usando Python 32-bit. O script gera automaticamente o sufixo `win-x86`.

## Estrutura

```txt
check-impressoras/
|-- check_impressoras.py
|-- check_impressoras_gui.py
|-- app_icon.ico
|-- build_installer.ps1
|-- BUILD.md
|-- installer/
|-- release/
|-- ips.txt
|-- rodar_check.bat
`-- README.md
```

## Encerramento

Projeto finalizado com instalador funcional, interface grafica, importacao/exportacao de lista, relatorios, historico, logs e validacoes de seguranca.
