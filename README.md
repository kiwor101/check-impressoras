# Check Impressoras

App simples para verificar semanalmente toner e unidade de imagem das impressoras HP Laser MFP 432 pela pagina web interna.

## Como usar

1. Abra `rodar_check.bat` para iniciar a tela do sistema.
2. Cadastre IP, setor e grupo pela janela.
3. Clique em `Iniciar pesquisa`.
4. Veja o resultado na aba `Resultado da pesquisa`.

Para abrir sem nenhuma janela preta piscando, use `Abrir Check Impressoras.vbs`.

O arquivo `ips.txt` continua existindo como base de dados simples. O formato dele e:

```txt
IP;Setor;Grupo
```

Tambem da para executar pelo terminal, se precisar:

```powershell
python .\check_impressoras.py
```

Depois da verificacao, abra:

- A aba `Resultado da pesquisa` para ver a tabela dentro do app.
- `relatorio_impressoras.csv` para abrir no Excel em formato simples.
- `relatorio_impressoras.xlsx` para abrir no Excel com cores e tabelas separadas.

## Observacoes

- O computador precisa estar na mesma rede das impressoras.
- O grupo pode ser `Assistencial 24h` ou `Administrativo`.
- Se a linha tiver apenas `IP;Setor`, ela entra automaticamente em `Assistencial 24h`.
- O setor aparece no HTML e no CSV, junto do `Cartucho de toner` e da `Unidade de imagem`.
- As linhas ficam verdes acima de 30%, amarelas de 10% a 29% e vermelhas de 0% a 9% ou quando houver erro de acesso.
- As linhas vermelhas e amarelas aparecem no topo de cada grupo.
- CSV nao guarda cores; use o arquivo `.xlsx` para ver a formatacao completa no Excel.
- A primeira versao le a pagina inicial da impressora, como `http://IP/sws/index.html`.
- O acesso e feito por HTTP simples para evitar erro de HTTPS antigo em algumas impressoras.
- Se alguma impressora exigir login ou mudar o texto da pagina, ela pode aparecer como erro no relatorio.
- Para automatizar semanalmente, este script pode ser colocado no Agendador de Tarefas do Windows.
