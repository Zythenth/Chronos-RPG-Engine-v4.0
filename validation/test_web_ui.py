import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_DIR = ROOT / "skills" / "web_ui"


class ChronosWebUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (UI_DIR / "index.html").read_text(encoding="utf-8")
        cls.css = (UI_DIR / "styles.css").read_text(encoding="utf-8")
        cls.javascript = (UI_DIR / "app.js").read_text(encoding="utf-8")

    def test_initial_markup_contains_no_campaign_or_reference_placeholders(self):
        forbidden = (
            "2142",
            "Kael",
            "Devorador de Fios",
            "Kit de Sobrevivência",
            "Rifle Gauss",
            '<canvas id="stars"',
            "[EMPRESA]",
            "A folhagem se abre",
            "O vulto entre as árvores",
            "gmResponses",
        )
        source = self.html + self.javascript
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, source)

        self.assertIn(r"C:\CHRONOS-7\SISTEMA&gt;", self.html)
        self.assertIn("const TERMINAL_NAMESPACE = 'CHRONOS-7';", self.javascript)

    def test_terminal_shell_keeps_navigation_and_command_accessible(self):
        required = (
            'href="#main-content"',
            'id="main-content"',
            'class="terminal-tabs" aria-label="Áreas do Chronos"',
            'id="nav-log"',
            'id="nav-dados"',
            'id="nav-codex"',
            'aria-current="page"',
            'class="window-controls" aria-hidden="true"',
            'id="system-status"',
            'role="status"',
            'id="log-announcer"',
            'for="command-input"',
            'aria-describedby="command-feedback"',
            'id="command-feedback"',
            '<dialog id="modal-levelup"',
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.html)

        forbidden = (
            'role="tablist"',
            'role="tab"',
            'role="tabpanel"',
            'class="chat-history" role="log"',
            'class="mobile-nav"',
            'class="app-sidebar"',
            'id="sidebar-toggle"',
            'id="command-submit"',
            'id="command-help"',
        )
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, self.html)

        self.assertEqual(self.html.count('class="tab-btn terminal-tab'), 3)
        controls_start = self.html.index('class="window-controls"')
        controls_end = self.html.index("</div>", controls_start)
        self.assertNotIn("<button", self.html[controls_start:controls_end])

    def test_log_places_scene_and_prompt_before_the_status_summary(self):
        log_start = self.html.index('id="tab-log"')
        log_end = self.html.index('id="tab-hud"')
        log_markup = self.html[log_start:log_end]

        self.assertLess(log_markup.index('class="terminal-banner"'), log_markup.index('class="chat-history"'))
        self.assertLess(log_markup.index('class="chat-history"'), log_markup.index('id="command-form"'))
        self.assertLess(log_markup.index('id="command-form"'), log_markup.index('class="log-hud-summary"'))
        self.assertEqual(log_markup.count('data-summary-vital="hp"'), 1)
        self.assertEqual(log_markup.count('data-summary-vital="energy"'), 1)
        self.assertNotIn('data-summary-vital="suit"', log_markup)
        self.assertNotIn('data-summary-vital="o2"', log_markup)
        self.assertEqual(log_markup.count('class="ascii-output"'), 2)
        self.assertNotIn('role="progressbar"', log_markup)
        self.assertIn("<dt>hud</dt>", log_markup)
        self.assertIn('id="summary-hud"', log_markup)
        self.assertIn("<dt>status</dt>", log_markup)
        self.assertNotIn("<dt>conexão</dt>", log_markup)

    def test_prompt_has_no_visual_box_or_send_button(self):
        required = (
            'id="command-prompt"',
            'class="command-line"',
            'class="cmd-input-field"',
            "autofocus",
            "caret-color: var(--terminal-text)",
            "background: transparent",
            "border: 0",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.html + self.css)

        field_start = self.css.index(".cmd-input-field {")
        field_end = self.css.index(".cmd-input-field:disabled", field_start)
        field_styles = self.css[field_start:field_end]
        self.assertNotIn("border-bottom", field_styles)
        self.assertNotIn('placeholder="Descreva a ação"', self.html)
        self.assertNotIn("cursor-blink", self.css)
        self.assertNotIn("@keyframes", self.css)

    def test_command_separates_narrative_suggestions_from_system_tools(self):
        required = (
            'id="narrative-actions"',
            'id="system-tools"',
            'class="utility-actions-container"',
            '[ações do sistema]',
        )
        source = self.html + self.javascript
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, source)
        self.assertNotIn("[Enter]", source)
        self.assertNotIn("Pressione Enter", source)

    def test_system_tools_are_immediately_below_the_full_hud_link(self):
        log_start = self.html.index('id="tab-log"')
        log_end = self.html.index('id="tab-hud"')
        log_markup = self.html[log_start:log_end]
        hud_link = '[abrir HUD completo]'
        hud_link_end = log_markup.index('</button>', log_markup.index(hud_link)) + len('</button>')
        system_tools_start = log_markup.index('<details id="system-tools"')

        self.assertLess(hud_link_end, system_tools_start)
        self.assertEqual(log_markup[hud_link_end:system_tools_start].strip(), "")

    def test_codex_search_keeps_a_gray_line_and_uses_the_native_caret(self):
        line_start = self.css.index(".codex-command-line {")
        line_end = self.css.index(".codex-search-input {", line_start)
        line_styles = self.css[line_start:line_end]

        self.assertIn("border-bottom: 1px solid var(--line-control)", line_styles)
        self.assertIn("--line-control: rgba(255, 255, 255, 0.42)", self.css)
        self.assertNotIn(".codex-command-line:focus-within", self.css)
        self.assertIn("caret-color: var(--terminal-text)", self.css)
        self.assertNotIn("cursor-blink", self.css)
        self.assertNotIn("@keyframes", self.css)

        navigation_start = self.javascript.index("document.querySelectorAll('.tab-btn, .view-switch')")
        navigation_end = self.javascript.index("// Chat e ciclo de turnos", navigation_start)
        navigation = self.javascript[navigation_start:navigation_end]
        self.assertIn("target === 'tab-codex'", navigation)
        self.assertIn("document.getElementById('codex-search')?.focus", navigation)

    def test_terminal_direction_is_monochrome_monospace_and_readable(self):
        required = (
            "--terminal-bg: #0c0c0c",
            "--terminal-text: #f2f2f2",
            '--font-terminal: "Cascadia Mono", "Cascadia Code", Consolas, "Space Mono", monospace',
            "font-size: 16px",
            "line-height: 1.55",
            "border-radius: 0",
            "@media (prefers-reduced-motion: reduce)",
            "@media (forced-colors: active)",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.css)

        forbidden = (
            "Orbitron",
            '"Crimson Pro"',
            '"JetBrains Mono"',
            "#00f5ff",
            "#00ffaa",
            "#67c5cc",
            "#d16c73",
            "#c39a5d",
            "rgba(0,245,255",
            "rgba(0, 245, 255",
            "text-shadow:",
        )
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, self.html + self.css + self.javascript)

    def test_terminal_supports_mobile_reflow_without_fixed_command_chrome(self):
        required = (
            "height: 100dvh",
            "overflow: auto",
            "@media (max-width: 820px)",
            "@media (max-width: 620px)",
            "@media (max-width: 390px)",
            "env(safe-area-inset-bottom)",
            "grid-template-columns: minmax(0, 1fr) 280px",
            "grid-template-columns: minmax(0, 1fr);",
            "padding: 20px 28px",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.css)

        self.assertNotIn("position: fixed;\n    z-index: 100;", self.css)
        self.assertNotIn("interaction-footer", self.html + self.css)
        self.assertNotIn("width: min(100%, 1220px)", self.css)
        self.assertIn("const command = document.getElementById('command-form');", self.javascript)
        self.assertNotIn("_chatViewport.scrollTop = _chatViewport.scrollHeight", self.javascript)

    def test_history_uses_bounded_chunks_and_loads_nearby_messages(self):
        required = (
            "const HISTORY_CHUNK_SIZE = 40;",
            "const HISTORY_DOM_LIMIT = 120;",
            "function renderHistoryWindow",
            "async function loadOlderHistory",
            "async function loadNewerHistory",
            "fetch(`/api/history?${params.toString()}`, { cache: 'no-store' })",
            "historyWindow.items.length > HISTORY_DOM_LIMIT",
            "focusDirection",
            "equivalentControl",
            "_chatViewport.addEventListener('scroll'",
            "[carregar mensagens anteriores]",
            "[carregar mensagens seguintes]",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.javascript)

        self.assertIn("state?.chat_history", self.javascript)
        self.assertIn("chat.appendChild(createChatMessage", self.javascript)

    def test_hud_complete_uses_the_terminal_type_scale(self):
        hud_start = self.css.index(".hud-detail {")
        hud_end = self.css.index("/* Dados e Codex", hud_start)
        hud_styles = self.css[hud_start:hud_end]

        self.assertIn("font-family: var(--font-terminal)", hud_styles)
        self.assertIn("font-size: 1rem", hud_styles)
        for selector in (
            ".content-header h2",
            ".section-kicker",
            ".hud-title",
            ".vital-label",
            ".hud-list",
        ):
            with self.subTest(selector=selector):
                selector_start = hud_styles.index(f"\n{selector} {{")
                selector_end = hud_styles.index("}", selector_start)
                self.assertIn("font-size: inherit", hud_styles[selector_start:selector_end])

    def test_roll_output_is_monochrome_for_empty_and_populated_states(self):
        roll_start = self.javascript.index("function renderRollSection")
        roll_end = self.javascript.index("function updateRoll", roll_start)
        roll_source = self.javascript[roll_start:roll_end]

        self.assertIn('class="roll-empty"', roll_source)
        self.assertIn('class="roll-result"', roll_source)
        for forbidden in (
            "0,245,255",
            "0, 245, 255",
            "var(--cyber-cyan)",
            "var(--cyber-green)",
            "var(--cyber-red)",
            "text-shadow",
            "statusColor",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, roll_source)

    def test_javascript_uses_real_status_terminal_prompts_and_ascii_vitals(self):
        required = (
            "function setSystemStatus",
            "function normalizeSearch",
            "function renderCodex",
            "codexSearch.addEventListener('input'",
            "let turnInFlight = false",
            "response.ok",
            "resultState?.ok === false",
            "modal.showModal()",
            "function announceLogUpdate",
            "function renderNarrativeState",
            "function deriveContextualState",
            "function terminalPrompt",
            "function setTerminalIdentity",
            "function asciiBar",
            "userInitiated",
            "replace(/^>\\s*COMANDO:\\s*/i, '')",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.javascript)

        forbidden = (
            "displayStages",
            "ATIRAR NO TERMINAL",
            "triggerGlitch",
            "warpStart",
            "querySelectorAll('[role=\"tablist\"]')",
            "Math.random()",
            "setTimeout(",
        )
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, self.javascript)

    def test_dados_is_structured_terminal_output_without_legacy_cards(self):
        required_markup = (
            'aria-labelledby="dados-title"',
            'id="dados-title"',
            'id="dados-status"',
            'id="dados-container"',
            'aria-busy="true"',
        )
        for value in required_markup:
            with self.subTest(value=value):
                self.assertIn(value, self.html)

        render_start = self.javascript.index("function renderDados")
        render_end = self.javascript.index("let codexEntries", render_start)
        render_source = self.javascript[render_start:render_end]
        ordered_sections = (
            '[ identificação ]',
            '[ estado geral ]',
            '[ atributos ]',
            '[ recursos ]',
            '[ habilidades ]',
            '[ inventário ]',
            '[ efeitos ativos ]',
        )
        positions = [render_source.index(section) for section in ordered_sections]
        self.assertEqual(positions, sorted(positions))
        for value in (
            '<table class="terminal-table attrs-table">',
            '<table class="terminal-table resource-table">',
            '<table class="terminal-table inventory-table">',
            'scope="col"',
            'scope="row"',
            'role="region" aria-label="Registros recentes do motor"',
        ):
            with self.subTest(value=value):
                self.assertIn(value, self.javascript)

        self.assertNotIn('style="', render_source)
        self.assertNotIn('rgba(255,170,0', self.javascript)
        self.assertNotIn('box-shadow:0 0 10px', self.javascript)
        self.assertIn("deriveContextualState(char, gameState.combat)", render_source)
        self.assertIn("'[ATENÇÃO]' : '[ESTÁVEL]'", render_source)
        self.assertIn('[ contexto atual ]', render_source)

    def test_dados_refreshes_the_complete_snapshot_after_a_turn(self):
        request_start = self.javascript.index("async function doAction")
        request_end = self.javascript.index("// 4. Modais", request_start)
        action_source = self.javascript[request_start:request_end]

        validation = action_source.index("resultState?.ok === false")
        data_refresh = action_source.index("renderDados(resultState.state, resultState.log)")
        codex_refresh = action_source.index("updateCodex(resultState.state.bestiary")
        self.assertGreater(data_refresh, validation)
        self.assertGreater(codex_refresh, data_refresh)

    def test_codex_uses_searchable_index_reader_and_bounded_pages(self):
        required_markup = (
            'aria-labelledby="codex-title"',
            'id="codex-search-form"',
            'role="search"',
            'for="codex-search"',
            'id="codex-clear-search"',
            'id="codex-results-status"',
            'id="codex-workspace"',
            'id="codex-index"',
            'aria-label="Índice do Codex"',
            'id="codex-reader"',
        )
        for value in required_markup:
            with self.subTest(value=value):
                self.assertIn(value, self.html)

        required_javascript = (
            "const CODEX_INDEX_PAGE_SIZE = 80;",
            "function selectCodexEntry",
            "function returnToCodexIndex",
            "data-codex-id",
            "aria-current",
            "ArrowDown",
            "ArrowUp",
            "event.key === 'Home'",
            "event.key === 'End'",
            "event.key === 'Escape'",
            "[SEM RESULTADO]",
            "[INDISPONÍVEL]",
            "codexAvailable ? '[VAZIO]",
        )
        for value in required_javascript:
            with self.subTest(value=value):
                self.assertIn(value, self.javascript)

        self.assertNotIn("codex-cards-grid", self.html + self.css + self.javascript)
        self.assertNotIn("codex-card", self.html + self.css + self.javascript)
        self.assertIn('.codex-workspace[data-view="index"] .codex-reader', self.css)
        self.assertIn('.codex-workspace[data-view="reader"] .codex-index', self.css)

    def test_dados_and_codex_define_reflow_focus_and_honest_states(self):
        required_css = (
            ".dados-layout {",
            "grid-template-columns: minmax(0, 1.55fr) minmax(300px, 0.8fr)",
            ".terminal-table-responsive .inventory-table",
            ".codex-command-line {",
            ".codex-index-entry[aria-current=\"true\"]",
            ".codex-search-input:focus-visible",
            "@media (max-width: 820px)",
            "@media (max-width: 620px)",
        )
        for value in required_css:
            with self.subTest(value=value):
                self.assertIn(value, self.css)

        self.assertIn("focusWasUntouched", self.javascript)
        self.assertIn("Os últimos dados válidos foram preservados", self.javascript)
        self.assertIn("[FALHA DE ATUALIZAÇÃO] Últimos registros válidos preservados.", self.javascript)
        self.assertIn("codexAvailable = meta?.available !== false", self.javascript)

        reader_handler = self.javascript[self.javascript.index("const codexReader"):]
        self.assertIn("if (event.key === 'Escape')", reader_handler)
        self.assertNotIn("matchMedia('(max-width: 700px)')", reader_handler)

    def test_hud_remains_reachable_without_becoming_a_fourth_top_tab(self):
        required = (
            'class="view-switch terminal-link"',
            'data-target="tab-hud"',
            'data-target="tab-log"',
            "const primaryTarget = tabName === 'tab-hud' ? 'tab-log' : tabName;",
            "document.querySelectorAll('.tab-btn, .view-switch')",
            "const isViewSwitch = event.currentTarget.classList.contains('view-switch');",
            "focusPanel: isViewSwitch && target !== 'tab-log'",
            "inputField.focus({ preventScroll: true })",
        )
        source = self.html + self.javascript
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, source)

        self.assertNotIn('class="tab-btn terminal-tab" type="button" aria-controls="tab-hud"', self.html)

    def test_javascript_keeps_failed_turn_out_of_the_narrative(self):
        request_start = self.javascript.index("async function doAction")
        request_end = self.javascript.index("// 4. Modais", request_start)
        action_source = self.javascript[request_start:request_end]

        history_refresh = action_source.index("renderNarrativeState({")
        response_validation = action_source.index("resultState?.ok === false")
        self.assertGreater(history_refresh, response_validation)
        self.assertNotIn("addMessage(normalizedText, 'player')", action_source)
        self.assertIn("inputField.value = normalizedText", action_source)
        self.assertIn("setAttribute('aria-invalid', 'true')", action_source)
        self.assertIn("turnError.inputInvalid", action_source)
        self.assertIn("else inputField.removeAttribute('aria-invalid')", action_source)
        self.assertIn("if (turnInFlight)", action_source)


if __name__ == "__main__":
    unittest.main()
