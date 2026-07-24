# Chronos RPG Engine

Chronos e um motor de RPG narrativo hard sci-fi com interface web local. O projeto combina regras deterministicas em Python, estado persistido em arquivos JSON/CSV/Markdown e geracao narrativa via Gemini. A IA narra e sugere opcoes; as consequencias mecanicas ficam sob responsabilidade dos scripts Python.

## Problema resolvido

RPGs narrativos com IA podem perder consistência quando o modelo também controla regras, estado e consequências. O Chronos separa essas responsabilidades: scripts Python determinísticos aplicam a mecânica e persistem o mundo, enquanto o Gemini fica restrito à narração e à sugestão de opções.

## Status atual

Protótipo funcional em desenvolvimento, executado localmente, com interface web, persistência em arquivos, integração com Gemini e testes de contrato. O projeto ainda não é um produto hospedado nem uma engine genérica pronta para distribuição.

## O que o projeto faz

- Mantem ficha, inventario, combate, mapa, clima, periodo e progresso do personagem.
- Executa turnos por uma pipeline de scripts: regras, ticker de mundo, geracao narrativa, processamento de deltas e arquivamento de lore.
- Exibe uma interface web local com HUD, narrativa, rolagens, inventario, mapa, missoes e acoes disponiveis.
- Persiste memoria de campanha em arquivos Markdown dentro de `world_context/`.

## Tecnologias utilizadas

- Python 3
- Flask para o servidor web local
- Google GenAI SDK para chamadas ao Gemini
- Pydantic como dependencia de apoio
- Frontend vanilla em HTML, CSS e JavaScript
- Persistencia em arquivos locais: JSON, CSV e Markdown

As dependencias Python estao em `requirements.txt`.

## Estrutura principal

```text
skills/
  web_server.py          Servidor Flask e orquestracao da interface
  system_engine.py       Regras mecanicas e efeitos de acoes
  game_master.py         Montagem de contexto e chamada narrativa ao Gemini
  scene_processor.py     Extrai deltas estruturados da cena gerada
  lore_archivist.py      Atualiza memoria e lore da campanha
  expansion_manager.py   Registra novas entidades e itens dinamicos
  loot_manager.py        Tabelas de loot e schema de itens
  world_context_loader.py Carregamento de lore/contexto para prompts
  web_ui/index.html      Estrutura da interface web
  web_ui/styles.css      Estilos visuais da interface
  web_ui/app.js          Logica frontend e chamadas da API

current_state/
  character_sheet.json   Ficha e progresso do personagem
  active_combat.json     Estado do combate atual
  chapter_tracker.json   Capitulo, clima, periodo e estado do mundo
  inventory.csv          Inventario
  world_map.json         Areas descobertas e pontos de interesse
  active_quests.md       Missoes ativas

world_context/
  world_bible.md         Premissa e regras do universo
  tone_guide.md          Tom narrativo
  story_bible.md         Memoria narrativa acumulada
  campaign_log.md        Diario de campanha
  npc_dossier.md         NPCs conhecidos
  bestiary.md            Criaturas e ameacas
  dynamic_items.json     Itens criados dinamicamente

validation/
  test_contracts.py      Testes de contrato do sistema
```

## Configuracao

1. Crie um ambiente virtual, se desejar.
2. Instale as dependencias:

```powershell
pip install -r requirements.txt
```

3. Crie um arquivo `.env` na raiz com sua chave:

```text
GEMINI_API_KEY=sua_chave_aqui
```

O arquivo `.env` deve permanecer fora do Git.

## Como rodar

Para iniciar a interface web local:

```powershell
py -B skills\web_server.py
```

Depois acesse:

```text
http://127.0.0.1:5000
```

Tambem e possivel ajustar host e porta com variaveis de ambiente:

```powershell
$env:CHRONOS_HOST="127.0.0.1"
$env:CHRONOS_PORT="5000"
py -B skills\web_server.py
```

## Validacao

Rodar os testes de contrato:

```powershell
py -B -m unittest validation.test_contracts
```

Checar sintaxe Python dos modulos principais:

```powershell
py -B -c "import ast, pathlib; files=list(pathlib.Path('skills').glob('*.py'))+list(pathlib.Path('validation').glob('*.py')); [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in files]; print('Python AST OK')"
```

Checar imports centrais:

```powershell
py -B -c "import sys; sys.path.insert(0, 'skills'); import loot_manager, expansion_manager, world_context_loader, game_master, web_server; print('Core imports OK')"
```

## Checkpoints e estado

`current_state/` continua sendo a fonte de verdade em arquivos JSON/CSV/Markdown. Para reduzir risco de corrupção entre arquivos, `checkpoint_manager.py` salva snapshots em duas fases:

- monta o checkpoint em um diretório temporário;
- copia arquivos críticos de `current_state/` e `world_context/`;
- gera `meta.json` com manifest, tamanho e SHA-256 de cada arquivo;
- promove o diretório para o checkpoint final somente depois que tudo foi gravado;
- restaura arquivos usando cópia temporária e `os.replace`.

`checkpoints/` é artefato local de execução e fica fora do Git.

## Fluxo de um turno

1. O frontend envia uma acao para `/api/turn`.
2. `web_server.py` valida o comando e bloqueia concorrencia de turno.
3. `system_engine.py` aplica regras mecanicas.
4. `world_state_ticker.py` atualiza clima, periodo e eventos.
5. `architect.py` valida estado, loot e level up.
6. `game_master.py` monta contexto e chama o Gemini.
7. `scene_processor.py` aplica deltas estruturados.
8. `lore_archivist.py` atualiza memoria e lore.
9. A interface recarrega estado, narrativa e opcoes.

## Cuidados de desenvolvimento

- Nao coloque chaves de API no Git.
- Prefira atualizar dados expansivos em JSON/Markdown em vez de editar codigo Python dinamicamente.
- Mantenha o servidor ligado apenas em `127.0.0.1`, salvo necessidade explicita.
- Antes de mudar regras centrais, rode os testes de contrato.
- Ao adicionar novos fluxos, registre pelo menos um teste em `validation/`.
- Nao versione `checkpoints/` nem rascunhos em `drafts/`; eles sao estado local de execucao.
