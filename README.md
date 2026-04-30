# Check Impressoras

Aplicativo local para consultar impressoras HP Laser MFP 432 na rede e centralizar as informacoes de **Cartucho de toner** e **Unidade de imagem** em uma tela unica.

O projeto foi criado para evitar a rotina manual de entrar IP por IP na pagina web de cada impressora.

## Funcionalidades

- Cadastro de impressoras por interface grafica.
- Campos de IP, setor e grupo.
- Separacao entre setores `Assistencial 24h` e `Administrativo`.
- Pesquisa automatica das impressoras pela rede local.
- Resultado exibido dentro do proprio app.
- Destaque por cor conforme nivel mais baixo entre toner e unidade de imagem.
- Exportacao para CSV, HTML e Excel formatado.
- Historico acumulado das pesquisas em CSV.
- Backup automatico da lista de impressoras antes de salvar alteracoes.
- Validacao para impedir IP invalido, duplicado ou fora da rede local.
- Compatibilidade com impressoras que redirecionam HTTP para HTTPS antigo.

## Regras de cor

| Cor | Condicao |
| --- | --- |
| Verde | 30% ou mais |
| Amarelo | 10% a 29% |
| Vermelho | 0% a 9% ou erro de acesso |

Linhas amarelas e vermelhas aparecem no topo de cada grupo para facilitar a priorizacao.

## Requisitos

- Windows.
- Python 3 instalado.
- Computador conectado na mesma rede das impressoras.
- Acesso web liberado para as impressoras.

Para verificar se o Python esta instalado:

```powershell
python --version
```

## Como usar

1. Abra `rodar_check.bat`.
2. Cadastre as impressoras na aba `Cadastro`.
3. Informe `IP`, `Setor` e `Grupo`.
4. Clique em `Adicionar`.
5. Clique em `Iniciar pesquisa`.
6. Veja o resultado na aba `Resultado da pesquisa`.

Para abrir com menos aparicao de terminal, use:

```txt
Abrir Check Impressoras.vbs
```

## Cadastro de impressoras

O app salva a lista no arquivo `ips.txt`.

Formato:

```txt
IP;Setor;Grupo
```

Exemplos:

```txt
192.168.1.15;NIR;Assistencial 24h
192.168.0.200;Financeiro;Administrativo
```

Se o grupo nao for informado, a impressora entra automaticamente como `Assistencial 24h`.

Exemplo valido:

```txt
192.168.1.15;NIR
```

## Relatorios gerados

Apos a pesquisa, o app gera:

| Arquivo | Uso |
| --- | --- |
| `relatorio_impressoras.html` | Relatorio para abrir no navegador |
| `relatorio_impressoras.csv` | Planilha simples, sem cores |
| `relatorio_impressoras.xlsx` | Planilha Excel formatada com cores |
| `historico_impressoras.csv` | Historico acumulado das pesquisas |

O resultado principal tambem aparece dentro da propria interface do app.

Na aba `Resultado da pesquisa`, de dois cliques em uma impressora para abrir a pagina web dela no navegador.

## Execucao pelo terminal

Tambem e possivel rodar a pesquisa sem abrir a interface:

```powershell
python .\check_impressoras.py
```

Para abrir a interface diretamente pelo Python:

```powershell
python .\check_impressoras_gui.py
```

## Como funciona

O app consulta os endpoints internos da pagina web da HP Laser MFP 432, principalmente:

```txt
/sws/app/information/home/home.json
/sws/app/information/supplies/supplies.json
```

Os campos usados sao:

| Informacao | Campo da impressora |
| --- | --- |
| Cartucho de toner | `toner_black.remaining` |
| Unidade de imagem | `drum_black.remaining` |

## Estrutura dos arquivos

```txt
check-impressoras/
|-- check_impressoras.py
|-- check_impressoras_gui.py
|-- ips.txt
|-- rodar_check.bat
|-- Abrir Check Impressoras.vbs
|-- relatorio_impressoras.html
|-- relatorio_impressoras.csv
|-- relatorio_impressoras.xlsx
|-- historico_impressoras.csv
|-- backups/
`-- README.md
```

## Observacoes

- O app precisa estar em uma maquina com acesso aos IPs das impressoras.
- Por seguranca, o cadastro aceita apenas IPv4 de rede local.
- Impressoras desligadas, lentas ou fora da rede aparecem em vermelho com erro no campo `Resultado`.
- CSV nao guarda cores; use o arquivo `.xlsx` para a versao mais apresentavel no Excel.
- A lista de IPs pode ser editada pela interface ou manualmente pelo `ips.txt`.
- Textos exportados para CSV/Excel sao tratados para evitar interpretacao indevida como formula.

## Status do projeto

Projeto em uso interno e em evolucao.

Melhorias futuras possiveis:

- Gerar instalador para Windows.
- Criar icone e atalho na area de trabalho.
- Adicionar historico semanal.
- Enviar alerta automatico quando algum item estiver amarelo ou vermelho.
