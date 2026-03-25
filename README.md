# ⏳ Chronos RPG Engine v4.0

> Um motor de RPG de texto baseado em navegador, focado em narrativas geradas por IA (Gemini API) com gerenciamento de estado complexo e separação estrita entre regras determinísticas e geração procedural.

O **Chronos** é um projeto em desenvolvimento contínuo (Work in Progress) que demonstra a integração de uma API de LLM (Large Language Model) em um fluxo de regras rígidas de RPG e sobrevivência (Hard Sci-Fi). O sistema garante que a matemática e as mecânicas do jogo rodem em Python puro, utilizando a Inteligência Artificial exclusivamente como Mestre de Jogo (Game Master) e gerador de conteúdo de fallback.

---

## 🏗️ Arquitetura e Fluxo do Sistema

O sistema foi desenhado com foco na **Separação de Responsabilidades (Separation of Concerns)**. O fluxo principal de um turno ocorre da seguinte forma:
`Frontend (index.html) -> web_server.py -> system_engine.py (Regras) -> game_master.py (IA Narradora) -> scene_processor.py (Extrator de Deltas) -> Atualização de Estado -> Frontend`

### 💻 Frontend & Servidor
* **`index.html`:** Interface visual do jogo (o "cockpit"). Exibe HP, Energy, vitais, inventário, a cena narrativa e as 3 opções de ação. O jogador interage visualmente, disparando o pipeline via fetch para a API.
* **`web_server.py`:** Servidor Flask e ponto de entrada da REST API. Orquestra o pipeline, faz snapshots de reversão antes de cada turno e detecta/trata erros 503 da API do Gemini.
* **`run_turn.py`:** Orquestrador CLI alternativo para rodar um turno completo via terminal, sem necessidade do navegador.

### ⚙️ Motor de Regras (Python Puro - Sem IA)
* **`system_engine.py`:** O motor mecânico central. Aplica as regras de survival decay, efeitos de status, combate, exploração, crafting, uso de itens, etc. Atualiza arquivos JSON/CSV e gera o relatório técnico para o GM.
* **`mechanics_engine.py`:** Biblioteca central de regras. Define tabelas e funções de cálculo (atributos, skills, XP, crafting, passivas). Não possui chamadas de IA nem IO de arquivo.
* **`architect.py`:** Guardião do estado e gestor de progressão. Gerencia level-up, inicia/encerra combates e aplica loot.
* **`loot_manager.py`:** Banco de dados do *schema* canônico de itens. Gerencia probabilidades de drop, tabelas de loot e serialização do inventário em CSV.
* **`world_state_ticker.py`:** Gerencia o ciclo orgânico do mundo a cada turno (fases do dia, clima dinâmico e nível de patrulhas).
* **`checkpoint_manager.py`:** Sistema de backup que salva snapshots completos do estado do jogo (10 arquivos) a cada 5 turnos, permitindo reversão e comparação (diff) de status.

### 🧠 Inteligência Artificial (Integração Gemini)
* **`game_master.py`:** O Narrador (Gemini 2.5 Pro). Lê o estado do mundo e injeta no prompt. Gera a cena narrativa e as 3 opções de ação. É a única tarefa puramente criativa; não aplica regras mecânicas.
* **`scene_processor.py`:** Extrator de deltas. Lê a cena e extrai alterações de vitais e itens (PARTE 4). Roda em Python puro no "caminho feliz" e chama o **Gemini 2.5 Flash** apenas como fallback para corrigir itens com schema inválido.
* **`lore_archivist.py`:** Arquivista de memória (Gemini 2.5 Flash). Lê a cena e extrai fatos para a persistência de longo prazo (Story Bible, NPCs, Bestiário, Quests), evitando duplicatas.
* **`expansion_manager.py`:** Criador dinâmico de conteúdo (Gemini 2.5 Flash). Acionado em rolagens de exploração altas (d20 ≥ 17) para gerar novos itens, criaturas ou NPCs dentro das regras de balanceamento (guardrails).
* **`arc_summarizer.py`:** Compressor de memória. Utiliza IA para comprimir eventos de um arco encerrado na Story Bible quando esta atinge limites de caracteres, preservando apenas momentos críticos.
* **`world_context_loader.py`:** Leitor e formatador de contexto narrativo. Prepara os blocos de texto injetados nos prompts do GM, controlando limites de tokens.

### 🎲 Rolagens e RNG
* **`d20.py` & `d4.py`:** Geradores de dados utilizando `secrets.choice` para aleatoriedade criptograficamente segura e sem viés.
* **`multi_roll.py`:** Ferramenta CLI para auditar e simular rolagens com sistemas de vantagem/desvantagem por atributo, espelhando o comportamento do motor central.

---

## 🚀 Roadmap e Desafios Atuais (Melhorias Futuras)

Este é um projeto vivo. Os próximos passos de desenvolvimento focam em estabilidade, resiliência e balanceamento:

* **Tratamento de Exceções da API:** Aprimorar o fallback para casos em que a API do Gemini sofra timeout ou retorne respostas fora do padrão, garantindo que o `web_server.py` reverta o estado graciosamente.
* **Testes de Estresse de JSON:** Melhorar a resiliência do `scene_processor.py` para lidar com JSONs malformados vindos da IA antes de acionar o reparo via Gemini Flash.
* **Balanceamento do Jogo (Playtesting):** Ajustar as tabelas de loot, dano e economia do jogo no `mechanics_engine.py` conforme o jogador progride.
* **Refatoração de Código:** Identificar e otimizar operações de leitura/escrita simultâneas em múltiplos arquivos JSON durante o ciclo de processamento do turno.

---

## 🛠️ Tecnologias Utilizadas

* **Linguagem Principal:** Python 3.14.3
* **Backend/API:** Flask
* **Frontend:** HTML5, CSS3, JavaScript (Vanilla, Fetch API)
* **Inteligência Artificial:** Google Gemini API (2.5 Pro e 2.5 Flash)
* **Armazenamento de Estado:** JSON e CSV manipulados em tempo de execução
