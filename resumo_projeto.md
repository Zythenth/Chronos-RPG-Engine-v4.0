# Resumo do Projeto

## 1. Estrutura Geral
- **`skills/` (.py):** Diretório contendo toda a lógica mecânica do motor, o orquestrador dos turnos e o servidor backend.
- **`skills/web_ui/` (.html, .js, .css):** Guarda o front-end, contido integralmente num único arquivo `index.html` injetado na raiz da rota web que carrega seu próprio CSS e JS.
- **`current_state/` (.json, .csv):** Mantém o estado não-narrativo do mundo/personagem salvo como tabelas `.csv` (inventário) e planilhas/dicionários `.json` (ficha, status, etc.).
- **`drafts/` (.md, .txt, .json):** Área rascunho. Guarda dados temporários que transitam entre scripts no mesmo frame de execução (ex: logs de batalha e arquivo RAW narrativo).
- **`world_context/` (.md):** Arquivos gerados por IA mantendo a longa continuidade (Lore/Memória).
- **`validation/` (.md):** Documentação super-restrita do arquiteto, guardando as regras definitivas de papéis GM x Scripts Python, Casos de Teste do código base, e regras de RPG pura.

## 2. index.html — Interface Atual
- **Layout Visual:** Um dashboard sci-fi cyberpunk denso. Apresenta fundo escuro, com overlays CRT de TV e background procedural de partículas em canvas.
- **Grid Lógico:** Painel esquerdo (`HUD`) para vitais de sobrevivência, status, progressão, inventário; e painel central com tabs de conteúdo (Narrativa da IA, Dados 3D de Rolagem, Quests).
- **Sistema de "3 Opções":** O painel de ação localiza-se na extremidade inferior direita. Há opções fixas de Sistema (Salvar Checkpoint), mecânicas (Explorar, Usar Cura), e interações dinâmicas criativas. A interface extrai os botões do back-end, exibe-os na tela e comanda um `doAction(opt)` quando o player dá clique ou toque.
- **Estado de Navegação:** Página única (SPA), com uma div com *overlay loader blocker* que impede duas ações consecutivas travando a tela com spinners visuais que exibem na string os processos do pipeline Python operando atrás (`["System Engine", "World Ticker", "GM", ...]`). 

## 3. Lógica e Dados
- **Dados:** Nada é pre-escrito em HTML ou banco (SQL). As props vem inteiramente preenchidas de forma dinâmica pelo arquivo backend e processadas via Fetch por `function loadState()`, parseadas baseadas nos `.json`. Variáveis mantidas ativas definem HUD Bars. 
- **Funções Principais no Frontend JS:** `updateHUD` processa mudanças de tamanho de barra progressiva e displays status textuais, `updateRoll` cria o visual dos lados recém testados pelo Python, `doAction` faz as requisições API trancando concorrências locais de envio, `switchTab` realiza trocas rápidas visuais.

## 4. Arquivos Python (.py)
- **`web_server.py`:** Servidor WSGI utilizando Micro-Framework **Flask**. Interage com o front, e controla a pipeline (travar Threads) e gerenciar endpoints como `/api/state` e POST `/api/turn`. Em `/turn`, ele empilha execuções em `subprocess`.
- **`run_turn.py`:** Simula um loop via terminal CLI igual ao Webserver ignorando o browser localmente.
- **Mecanismos Python Puros (Zero IA):** `system_engine.py`, `mechanics_engine.py` coordenam matemática e regras fixas sem API. Auxiliados via helpers `architect.py`, `d20.py`, `d4.py` e `multi_roll.py`. Tratam 100% da integridade ludo-narrativa e decaimentos por turno.
- **IA e Geradores (Gemini):** 
  - `game_master.py`: Mestre de jogo rolando llm criativo apenas focado na interpretação narradora com Gemini 2.5 Pro; Não resolve danos; apenas extrai a situação textualmente para o front, e propõe três ações ao usuário.
  - `scene_processor.py`, `lore_archivist.py`, e `expansion_manager.py`: Módulos suportivos para processar extrações de textos para os arquivos da engine e parsear strings narrativas complexas criando deltas limpos nos CSVs e gerindo memória contextual limitando uso da IA base onde não precisa de contexto gigante.

## 5. Documentação Markdown (.md)
- Estão em duas linhas do jogo: 
   - **Lores:** Fichas persistentes do andamento de um arco de longo prazo gerado por GenAI, salvando monstros e o estado social geral em `/world_context/*.md`.
   - **Regras:** Usadas como guide e prompt definitions para validações de código guardadas em arquivos de `validation/*`. Explicitam com extremismo regras de separação responsabilidade GM-Engine ou pipeline end-to-end do server.

## 6. Estilo e Tema Visual
- **Tema:** Dark-Mode de interfaces industriais. Sombras e glows de painel neon (`text-shadow: 0 0 8px...`).
- **Paleta de Cores:** Fundo Preto azulado (`#02040a`). Detalhes em ciano/Holo (`#00e5ff`) e subtons azul neon, verde sucesso (`#00ff88`) e sinais críticos avermelhados vermelhos (`#ff2244`). 
- **Fontes Base:** Encoraja estilo hacker com `Share Tech Mono` (infos periféricas e miúdas), `Orbitron` (numéricos bold/titulos), e familia `Inter` para leitura longa da narrativa da IA de forma humana.
- **Framework:** **Nenhum**. Layout montado 100% a mão e sem uso de TailwindCSS/Bootstrap baseados puramente em Flex/Grid Vanilla local e variáveis estáticas `:root`.

## 7. Dependências Externas
- **Bibliotecas JS:** Nenhuma biblioteca de terceiros (jQuery, React, etc.). Tudo manipulação DOM API e CSS hardcoded nativos.
- **Assets e APIs Web Externas:** Nenhuma biblioteca web sendo importada exceto fonte do Google (`https://fonts.googleapis.com`).
- **Python / APIs:** Flask no Servidor Web; SDK Padrão Core; e a API do **Gemini via framework Google/GenAI**.

## 8. Pontos de Integração para o Chatbot
- **Áreas Operacionais pelo Usuário:** Apenas os cliques nos botões do Grid (`O Que Você Faz?`) com chamadas limitadas via `.opt-btn` que ativam callback function com object data. Alem desses, há interações por interface modais para atributos ou passivas de Nivel (`confirmSkills`), que chamam suas proprias APIs e desmarcam as divs hidden.
- **Atrelamento do Chatbot:** Todo o ciclo de narrativa atualiza o bloco #narr-text do DOM por `setNarrative`. Não há chat interativo onde o usuário "digita" no formato ChatGPT cru, o usuário decide as opções da engine clicando em ações processadas pelas scripts, logo após o Gemini interage gerando as narrativas passivas das escolhas e definindo os rumos em resposta passivas preenchendo deltas json sem o usuário encostar em form inputs livres.
