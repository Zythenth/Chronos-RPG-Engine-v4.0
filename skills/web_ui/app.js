// ---------------------------------------------------------
// FUNÇÕES DE ESTADO E HUD
// ---------------------------------------------------------

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatLimitedMarkdown(value) {
    return escapeHtml(value)
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
}

function clearElement(el) {
    if (!el) return;
    while (el.firstChild) el.removeChild(el.firstChild);
}

function makeEl(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
}

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
let hasTrustedContent = false;
let stateLoadFailed = false;
const TERMINAL_NAMESPACE = 'CHRONOS-7';
let terminalCharacter = 'FERRO';
const HISTORY_CHUNK_SIZE = 40;
const HISTORY_DOM_LIMIT = 120;
const historyWindow = {
    items: [],
    start: 0,
    total: 0,
    loading: false,
    failedDirection: null,
    fallbackNarrative: ''
};

function normalizeTerminalActor(value, fallback) {
    const normalized = String(value || fallback || '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLocaleUpperCase('pt-BR')
        .replace(/[^A-Z0-9_-]+/g, '_')
        .replace(/^_+|_+$/g, '');
    return normalized || fallback;
}

function terminalPrompt(actor) {
    return `C:\\${TERMINAL_NAMESPACE}\\${normalizeTerminalActor(actor, 'SISTEMA')}>`;
}

function setTerminalIdentity(name) {
    terminalCharacter = normalizeTerminalActor(name, 'FERRO');
    const prompt = document.getElementById('command-prompt');
    if (prompt) prompt.textContent = terminalPrompt(terminalCharacter);
}

function formatTerminalLevel(value) {
    const level = Number(value);
    return Number.isFinite(level) ? `nv.${String(Math.max(0, level)).padStart(2, '0')}` : 'nv.—';
}

function formatTerminalCoordinate(name, value) {
    if (name === 'chapter' || name === 'turn') {
        const numeric = Number(value);
        if (Number.isFinite(numeric)) {
            return String(Math.max(0, Math.trunc(numeric))).padStart(2, '0');
        }
    }
    if (name === 'sector') return String(value).toLocaleLowerCase('pt-BR');
    return String(value);
}

function setCoordinate(name, value) {
    document.querySelectorAll(`[data-coordinate="${name}"]`).forEach(element => {
        const available = value !== undefined && value !== null && String(value).trim() !== '' && String(value) !== '—';
        element.textContent = available ? formatTerminalCoordinate(name, value) : '—';
        const contextItem = element.closest('.context-item');
        if (contextItem) contextItem.hidden = !available;
    });
}

function updateCoordinates(chapter, sector, turn, coordinates = null) {
    setCoordinate('chapter', chapter);
    setCoordinate('sector', sector);
    setCoordinate('turn', turn);
    setCoordinate('coordinates', coordinates);
}

function setConnectionState(state, label) {
    const wrapper = document.querySelector('.connection-state');
    const text = document.getElementById('connection-label');
    if (wrapper) wrapper.dataset.connectionState = state;
    if (text) text.textContent = label;
}

const statusCodes = {
    loading: '[SYNC]',
    processing: '[PROC]',
    success: '[OK]',
    error: '[ERRO]'
};

function setSystemStatus(state, message, options = {}) {
    const region = document.getElementById('system-status');
    const code = region?.querySelector('.status-code');
    const text = document.getElementById('system-status-message');
    const retry = document.getElementById('retry-state');
    if (!region || !text) return;

    region.dataset.state = state;
    region.classList.toggle('is-quiet', Boolean(options.quiet));
    if (code) code.textContent = statusCodes[state] || '[SYS]';
    text.textContent = message;
    if (retry) retry.hidden = !options.retry;
}

function announceLogUpdate(message) {
    const announcer = document.getElementById('log-announcer');
    if (!announcer) return;
    announcer.textContent = '';
    window.requestAnimationFrame(() => {
        announcer.textContent = message;
    });
}

function createChatMessage(role, text) {
    const normalizedRole = role === 'gm' || role === 'player' ? role : 'system-error';
    const message = makeEl('div', `chat-msg ${normalizedRole}`);
    const actor = normalizedRole === 'gm'
        ? 'GM'
        : (normalizedRole === 'player' ? terminalCharacter : 'SISTEMA');
    const actorLabel = normalizedRole === 'gm'
        ? 'GM'
        : (normalizedRole === 'player' ? terminalCharacter : 'Sistema');
    const prompt = makeEl('span', 'terminal-line-prompt', terminalPrompt(actor));
    prompt.setAttribute('aria-label', `${actorLabel}:`);
    const body = makeEl('span', 'terminal-line-text');

    if (normalizedRole === 'gm') {
        body.innerHTML = formatLimitedMarkdown(text);
    } else if (normalizedRole === 'player') {
        body.textContent = String(text || '').replace(/^>\s*COMANDO:\s*/i, '');
    } else {
        body.textContent = text;
    }

    message.appendChild(prompt);
    message.appendChild(body);
    return message;
}

function campaignNotStarted(text) {
    return /campanha ainda n[aã]o iniciada/i.test(String(text || ''));
}

function normalizeHistoryPage(history, page) {
    const sourceItems = Array.isArray(history) ? history : [];
    const reportedTotal = Number.isInteger(page?.total) ? page.total : sourceItems.length;
    const total = Math.max(reportedTotal, sourceItems.length, 0);
    const defaultStart = Math.max(0, total - sourceItems.length);
    const reportedStart = Number.isInteger(page?.start) ? page.start : defaultStart;
    const start = Math.min(Math.max(reportedStart, 0), total);
    const items = sourceItems.slice(0, Math.max(0, total - start));
    return { items, start, end: start + items.length, total };
}

function createHistoryLoadControl(direction) {
    const older = direction === 'older';
    const label = older
        ? '[carregar mensagens anteriores]'
        : '[carregar mensagens seguintes]';
    const button = makeEl('button', 'history-load terminal-link', label);
    button.type = 'button';
    button.dataset.historyDirection = direction;
    button.setAttribute(
        'aria-label',
        older ? 'Carregar mensagens anteriores do Log' : 'Carregar mensagens seguintes do Log'
    );
    button.addEventListener('click', () => {
        if (older) loadOlderHistory({ userInitiated: true });
        else loadNewerHistory({ userInitiated: true });
    });
    return button;
}

function renderHistoryWindow(options = {}) {
    const chat = document.querySelector('.chat-history');
    if (!chat) return;

    clearElement(chat);
    const hasHistory = historyWindow.items.length > 0;

    if (hasHistory) {
        if (historyWindow.start > 0) chat.appendChild(createHistoryLoadControl('older'));
        historyWindow.items.forEach((message, offset) => {
            if (!message || typeof message !== 'object') return;
            const element = createChatMessage(message.role, message.text || '');
            element.dataset.historyIndex = String(historyWindow.start + offset);
            chat.appendChild(element);
        });
        if (historyWindow.start + historyWindow.items.length < historyWindow.total) {
            chat.appendChild(createHistoryLoadControl('newer'));
        }
        chat.classList.remove('is-empty');
    } else if (historyWindow.fallbackNarrative && !campaignNotStarted(historyWindow.fallbackNarrative)) {
        chat.appendChild(createChatMessage('gm', historyWindow.fallbackNarrative));
        chat.classList.remove('is-empty');
    } else {
        const empty = createChatMessage(
            'system-error',
            'Campanha ainda não iniciada.'
        );
        empty.classList.add('narrative-empty');
        chat.appendChild(empty);
        chat.classList.add('is-empty');
    }

    chat.setAttribute('aria-busy', 'false');
    if (options.scrollToBottom) scrollToBottom(true);

    if (options.anchor || Number.isInteger(options.focusIndex) || options.focusDirection) {
        window.requestAnimationFrame(() => {
            if (options.anchor && _chatViewport) {
                const anchor = chat.querySelector(`[data-history-index="${options.anchor.index}"]`);
                if (anchor) {
                    const shift = anchor.getBoundingClientRect().top - options.anchor.top;
                    _chatViewport.scrollTop += shift;
                }
            }
            if (Number.isInteger(options.focusIndex)) {
                const focusTarget = chat.querySelector(`[data-history-index="${options.focusIndex}"]`);
                if (focusTarget) {
                    focusTarget.setAttribute('tabindex', '-1');
                    focusTarget.focus({ preventScroll: true });
                    focusTarget.addEventListener('blur', () => focusTarget.removeAttribute('tabindex'), { once: true });
                }
            } else if (options.focusDirection) {
                const equivalentControl = chat.querySelector(`[data-history-direction="${options.focusDirection}"]`);
                const fallbackIndex = options.anchor?.index;
                const fallbackMessage = Number.isInteger(fallbackIndex)
                    ? chat.querySelector(`[data-history-index="${fallbackIndex}"]`)
                    : null;
                const focusTarget = equivalentControl || fallbackMessage;
                if (focusTarget) {
                    if (!equivalentControl) focusTarget.setAttribute('tabindex', '-1');
                    focusTarget.focus({ preventScroll: true });
                    if (!equivalentControl) {
                        focusTarget.addEventListener('blur', () => focusTarget.removeAttribute('tabindex'), { once: true });
                    }
                }
            }
        });
    }
}

function renderNarrativeState(state, options = {}) {
    const page = normalizeHistoryPage(state?.chat_history, state?.chat_history_page);
    historyWindow.items = page.items;
    historyWindow.start = page.start;
    historyWindow.total = page.total;
    historyWindow.loading = false;
    historyWindow.failedDirection = null;
    historyWindow.fallbackNarrative = String(state?.narrative || '').trim();

    renderHistoryWindow({ scrollToBottom: true });
    if (!options.silent) announceLogUpdate(page.items.length > 0 ? 'Histórico atualizado.' : 'Cena atualizada.');
}

function renderNarrativeUnavailable(message) {
    const chat = document.querySelector('.chat-history');
    if (!chat) return;
    historyWindow.items = [];
    historyWindow.start = 0;
    historyWindow.total = 0;
    historyWindow.loading = false;
    historyWindow.failedDirection = null;
    historyWindow.fallbackNarrative = '';
    clearElement(chat);
    chat.classList.add('is-empty');
    chat.setAttribute('aria-busy', 'false');
    chat.appendChild(createChatMessage('system-error', message));
}

function clearActionControls() {
    const narrativeActions = document.getElementById('narrative-actions');
    const narrative = document.querySelector('.action-chips-container');
    const utilities = document.querySelector('.utility-actions-container');
    const utilityRegion = document.getElementById('system-tools');
    if (narrative) clearElement(narrative);
    if (utilities) clearElement(utilities);
    if (narrativeActions) narrativeActions.hidden = true;
    if (utilityRegion) utilityRegion.hidden = true;
}


// 4. Integração de Estado (GET /api/state)
async function loadState(options = {}) {
    const userInitiated = Boolean(options.userInitiated);
    const focusBeforeLoad = document.activeElement;
    const chat = document.querySelector('.chat-history');
    const statusRegion = document.getElementById('system-status');
    const retry = document.getElementById('retry-state');
    if (userInitiated && retry === document.activeElement && statusRegion) statusRegion.focus();
    setSystemStatus('loading', 'Sincronizando o estado local da campanha…');
    setConnectionState('loading', 'sincronizando');
    setControlsDisabled(true);
    if (chat) chat.setAttribute('aria-busy', 'true');
    const dataPanel = document.getElementById('dados-container');
    const dataStatus = document.getElementById('dados-status');
    const codexWorkspace = document.getElementById('codex-workspace');
    const codexStatus = document.getElementById('codex-results-status');
    if (dataPanel) dataPanel.setAttribute('aria-busy', 'true');
    if (dataStatus) dataStatus.textContent = 'Sincronizando dados do personagem…';
    if (codexWorkspace) codexWorkspace.setAttribute('aria-busy', 'true');
    if (codexStatus) codexStatus.textContent = 'Sincronizando registros…';

    try {
        let response;
        try {
            response = await fetch('/api/state');
        } catch (_error) {
            throw new Error('O servidor local não respondeu.');
        }

        let state;
        try {
            state = await response.json();
        } catch (_error) {
            throw new Error(`O servidor retornou uma resposta inválida (${response.status}).`);
        }
        if (!response.ok) {
            throw new Error(state?.message || `O estado local não pôde ser lido (${response.status}).`);
        }

        const loadedCharacter = state.state?.character;
        setTerminalIdentity(loadedCharacter?.name);
        renderNarrativeState(state, { silent: true });

        // Popula barras e Status do HUD
        if (state.state && state.state.character) {
            updateHUD(state.state.character, state.state.inventory, state.state.combat);
            if (state.state.character.level_up_pending || state.state.character.skill_pending) {
                confirmSkills(state.state.character);
            } else {
                closeLevelUpModal({ resolved: true });
            }

            renderDados(state.state, state.log);
        }

        // Coordenadas via Chapter Tracker
        if (state.state && state.state.world) {
            updateCoordinates(
                state.state.world.capitulo ?? '—',
                state.state.world.ambiente ?? '—',
                state.state.world.interacoes ?? '—'
            );
        }

        // Action Chips de narrativa
        renderChips(Array.isArray(state.options) ? state.options : []);

        // Codex Data
        if (state.state) updateCodex(state.state.bestiary, state.state.npc_dossier, state.state.codex_meta);

        const character = state.state?.character;
        const name = document.getElementById('summary-character-name');
        const level = document.getElementById('summary-level');
        if (name) name.textContent = character?.name || '—';
        if (level) level.textContent = formatTerminalLevel(character?.level);

        const recovered = stateLoadFailed;
        hasTrustedContent = true;
        stateLoadFailed = false;
        setSystemStatus(
            'success',
            recovered ? 'Conexão recuperada. O estado local foi atualizado.' : 'Estado local sincronizado.',
            { quiet: !recovered && !userInitiated }
        );
        setConnectionState('ready', 'estável');
        const modal = document.getElementById('modal-levelup');
        setControlsDisabled(Boolean(modal?.open));
        const focusWasUntouched = focusBeforeLoad === document.body
            || focusBeforeLoad === document.documentElement
            || focusBeforeLoad === retry
            || focusBeforeLoad === statusRegion;
        if (!modal?.open && focusWasUntouched && (userInitiated || document.activeElement === document.body)) {
            document.getElementById('command-input')?.focus({ preventScroll: true });
        }

    } catch (error) {
        console.error("Erro na API:", error);
        stateLoadFailed = true;
        const cause = error?.message || 'Falha ao carregar o estado local.';
        if (hasTrustedContent) {
            if (chat) chat.setAttribute('aria-busy', 'false');
        } else {
            renderNarrativeUnavailable('Não foi possível carregar a campanha. Nenhum dado local foi apresentado como válido.');
            resetHUD();
            updateCoordinates(null, null, null);
            renderCodexUnavailable('Codex indisponível enquanto o motor local não responder.');
            if (dataPanel) {
                dataPanel.className = 'terminal-empty';
                dataPanel.setAttribute('aria-busy', 'false');
                dataPanel.innerHTML = '<p>[ERRO] Dados indisponíveis enquanto o motor local não responder.</p>';
            }
            if (dataStatus) dataStatus.textContent = 'Dados indisponíveis.';
        }
        if (hasTrustedContent) {
            if (dataPanel) dataPanel.setAttribute('aria-busy', 'false');
            if (codexWorkspace) codexWorkspace.setAttribute('aria-busy', 'false');
            if (dataStatus) dataStatus.textContent = 'Falha ao atualizar. Os últimos dados válidos foram preservados.';
            if (codexStatus) codexStatus.textContent = '[FALHA DE ATUALIZAÇÃO] Últimos registros válidos preservados.';
        }
        clearActionControls();
        const preservation = hasTrustedContent
            ? ' A cena já carregada foi preservada; novos comandos permanecem bloqueados.'
            : ' Nenhum dado foi tratado como válido.';
        setSystemStatus('error', `${cause}${preservation}`, { retry: true });
        setConnectionState('error', 'indisponível');
        setControlsDisabled(true);
        if (userInitiated) window.requestAnimationFrame(() => document.getElementById('retry-state')?.focus());
    }
}

function hasDataValue(value) {
    return value !== undefined && value !== null && String(value).trim() !== '';
}

function terminalDataValue(value, suffix = '') {
    return hasDataValue(value) ? `${escapeHtml(value)}${suffix}` : '—';
}

function terminalEquipmentValue(value) {
    const normalized = String(value ?? '').trim().toLocaleLowerCase('pt-BR');
    return !normalized || normalized === 'none' || normalized === 'null' ? '—' : escapeHtml(value);
}

function renderResourceRow(label, value, max = 100, suffix = '%') {
    if (!hasDataValue(value)) {
        return `<tr><th scope="row">${escapeHtml(label)}</th><td>—</td><td>indisponível</td></tr>`;
    }
    const numericValue = Number(value);
    const numericMax = Number(max);
    const validMax = Number.isFinite(numericMax) && numericMax > 0 ? numericMax : 100;
    const percent = Number.isFinite(numericValue) ? Math.max(0, Math.min(100, (numericValue / validMax) * 100)) : 0;
    const visibleValue = suffix === '/' ? `${escapeHtml(value)}/${escapeHtml(max)}` : `${escapeHtml(value)}${suffix}`;
    const accessibleValue = suffix === '/' ? `${escapeHtml(value)} de ${escapeHtml(max)}` : visibleValue;
    return `<tr>
        <th scope="row">${escapeHtml(label)}</th>
        <td>${visibleValue}</td>
        <td><span class="ascii-output" aria-hidden="true">${asciiBar(percent, 10)}</span><span class="sr-only">${accessibleValue}</span></td>
    </tr>`;
}

function renderTerminalList(items, emptyMessage, formatter) {
    if (!Array.isArray(items) || !items.length) {
        return `<li class="terminal-list-empty">${escapeHtml(emptyMessage)}</li>`;
    }
    return items.map((item, index) => `<li>${formatter(item, index)}</li>`).join('');
}

function renderInventoryRows(inventory) {
    if (!Array.isArray(inventory) || !inventory.length) {
        return '<tr class="terminal-table-empty"><td colspan="5">Inventário vazio.</td></tr>';
    }
    return inventory.map(item => {
        const durability = hasDataValue(item?.durability)
            ? `${escapeHtml(item.durability)}/${terminalDataValue(item.dur_max)}`
            : '—';
        return `<tr>
            <th scope="row" data-label="item">${terminalDataValue(item?.name)}</th>
            <td data-label="qtd.">${terminalDataValue(item?.qty)}</td>
            <td data-label="tipo">${terminalDataValue(item?.type)}</td>
            <td data-label="dur.">${durability}</td>
            <td data-label="efeito">${terminalDataValue(item?.effect)}</td>
        </tr>`;
    }).join('');
}

function renderWorldSection(mapa, quests) {
    const areas = Array.isArray(mapa) ? mapa : [];
    const questList = Array.isArray(quests) ? quests : [];
    const areasHtml = renderTerminalList(
        areas,
        'Nenhuma área descoberta.',
        area => {
            const name = area?.nome || area?.id || 'Área sem nome';
            const status = area?.status ? ` — ${escapeHtml(area.status)}` : '';
            const notes = area?.notas ? `<span class="terminal-list-note">${escapeHtml(area.notas)}</span>` : '';
            return `<strong>${escapeHtml(name)}</strong>${status}${notes}`;
        }
    );
    const questsHtml = renderTerminalList(
        questList,
        'Nenhuma missão ativa rastreada.',
        quest => {
            const objectives = renderTerminalList(
                quest?.objetivos,
                'Sem objetivos rastreados.',
                objective => `${objective?.feito ? '[x]' : '[ ]'} ${terminalDataValue(objective?.texto)}`
            );
            return `<strong>[${terminalDataValue(quest?.tipo)}] ${terminalDataValue(quest?.nome)}</strong>
                <ul class="terminal-list terminal-objective-list">${objectives}</ul>`;
        }
    );
    return `<details class="terminal-disclosure">
        <summary>[mundo, mapa e missões] ${areas.length} área(s) · ${questList.length} missão(ões)</summary>
        <div class="terminal-disclosure-body dados-world-grid">
            <section aria-labelledby="dados-map-title">
                <h4 id="dados-map-title">Áreas descobertas</h4>
                <ul class="terminal-list">${areasHtml}</ul>
            </section>
            <section aria-labelledby="dados-quests-title">
                <h4 id="dados-quests-title">Missões ativas</h4>
                <ul class="terminal-list terminal-quest-list">${questsHtml}</ul>
            </section>
        </div>
    </details>`;
}

function renderDados(gameState, engineLog = []) {
    const container = document.getElementById('dados-container');
    const status = document.getElementById('dados-status');
    const char = gameState?.character;
    if (!container || !char) {
        if (container) {
            container.className = 'terminal-empty';
            container.setAttribute('aria-busy', 'false');
            container.innerHTML = '<p>[INDISPONÍVEL] O estado do personagem não foi fornecido.</p>';
        }
        if (status) status.textContent = 'Dados do personagem indisponíveis.';
        return;
    }

    const attrs = Array.isArray(char.attrs) ? char.attrs : [];
    const inventory = Array.isArray(gameState.inventory) ? gameState.inventory : [];
    const passives = Array.isArray(char.passivas) ? char.passivas : [];
    const effects = Array.isArray(char.status_effects) ? char.status_effects : [];
    const world = gameState.world || {};
    const activeAttr = gameState.last_roll?.attr_nome || null;
    const contextualState = deriveContextualState(char, gameState.combat);
    const contextualPrefix = contextualState.critical ? '[ATENÇÃO]' : '[ESTÁVEL]';
    window._lastAttrs = attrs;

    const skillsHtml = renderTerminalList(passives, 'Nenhuma habilidade adquirida.', passive => {
        if (typeof passive === 'string') return escapeHtml(passive);
        const name = passive?.nome || passive?.id || 'Habilidade sem identificação';
        const detail = passive?.efeito || passive?.descricao;
        return `<strong>${escapeHtml(name)}</strong>${detail ? `<span class="terminal-list-note">${escapeHtml(detail)}</span>` : ''}`;
    });
    const effectsHtml = renderTerminalList(effects, 'Nenhum efeito ativo.', effect => {
        if (typeof effect === 'string') return escapeHtml(effect);
        const stacks = Number(effect?.stacks || 1);
        return `${terminalDataValue(effect?.id)}${stacks > 1 ? ` ×${escapeHtml(stacks)}` : ''}`;
    });
    const logsHtml = renderTerminalList(
        Array.isArray(engineLog) ? engineLog : [],
        'Nenhum registro de sistema nesta sessão.',
        log => escapeHtml(log)
    );

    container.className = 'dados-terminal';
    container.innerHTML = `<div class="dados-layout">
        <div class="dados-primary">
            <section class="terminal-section dados-identity" aria-labelledby="dados-identity-title">
                <h3 id="dados-identity-title">[ identificação ]</h3>
                <dl class="terminal-definition-grid">
                    <div><dt>personagem</dt><dd>${terminalDataValue(char.name)}</dd></div>
                    <div><dt>nível</dt><dd>${terminalDataValue(char.level)}</dd></div>
                    <div><dt>experiência</dt><dd>${terminalDataValue(char.xp_cur)}/${terminalDataValue(char.xp_next)}</dd></div>
                    <div><dt>arma</dt><dd>${terminalEquipmentValue(char.weapon)}</dd></div>
                    <div><dt>armadura</dt><dd>${terminalEquipmentValue(char.armor)}</dd></div>
                    <div><dt>pontos de atributo</dt><dd>${terminalDataValue(char.attr_pts)}</dd></div>
                </dl>
            </section>

            <section class="terminal-section dados-condition" aria-labelledby="dados-condition-title">
                <h3 id="dados-condition-title">[ estado geral ]</h3>
                <p class="dados-condition-line"><strong>${contextualPrefix}</strong> ${escapeHtml(contextualState.text)}</p>
            </section>

            <section class="terminal-section" aria-labelledby="dados-attrs-title">
                <h3 id="dados-attrs-title">[ atributos ]</h3>
                <div class="terminal-table-wrap">
                    <table class="terminal-table attrs-table">
                        <caption class="sr-only">Atributos base do personagem</caption>
                        <thead><tr><th scope="col">atributo</th><th scope="col">valor</th><th scope="col">estado</th></tr></thead>
                        <tbody id="attrs-grid">${renderAttrsGrid(attrs, activeAttr)}</tbody>
                    </table>
                </div>
            </section>

            <section class="terminal-section" aria-labelledby="dados-resources-title">
                <h3 id="dados-resources-title">[ recursos ]</h3>
                <div class="terminal-table-wrap">
                    <table class="terminal-table resource-table">
                        <caption class="sr-only">Recursos e condição do personagem</caption>
                        <thead><tr><th scope="col">recurso</th><th scope="col">valor</th><th scope="col">leitura</th></tr></thead>
                        <tbody>
                            ${renderResourceRow('integridade', char.hp_cur, char.hp_max, '/')}
                            ${renderResourceRow('energia', char.energy)}
                            ${renderResourceRow('oxigênio', char.o2)}
                            ${renderResourceRow('traje', char.suit)}
                            ${renderResourceRow('casco', char.hull)}
                            ${renderResourceRow('carga do chip', char.chip_carga)}
                            ${renderResourceRow('combustível', char.fuel_cur, char.fuel_max, '/')}
                            ${renderResourceRow('fome', char.fome)}
                            ${renderResourceRow('sede', char.sede)}
                            ${renderResourceRow('exaustão', char.exaustao)}
                        </tbody>
                    </table>
                </div>
            </section>

            <section class="terminal-section" aria-labelledby="dados-skills-title">
                <h3 id="dados-skills-title">[ habilidades ]</h3>
                <ul class="terminal-list">${skillsHtml}</ul>
            </section>

            <section class="terminal-section" aria-labelledby="dados-inventory-title">
                <h3 id="dados-inventory-title">[ inventário ]</h3>
                <div class="terminal-table-wrap terminal-table-responsive" tabindex="0" role="region" aria-label="Inventário do personagem">
                    <table class="terminal-table inventory-table">
                        <caption class="sr-only">Itens carregados pelo personagem</caption>
                        <thead><tr><th scope="col">item</th><th scope="col">qtd.</th><th scope="col">tipo</th><th scope="col">dur.</th><th scope="col">efeito</th></tr></thead>
                        <tbody>${renderInventoryRows(inventory)}</tbody>
                    </table>
                </div>
            </section>

            <section class="terminal-section" aria-labelledby="dados-effects-title">
                <h3 id="dados-effects-title">[ efeitos ativos ]</h3>
                <ul class="terminal-list">${effectsHtml}</ul>
            </section>
        </div>

        <aside class="dados-secondary" aria-label="Contexto e registros secundários">
            <section class="terminal-section" aria-labelledby="dados-context-title">
                <h3 id="dados-context-title">[ contexto atual ]</h3>
                <dl class="terminal-definition-list">
                    <div><dt>capítulo</dt><dd>${terminalDataValue(world.capitulo)} — ${terminalDataValue(world.titulo)}</dd></div>
                    <div><dt>arco</dt><dd>${terminalDataValue(world.arco)}</dd></div>
                    <div><dt>ambiente</dt><dd>${terminalDataValue(world.ambiente)}</dd></div>
                    <div><dt>clima</dt><dd>${terminalDataValue(world.clima)}</dd></div>
                    <div><dt>período</dt><dd>${terminalDataValue(world.periodo)}</dd></div>
                    <div><dt>turno do capítulo</dt><dd>${terminalDataValue(world.interacoes)}</dd></div>
                </dl>
            </section>

            <section class="terminal-section" aria-labelledby="dados-roll-title">
                <h3 id="dados-roll-title">[ última rolagem ]</h3>
                <div id="roll-display">${renderRollSection(gameState.last_roll)}</div>
            </section>

            ${renderWorldSection(gameState.mapa, gameState.quests)}

            <details class="terminal-disclosure">
                <summary>[registros do motor] ${Array.isArray(engineLog) ? engineLog.length : 0} linha(s)</summary>
                <div class="engine-log-container" tabindex="0" role="region" aria-label="Registros recentes do motor">
                    <ul class="terminal-list">${logsHtml}</ul>
                </div>
            </details>
        </aside>
    </div>`;
    container.setAttribute('aria-busy', 'false');
    if (status) status.textContent = `${String(char.name || 'Personagem')} sincronizado: ${attrs.length} atributo(s), ${inventory.length} item(ns).`;
}

let codexEntries = [];
let codexSelectedId = null;
let codexDisplayedId = null;
let codexPageStart = 0;
let codexLastQuery = '';
let codexAvailable = true;
const CODEX_INDEX_PAGE_SIZE = 80;

function normalizeSearch(value) {
    return String(value ?? '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLocaleLowerCase('pt-BR')
        .trim();
}

function codexEntryId(type, name) {
    const slug = normalizeSearch(`${type}-${name}`)
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
    return slug || 'registro';
}

function renderCodexReader(entry) {
    const reader = document.getElementById('codex-reader');
    if (!reader) return;
    clearElement(reader);
    reader.removeAttribute('aria-labelledby');

    if (!entry) {
        reader.appendChild(makeEl('p', 'terminal-empty', 'Nenhum registro selecionado.'));
        return;
    }

    const back = makeEl('button', 'terminal-text-action codex-back', '[voltar ao índice]');
    back.type = 'button';
    back.dataset.codexBack = 'true';
    reader.appendChild(back);

    const path = makeEl('p', 'terminal-path', `C:\\CHRONOS-7\\CODEX\\${entry.type}\\`);
    path.setAttribute('aria-hidden', 'true');
    reader.appendChild(path);
    const title = makeEl('h3', 'codex-entry-title', entry.name);
    title.id = 'codex-entry-title';
    reader.appendChild(title);
    reader.setAttribute('aria-labelledby', title.id);
    reader.appendChild(makeEl('p', 'codex-entry-type', `[${entry.type.toLocaleLowerCase('pt-BR')}]`));
    reader.appendChild(makeEl(
        'p',
        entry.description ? 'codex-entry-copy' : 'terminal-empty',
        entry.description || '[SEM DETALHES] Nenhuma descrição adicional foi catalogada.'
    ));
}

function renderCodexUnavailable(message) {
    codexEntries = [];
    codexSelectedId = null;
    codexDisplayedId = null;
    codexAvailable = false;
    const index = document.getElementById('codex-index');
    const workspace = document.getElementById('codex-workspace');
    const status = document.getElementById('codex-results-status');
    if (index) {
        clearElement(index);
        index.appendChild(makeEl('p', 'terminal-empty', `[INDISPONÍVEL] ${message}`));
    }
    renderCodexReader(null);
    if (workspace) workspace.setAttribute('aria-busy', 'false');
    if (status) status.textContent = 'Codex indisponível.';
}

function renderCodex(query = '', options = {}) {
    const index = document.getElementById('codex-index');
    const workspace = document.getElementById('codex-workspace');
    const status = document.getElementById('codex-results-status');
    const clearButton = document.getElementById('codex-clear-search');
    if (!index || !workspace) return;
    clearElement(index);
    workspace.setAttribute('aria-busy', 'false');
    if (!workspace.dataset.view) workspace.dataset.view = 'index';

    const normalizedQuery = normalizeSearch(query);
    if (normalizedQuery !== codexLastQuery || options.resetPage) codexPageStart = 0;
    if (Number.isInteger(options.pageStart)) codexPageStart = Math.max(0, options.pageStart);
    codexLastQuery = normalizedQuery;
    if (clearButton) clearButton.hidden = !String(query || '').length;

    const visibleEntries = normalizedQuery
        ? codexEntries.filter(entry => normalizeSearch(`${entry.type} ${entry.name} ${entry.description}`).includes(normalizedQuery))
        : codexEntries;

    if (!codexEntries.length) {
        index.appendChild(makeEl(
            'p',
            'terminal-empty',
            codexAvailable ? '[VAZIO] Nenhum registro foi descoberto no Codex.' : '[INDISPONÍVEL] As fontes do Codex não puderam ser lidas.'
        ));
        renderCodexReader(null);
        if (status) status.textContent = codexAvailable ? 'Codex vazio.' : 'Codex indisponível.';
        return;
    }

    if (!visibleEntries.length) {
        index.appendChild(makeEl('p', 'terminal-empty', `[SEM RESULTADO] Nenhum registro corresponde a “${String(query)}”.`));
        renderCodexReader(null);
        if (status) status.textContent = `0 resultados para “${String(query)}”.`;
        return;
    }

    const preferredIndex = visibleEntries.findIndex(entry => entry.id === codexSelectedId);
    if (!Number.isInteger(options.pageStart) && preferredIndex >= 0) {
        codexPageStart = Math.floor(preferredIndex / CODEX_INDEX_PAGE_SIZE) * CODEX_INDEX_PAGE_SIZE;
    }
    codexPageStart = Math.min(codexPageStart, Math.floor((visibleEntries.length - 1) / CODEX_INDEX_PAGE_SIZE) * CODEX_INDEX_PAGE_SIZE);
    const pageEntries = visibleEntries.slice(codexPageStart, codexPageStart + CODEX_INDEX_PAGE_SIZE);
    const displayed = pageEntries.find(entry => entry.id === codexSelectedId) || pageEntries[0];
    codexDisplayedId = displayed?.id || null;
    if (!codexSelectedId && displayed) codexSelectedId = displayed.id;

    const groups = new Map();
    pageEntries.forEach(entry => {
        if (!groups.has(entry.type)) groups.set(entry.type, []);
        groups.get(entry.type).push(entry);
    });
    groups.forEach((entries, type) => {
        const section = makeEl('section', 'codex-index-group');
        section.appendChild(makeEl('h3', 'codex-index-heading', `[ ${type.toLocaleLowerCase('pt-BR')} ]`));
        const list = makeEl('ul', 'codex-index-list');
        entries.forEach(entry => {
            const item = document.createElement('li');
            const button = makeEl('button', 'codex-index-entry', entry.name);
            button.type = 'button';
            button.dataset.codexId = entry.id;
            button.setAttribute('aria-controls', 'codex-reader');
            if (entry.id === codexDisplayedId) button.setAttribute('aria-current', 'true');
            item.appendChild(button);
            list.appendChild(item);
        });
        section.appendChild(list);
        index.appendChild(section);
    });

    if (visibleEntries.length > CODEX_INDEX_PAGE_SIZE) {
        const pager = makeEl('div', 'codex-pager');
        const previous = makeEl('button', 'terminal-text-action', '[anteriores]');
        previous.type = 'button';
        previous.dataset.codexPage = 'previous';
        previous.disabled = codexPageStart === 0;
        const next = makeEl('button', 'terminal-text-action', '[próximos]');
        next.type = 'button';
        next.dataset.codexPage = 'next';
        next.disabled = codexPageStart + CODEX_INDEX_PAGE_SIZE >= visibleEntries.length;
        pager.append(previous, next);
        index.appendChild(pager);
    }

    renderCodexReader(displayed);
    const start = codexPageStart + 1;
    const end = Math.min(codexPageStart + CODEX_INDEX_PAGE_SIZE, visibleEntries.length);
    const availabilityPrefix = codexAvailable ? '' : '[FONTE PARCIAL] ';
    if (status) status.textContent = `${availabilityPrefix}${visibleEntries.length} registro(s). Exibindo ${start}–${end}.`;
}

function updateCodex(bestiary, npcs, meta = {}) {
    codexEntries = [];

    const collectEntries = (obj, type) => {
        if (!obj || typeof obj !== 'object') return;
        Object.entries(obj).forEach(([name, data]) => {
            codexEntries.push({
                type,
                name,
                description: String(data?.descricao ?? data?.description ?? '')
            });
        });
    };

    collectEntries(npcs, 'ENTIDADE');
    collectEntries(bestiary, 'CRIATURA');
    codexEntries.sort((a, b) => a.type.localeCompare(b.type, 'pt-BR') || a.name.localeCompare(b.name, 'pt-BR'));
    codexEntries = codexEntries.map(entry => ({ ...entry, id: codexEntryId(entry.type, entry.name) }));
    codexAvailable = meta?.available !== false;
    if (!codexEntries.some(entry => entry.id === codexSelectedId)) codexSelectedId = codexEntries[0]?.id || null;
    const search = document.getElementById('codex-search');
    renderCodex(search?.value || '', { resetPage: false });
}

function selectCodexEntry(entryId, options = {}) {
    if (!codexEntries.some(entry => entry.id === entryId)) return;
    codexSelectedId = entryId;
    const workspace = document.getElementById('codex-workspace');
    const search = document.getElementById('codex-search');
    if (workspace) workspace.dataset.view = 'reader';
    renderCodex(search?.value || '');
    if (options.focusReader !== false) {
        window.requestAnimationFrame(() => document.getElementById('codex-reader')?.focus({ preventScroll: false }));
    }
}

function returnToCodexIndex() {
    const workspace = document.getElementById('codex-workspace');
    if (workspace) workspace.dataset.view = 'index';
    window.requestAnimationFrame(() => {
        const selected = document.querySelector(`.codex-index-entry[data-codex-id="${codexDisplayedId}"]`);
        (selected || document.getElementById('codex-search'))?.focus({ preventScroll: false });
    });
}


function deriveContextualState(characterSheet, combat) {
    const hpMax = Math.max(1, Number(characterSheet.hp_max || 1));
    const hpPct = (Number(characterSheet.hp_cur || 0) / hpMax) * 100;
    const energy = Number(characterSheet.energy ?? 100);
    const oxygen = Number(characterSheet.o2 ?? 100);
    const suit = Number(characterSheet.suit ?? 100);
    const effects = Array.isArray(characterSheet.status_effects) ? characterSheet.status_effects : [];

    if (Number(characterSheet.hp_cur || 0) <= 0) return { critical: true, text: 'Integridade esgotada. Consulte o HUD completo antes de agir.' };
    if (oxygen <= 25) return { critical: true, text: `Oxigênio crítico: ${oxygen}%.` };
    if (suit <= 25) return { critical: true, text: `Traje em condição crítica: ${suit}%.` };
    if (hpPct <= 25) return { critical: true, text: `Integridade crítica: ${characterSheet.hp_cur}/${hpMax}.` };
    if (combat?.ativo) {
        const opponent = combat.nome ? ` contra ${combat.nome}` : '';
        return { critical: true, text: `Combate ativo${opponent}.` };
    }
    if (effects.length) return { critical: true, text: `${effects.length} efeito(s) ativo(s). Consulte o HUD completo.` };
    if (energy <= 15) return { critical: true, text: `Energia crítica: ${energy}%.` };
    return { critical: false, text: 'Condição estável. Recursos secundários estão no HUD completo.' };
}

function asciiBar(percent, length = 12) {
    const safePercent = Math.max(0, Math.min(100, Number(percent) || 0));
    const filled = Math.round((safePercent / 100) * length);
    return `[${'█'.repeat(filled)}${'░'.repeat(length - filled)}]`;
}

// 5. Atualização visual completa do HUD (updateHUD)
function updateHUD(characterSheet, inventoryJson, combat) {
    if (!characterSheet) return;

    const vitalsMap = {
        hp: { value: characterSheet.hp_cur, max: characterSheet.hp_max || 1 },
        energy: { value: characterSheet.energy, max: 100 },
        fome: { value: characterSheet.fome, max: 100 },
        sede: { value: characterSheet.sede, max: 100 },
        exaustao: { value: characterSheet.exaustao, max: 100 },
        o2: { value: characterSheet.o2, max: 100 },
        suit: { value: characterSheet.suit, max: 100 }
    };

    Object.entries(vitalsMap).forEach(([key, vital]) => {
        if (vital.value !== undefined && vital.value !== null) {
            const pct = Math.max(0, Math.min(100, (Number(vital.value) / Number(vital.max || 1)) * 100));
            const block = document.querySelector(`[data-vital="${key}"]`);
            if (block) {
                if (key === 'hp') block.dataset.critical = String(pct <= 25);
                const fill = block.querySelector('.vital-fill');
                if (fill) fill.style.width = `${pct}%`;
                const meter = block.querySelector('[role="progressbar"]');
                if (meter) {
                    meter.setAttribute('aria-valuenow', String(Math.round(pct)));
                    meter.setAttribute('aria-valuetext', key === 'hp' ? `${vital.value} de ${vital.max}` : `${vital.value}%`);
                }
                const valSpan = block.querySelector('.vital-label span:nth-child(2)');
                if (valSpan) {
                    valSpan.textContent = key === 'hp' ? `${vital.value}/${vital.max}` : `${vital.value}%`;
                }
            }

            const summary = document.querySelector(`[data-summary-vital="${key}"]`);
            if (summary) {
                if (key === 'hp') summary.dataset.critical = String(pct <= 25);
                const output = summary.querySelector('.ascii-output');
                const accessible = summary.querySelector('.ascii-accessible');
                const visibleValue = key === 'hp' ? `${vital.value}/${vital.max}` : `${vital.value}%`;
                const accessibleValue = key === 'hp' ? `${vital.value} de ${vital.max}` : `${vital.value}%`;
                const label = key === 'hp' ? 'Integridade' : 'Energia';
                if (output) output.textContent = `${asciiBar(pct)} ${visibleValue}`;
                if (accessible) accessible.textContent = `${label}: ${accessibleValue}`;
            }
        }
    });

    const summaryHud = document.getElementById('summary-hud');
    if (summaryHud) {
        const hpAvailable = characterSheet.hp_cur !== undefined
            && characterSheet.hp_cur !== null
            && characterSheet.hp_max !== undefined
            && characterSheet.hp_max !== null;
        summaryHud.textContent = hpAvailable ? `${characterSheet.hp_cur}/${characterSheet.hp_max}` : '—';
    }

    const summary = document.querySelector('.log-hud-summary');
    const logStage = document.querySelector('.log-stage');
    const summaryContext = document.getElementById('summary-context');
    const contextualState = deriveContextualState(characterSheet, combat);
    if (summary) summary.dataset.critical = String(contextualState.critical);
    if (logStage) logStage.dataset.critical = String(contextualState.critical);
    if (summaryContext) summaryContext.textContent = contextualState.text;
    if (contextualState.critical) announceLogUpdate(contextualState.text);

    // Inventário
    const invList = document.getElementById('inventory-list');
    if (invList) {
        clearElement(invList);
        if (Array.isArray(inventoryJson) && inventoryJson.length) {
            inventoryJson.forEach(item => {
                invList.appendChild(makeEl('li', '', `${item.name || 'Item sem nome'} (Qt: ${item.qty ?? 0})`));
            });
        } else {
            invList.appendChild(makeEl('li', 'empty-list', 'Inventário vazio.'));
        }
    }

    // Skills/Passivas
    const skillList = document.getElementById('skills-list');
    if (skillList) {
        clearElement(skillList);
        if (Array.isArray(characterSheet.passivas) && characterSheet.passivas.length) {
            characterSheet.passivas.forEach(p => {
                skillList.appendChild(makeEl('li', '', typeof p === 'string' ? p : (p.id || 'Habilidade sem ID')));
            });
        } else {
            skillList.appendChild(makeEl('li', 'empty-list', 'Nenhuma habilidade adquirida.'));
        }
    }

    // Status Ativos
    const statusList = document.getElementById('status-list');
    if (statusList) {
        clearElement(statusList);
        if (Array.isArray(characterSheet.status_effects) && characterSheet.status_effects.length) {
            characterSheet.status_effects.forEach(st => {
                statusList.appendChild(makeEl('li', '', typeof st === 'string' ? st : (st.id || 'Status sem ID')));
            });
        } else {
            statusList.appendChild(makeEl('li', 'empty-list', 'Nenhum efeito ativo.'));
        }
    }
}

function resetHUD() {
    const name = document.getElementById('summary-character-name');
    const level = document.getElementById('summary-level');
    if (name) name.textContent = '—';
    if (level) level.textContent = 'nv.—';
    const summary = document.querySelector('.log-hud-summary');
    const logStage = document.querySelector('.log-stage');
    const summaryContext = document.getElementById('summary-context');
    if (summary) summary.dataset.critical = 'false';
    if (logStage) logStage.dataset.critical = 'false';
    if (summaryContext) summaryContext.textContent = 'Estado local indisponível.';
    const summaryHud = document.getElementById('summary-hud');
    if (summaryHud) summaryHud.textContent = '—';

    document.querySelectorAll('[data-vital]').forEach(block => {
        if (block.dataset.vital === 'hp') block.dataset.critical = 'false';
        const value = block.querySelector('.vital-label span:nth-child(2)');
        const fill = block.querySelector('.vital-fill');
        const meter = block.querySelector('[role="progressbar"]');
        if (value) value.textContent = '—';
        if (fill) fill.style.width = '0%';
        if (meter) {
            meter.setAttribute('aria-valuenow', '0');
            meter.setAttribute('aria-valuetext', 'Indisponível');
        }
    });
    document.querySelectorAll('[data-summary-vital]').forEach(block => {
        if (block.dataset.summaryVital === 'hp') block.dataset.critical = 'false';
        const output = block.querySelector('.ascii-output');
        const accessible = block.querySelector('.ascii-accessible');
        const label = block.dataset.summaryVital === 'hp' ? 'Integridade' : 'Energia';
        if (output) output.textContent = `${asciiBar(0)} —`;
        if (accessible) accessible.textContent = `${label} indisponível`;
    });
    ['inventory-list', 'skills-list', 'status-list'].forEach(id => {
        const list = document.getElementById(id);
        if (!list) return;
        clearElement(list);
        list.appendChild(makeEl('li', 'empty-list', 'Dados indisponíveis.'));
    });
}

function setControlsDisabled(disabled) {
    const input = document.getElementById('command-input');
    if (input) input.disabled = disabled;
    document.querySelectorAll('.action-chip, .utility-action').forEach(button => {
        button.disabled = disabled;
    });
}


// 6. Saída estruturada de Dados (atributos + última rolagem)

function renderAttrsGrid(attrs, activeAttr) {
    if (!Array.isArray(attrs) || !attrs.length) {
        return '<tr class="terminal-table-empty"><td colspan="3">Nenhum atributo disponível.</td></tr>';
    }
    return attrs.map(a => {
        const isActive = activeAttr && a.abbr === activeAttr;
        return `<tr${isActive ? ' class="is-tested"' : ''}>
            <th scope="row">${terminalDataValue(a?.abbr)}</th>
            <td>${terminalDataValue(a?.value)}</td>
            <td>${isActive ? '[testado]' : '—'}</td>
        </tr>`;
    }).join('');
}

function renderRollSection(roll) {
    if (!roll || !roll.dado) {
        return '<p class="roll-empty">Nenhuma rolagem registrada.</p>';
    }

    const dado = roll.dado;
    const total = roll.total ?? dado;
    const isCrit = dado === 20;
    const isFumble = dado === 1;

    let statusText = 'NORMAL';
    if (isCrit) statusText = 'SUCESSO CRÍTICO!';
    if (isFumble) statusText = 'FALHA CRÍTICA!';

    // Fórmula: D20(valor) + MOD(bonus) = TOTAL vs DC
    const formulaParts = [`<strong>D20(${escapeHtml(dado)})</strong>`];
    if (roll.attr_nome && roll.bonus != null) {
        formulaParts.push(`<strong>${escapeHtml(roll.attr_nome)}(${roll.bonus >= 0 ? '+' : ''}${escapeHtml(roll.bonus)})</strong>`);
    }
    let formula = formulaParts.join(' + ');
    formula += ` = <strong>${escapeHtml(total)}</strong>`;
    if (roll.dc != null) {
        const passed = total >= roll.dc;
        formula += ` &nbsp;vs&nbsp; <strong>DC ${escapeHtml(roll.dc)} — ${passed ? 'PASSOU' : 'FALHOU'}</strong>`;
    }

    // Todos os dados rolados
    let allRolls = '';
    if (roll.all_rolls && roll.all_rolls.length > 1) {
        const criterioLabel = roll.criterio === 'MELHOR' ? 'VANTAGEM' : roll.criterio === 'PIOR' ? 'DESVANTAGEM' : '';
        allRolls = `<div class="roll-list">
            ${criterioLabel ? `<strong>[${criterioLabel}]</strong><br>` : ''}
            <span class="roll-list-label">Dados rolados: </span>
            ${roll.all_rolls.map(r => {
                const chosen = r === dado;
                return `<span class="roll-chip${chosen ? ' is-selected' : ''}">${escapeHtml(r)}</span>`;
            }).join(' ')}
        </div>`;
    }

    return `
        <div class="roll-result">
            <div class="roll-die">
                <div class="roll-die-label">D20</div>
                <div class="roll-die-value">${escapeHtml(dado)}</div>
            </div>
            <div class="roll-details">
                <div class="roll-status">${statusText}</div>
                <div class="roll-formula">${formula}</div>
                ${allRolls}
            </div>
        </div>`;
}


function updateRoll(rollData) {
    if (!rollData || !rollData.dado) return;

    // Atualiza painel de rolagem
    const rollDisplay = document.getElementById('roll-display');
    if (rollDisplay) rollDisplay.innerHTML = renderRollSection(rollData);

    // Destaca atributo usado na grid
    const attrGrid = document.getElementById('attrs-grid');
    if (attrGrid && rollData.attr_nome && window._lastAttrs) {
        attrGrid.innerHTML = renderAttrsGrid(window._lastAttrs, rollData.attr_nome);
    }
}


// 7. Navegação entre áreas
const panelScrollPositions = new Map();

function switchTab(tabName, options = {}) {
    const targetContent = document.getElementById(tabName);
    if (!targetContent) return;
    const main = document.querySelector('.main-panel');
    const viewport = document.querySelector('.tab-viewport');
    const previousTab = main?.dataset.activeTab;
    if (viewport && previousTab) panelScrollPositions.set(previousTab, viewport.scrollTop);

    document.querySelectorAll('.tab-content').forEach(panel => {
        const active = panel.id === tabName;
        panel.classList.toggle('active', active);
        panel.hidden = !active;
    });
    const primaryTarget = tabName === 'tab-hud' ? 'tab-log' : tabName;
    document.querySelectorAll('.terminal-tab[data-target]').forEach(button => {
        const active = button.dataset.target === primaryTarget;
        button.classList.toggle('active', active);
        if (active) button.setAttribute('aria-current', 'page');
        else button.removeAttribute('aria-current');
    });

    if (main) main.dataset.activeTab = tabName;
    if (viewport) viewport.scrollTop = panelScrollPositions.get(tabName) || 0;
    if (options.focusPanel) targetContent.focus();
}

// Bind de navegação
document.querySelectorAll('.tab-btn, .view-switch').forEach(btn => {
    btn.addEventListener('click', (event) => {
        const target = event.currentTarget.dataset.target;
        const isViewSwitch = event.currentTarget.classList.contains('view-switch');
        switchTab(target, { focusPanel: isViewSwitch && target !== 'tab-log' });
        if (target === 'tab-codex') {
            window.requestAnimationFrame(() => document.getElementById('codex-search')?.focus({ preventScroll: true }));
        }
        if (isViewSwitch && target === 'tab-log' && inputField && !inputField.disabled) {
            inputField.focus({ preventScroll: true });
        }
    });
});

// Chat e ciclo de turnos
const _chatViewport = document.querySelector('.tab-viewport');

function isNearBottom() {
    if (!_chatViewport) return true;
    const command = document.getElementById('command-form');
    if (!command) return true;
    const viewportRect = _chatViewport.getBoundingClientRect();
    const commandRect = command.getBoundingClientRect();
    return commandRect.bottom <= viewportRect.bottom + 80 && commandRect.bottom >= viewportRect.top;
}

function scrollToBottom(force) {
    if (!_chatViewport) return;
    const command = document.getElementById('command-form');
    if (!command) return;
    if (force || isNearBottom()) {
        const viewportRect = _chatViewport.getBoundingClientRect();
        const commandRect = command.getBoundingClientRect();
        const delta = commandRect.bottom - viewportRect.bottom + 16;
        _chatViewport.scrollTop = Math.max(0, _chatViewport.scrollTop + delta);
    }
}

function currentHistoryAnchor(direction) {
    const chat = document.querySelector('.chat-history');
    if (!chat) return null;
    const messages = chat.querySelectorAll('.chat-msg[data-history-index]');
    if (!messages.length) return null;
    const element = direction === 'older' ? messages[0] : messages[messages.length - 1];
    return {
        index: Number(element.dataset.historyIndex),
        top: element.getBoundingClientRect().top
    };
}

async function fetchHistoryPage(start) {
    const params = new URLSearchParams({ limit: String(HISTORY_CHUNK_SIZE) });
    if (Number.isInteger(start)) params.set('start', String(start));

    let response;
    try {
        response = await fetch(`/api/history?${params.toString()}`, { cache: 'no-store' });
    } catch (_error) {
        throw new Error('O servidor local não respondeu ao carregar o histórico.');
    }

    let payload;
    try {
        payload = await response.json();
    } catch (_error) {
        throw new Error(`O servidor retornou um trecho inválido do histórico (${response.status}).`);
    }
    if (!response.ok || payload?.error) {
        throw new Error(payload?.message || `O histórico não pôde ser carregado (${response.status}).`);
    }
    return normalizeHistoryPage(payload.chat_history, payload.chat_history_page);
}

function setHistoryControlLoading(direction, loading) {
    const chat = document.querySelector('.chat-history');
    if (chat) chat.setAttribute('aria-busy', loading ? 'true' : 'false');
    const control = chat?.querySelector(`[data-history-direction="${direction}"]`);
    if (!control) return;
    control.disabled = loading;
    if (loading) {
        control.textContent = direction === 'older'
            ? '[carregando mensagens anteriores…]'
            : '[carregando mensagens seguintes…]';
    }
}

function reportHistoryLoadFailure(direction, error, userInitiated) {
    console.error('Falha ao carregar trecho do histórico:', error);
    historyWindow.failedDirection = direction;
    const chat = document.querySelector('.chat-history');
    const control = chat?.querySelector(`[data-history-direction="${direction}"]`);
    if (control) {
        control.disabled = false;
        control.textContent = direction === 'older'
            ? '[tentar mensagens anteriores novamente]'
            : '[tentar mensagens seguintes novamente]';
        if (userInitiated) control.focus({ preventScroll: true });
    }
    const message = `${error?.message || 'Falha ao carregar o histórico.'} O trecho visível foi preservado.`;
    setSystemStatus('error', message);
    announceLogUpdate(message);
}

async function loadOlderHistory(options = {}) {
    if (historyWindow.loading || historyWindow.start <= 0) return;
    const userInitiated = Boolean(options.userInitiated);
    const focusDirection = document.activeElement?.dataset?.historyDirection || null;
    const currentStart = historyWindow.start;
    const anchor = currentHistoryAnchor('older');
    const recovering = historyWindow.failedDirection === 'older';
    historyWindow.loading = true;
    historyWindow.failedDirection = null;
    setHistoryControlLoading('older', true);

    try {
        const page = await fetchHistoryPage(Math.max(0, currentStart - HISTORY_CHUNK_SIZE));
        if (page.end !== currentStart) {
            historyWindow.items = page.items;
            historyWindow.start = page.start;
        } else {
            historyWindow.items = [...page.items, ...historyWindow.items];
            historyWindow.start = page.start;
            if (historyWindow.items.length > HISTORY_DOM_LIMIT) {
                historyWindow.items = historyWindow.items.slice(0, HISTORY_DOM_LIMIT);
            }
        }
        historyWindow.total = page.total;
        renderHistoryWindow({
            anchor,
            focusIndex: userInitiated && anchor ? anchor.index : null,
            focusDirection: userInitiated ? null : focusDirection
        });
        if (userInitiated) announceLogUpdate(`${page.items.length} mensagens anteriores carregadas.`);
        if (recovering) setSystemStatus('success', 'Carregamento do histórico recuperado.');
    } catch (error) {
        reportHistoryLoadFailure('older', error, userInitiated);
    } finally {
        historyWindow.loading = false;
        setHistoryControlLoading('older', false);
    }
}

async function loadNewerHistory(options = {}) {
    const currentEnd = historyWindow.start + historyWindow.items.length;
    if (historyWindow.loading || currentEnd >= historyWindow.total) return;
    const userInitiated = Boolean(options.userInitiated);
    const focusDirection = document.activeElement?.dataset?.historyDirection || null;
    const anchor = currentHistoryAnchor('newer');
    const recovering = historyWindow.failedDirection === 'newer';
    historyWindow.loading = true;
    historyWindow.failedDirection = null;
    setHistoryControlLoading('newer', true);

    try {
        const page = await fetchHistoryPage(currentEnd);
        if (page.start !== currentEnd) {
            historyWindow.items = page.items;
            historyWindow.start = page.start;
        } else {
            historyWindow.items = [...historyWindow.items, ...page.items];
            if (historyWindow.items.length > HISTORY_DOM_LIMIT) {
                const overflow = historyWindow.items.length - HISTORY_DOM_LIMIT;
                historyWindow.items = historyWindow.items.slice(overflow);
                historyWindow.start += overflow;
            }
        }
        historyWindow.total = page.total;
        renderHistoryWindow({
            anchor,
            focusIndex: userInitiated && anchor ? anchor.index : null,
            focusDirection: userInitiated ? null : focusDirection
        });
        if (userInitiated) announceLogUpdate(`${page.items.length} mensagens seguintes carregadas.`);
        if (recovering) setSystemStatus('success', 'Carregamento do histórico recuperado.');
    } catch (error) {
        reportHistoryLoadFailure('newer', error, userInitiated);
    } finally {
        historyWindow.loading = false;
        setHistoryControlLoading('newer', false);
    }
}

function checkHistoryProximity() {
    if (!_chatViewport || historyWindow.loading) return;
    if (document.querySelector('.main-panel')?.dataset.activeTab !== 'tab-log') return;
    const chat = document.querySelector('.chat-history');
    if (!chat || !historyWindow.items.length) return;

    const viewportRect = _chatViewport.getBoundingClientRect();
    const chatRect = chat.getBoundingClientRect();
    const threshold = Math.min(240, viewportRect.height * 0.3);
    if (
        historyWindow.start > 0
        && historyWindow.failedDirection !== 'older'
        && chatRect.top >= viewportRect.top - threshold
    ) {
        loadOlderHistory();
        return;
    }

    const currentEnd = historyWindow.start + historyWindow.items.length;
    if (
        currentEnd < historyWindow.total
        && historyWindow.failedDirection !== 'newer'
        && chatRect.bottom <= viewportRect.bottom + threshold
    ) {
        loadNewerHistory();
    }
}

let historyScrollFrame = null;
if (_chatViewport) {
    _chatViewport.addEventListener('scroll', () => {
        if (historyScrollFrame !== null) return;
        historyScrollFrame = window.requestAnimationFrame(() => {
            historyScrollFrame = null;
            checkHistoryProximity();
        });
    }, { passive: true });
}

let pendingStructuredAction = null;

function buildTurnPayload(texto, opt) {
    if (opt && typeof opt === 'object' && opt.type) {
        const payload = {
            action: texto,
            type: opt.type,
            action_label: opt.action_label || opt.label || texto
        };
        if (opt.cmd) payload.cmd = opt.cmd;
        return payload;
    }
    return { action: texto };
}

function terminalOptionLabel(value) {
    return String(value || '').replace(/^[^\p{L}\p{N}]+/u, '').trim();
}

function renderChips(opcoes) {
    const narrativeContainer = document.querySelector('.action-chips-container');
    const utilityContainer = document.querySelector('.utility-actions-container');
    const narrativeRegion = document.getElementById('narrative-actions');
    const utilityRegion = document.getElementById('system-tools');
    if (!narrativeContainer || !utilityContainer) return;

    clearElement(narrativeContainer);
    clearElement(utilityContainer);
    if (narrativeRegion) narrativeRegion.hidden = true;
    if (utilityRegion) utilityRegion.hidden = true;

    if(!opcoes || !Array.isArray(opcoes)) return;

    opcoes.forEach(opt => {
        if (typeof opt === 'object' && opt.type === 'separator') return;
        const textStr = typeof opt === 'object' ? (opt.action_label || opt.label || opt.acao) : opt;
        if (!textStr) return;
        const displayText = terminalOptionLabel(textStr);
        if (!displayText) return;
        const isUtility = typeof opt === 'object' && ['checkpoint_save', 'arc_check'].includes(opt.type);

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = isUtility ? 'utility-action' : 'action-chip';
        btn.textContent = displayText;

        btn.addEventListener('click', () => {
            const input = document.querySelector('.cmd-input-field');
            const feedback = document.getElementById('command-feedback');
            if (input) {
                input.value = displayText;
                pendingStructuredAction = buildTurnPayload(displayText, opt);
                input.removeAttribute('aria-invalid');
                input.focus();
            }
            if (feedback) feedback.textContent = isUtility
                ? 'Ação do sistema carregada no prompt.'
                : 'Sugestão carregada no comando; você ainda pode editá-la.';
        });

        (isUtility ? utilityContainer : narrativeContainer).appendChild(btn);
    });

    if (narrativeRegion) narrativeRegion.hidden = narrativeContainer.childElementCount === 0;
    if (utilityRegion) utilityRegion.hidden = utilityContainer.childElementCount === 0;
}

// Ciclo lógico primário
const inputField = document.getElementById('command-input');
let turnInFlight = false;

async function doAction(texto, payload) {
    const normalizedText = String(texto || '').trim();
    const feedback = document.getElementById('command-feedback');
    const commandForm = document.getElementById('command-form');
    if (!normalizedText) {
        if (feedback) feedback.textContent = 'Descreva uma ação.';
        if (inputField) {
            inputField.setAttribute('aria-invalid', 'true');
            inputField.focus();
        }
        return;
    }
    if (turnInFlight) {
        if (feedback) feedback.textContent = 'O turno atual ainda está sendo processado.';
        announceLogUpdate('Envio duplicado bloqueado. Aguarde o turno atual.');
        return;
    }

    const structuredAction = pendingStructuredAction && pendingStructuredAction.action === normalizedText
        ? pendingStructuredAction
        : null;
    const turnPayload = payload || (
        structuredAction
            ? pendingStructuredAction
            : { action: normalizedText }
    );
    turnInFlight = true;
    pendingStructuredAction = null;
    const utilityAction = ['checkpoint_save', 'arc_check'].includes(turnPayload.type);

    switchTab('tab-log');
    setControlsDisabled(true);
    setSystemStatus('processing', 'Processando o turno no motor local…');
    const chat = document.querySelector('.chat-history');
    if (chat) chat.setAttribute('aria-busy', 'true');
    if (commandForm) commandForm.setAttribute('aria-busy', 'true');
    if (feedback) feedback.textContent = 'Turno em processamento. Aguarde.';
    if (inputField) inputField.removeAttribute('aria-invalid');

    try {
        const response = await fetch('/api/turn', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(turnPayload)
        });

        let resultState;
        try {
            resultState = await response.json();
        } catch (_error) {
            throw new Error(`O motor retornou uma resposta inválida (${response.status}).`);
        }
        if (!response.ok || resultState?.error || resultState?.ok === false) {
            const pendingCharacter = resultState?.state?.character;
            if (pendingCharacter?.level_up_pending || pendingCharacter?.skill_pending) {
                updateHUD(pendingCharacter, resultState.state.inventory, resultState.state.combat);
                confirmSkills(pendingCharacter);
            }
            const usefulLog = Array.isArray(resultState?.log) ? resultState.log.at(-1) : '';
            const turnError = new Error(resultState?.message || usefulLog || `O motor recusou o turno (${response.status}).`);
            turnError.inputInvalid = response.status === 400 && resultState?.error === 'invalid_action';
            throw turnError;
        }

        setTerminalIdentity(resultState.state?.character?.name);
        renderNarrativeState({
            chat_history: resultState.chat_history,
            chat_history_page: resultState.chat_history_page,
            narrative: resultState.scene
        }, { silent: true });
        if (!utilityAction && resultState.scene) announceLogUpdate('Nova cena adicionada ao Log.');
        if (resultState.state?.character) {
            const character = resultState.state.character;
            updateHUD(character, resultState.state.inventory, resultState.state.combat);
            window._lastAttrs = character.attrs || [];
            const name = document.getElementById('summary-character-name');
            const level = document.getElementById('summary-level');
            if (name) name.textContent = character.name || '—';
            if (level) level.textContent = formatTerminalLevel(character.level);
        }
        if (resultState.state?.world) {
            updateCoordinates(
                resultState.state.world.capitulo ?? '—',
                resultState.state.world.ambiente ?? '—',
                resultState.state.world.interacoes ?? '—'
            );
        }
        if (resultState.state) {
            renderDados(resultState.state, resultState.log);
            updateCodex(resultState.state.bestiary, resultState.state.npc_dossier, resultState.state.codex_meta);
        }
        if (Array.isArray(resultState.options)) renderChips(resultState.options);

        const utilityResult = Array.isArray(resultState.log) ? resultState.log.at(-1) : '';
        const successMessage = resultState.scene
            ? 'Turno concluído. A nova cena e o estado local foram sincronizados.'
            : (utilityResult || 'Ação do sistema concluída.');
        setSystemStatus('success', successMessage);
        setConnectionState('ready', 'estável');
        if (inputField) inputField.value = '';
        if (feedback) feedback.textContent = '';
    } catch (error) {
        console.error('Falha no turno:', error);
        const failure = error?.message || 'Falha ao processar o turno.';
        setSystemStatus('error', `${failure} Nenhuma nova cena foi adicionada; o comando foi preservado.`);
        setConnectionState('error', 'atenção');
        if (inputField) {
            inputField.value = normalizedText;
            if (error?.inputInvalid) inputField.setAttribute('aria-invalid', 'true');
            else inputField.removeAttribute('aria-invalid');
        }
        if (feedback) {
            feedback.textContent = error?.inputInvalid
                ? 'O turno não avançou. Revise o comando preservado.'
                : 'O turno não avançou por uma falha do sistema. O comando foi preservado para nova tentativa.';
        }
        if (structuredAction) pendingStructuredAction = structuredAction;
    } finally {
        turnInFlight = false;
        if (chat) chat.setAttribute('aria-busy', 'false');
        if (commandForm) commandForm.setAttribute('aria-busy', 'false');
        const modal = document.getElementById('modal-levelup');
        setControlsDisabled(Boolean(modal?.open) || stateLoadFailed);
        if (inputField && !inputField.disabled) inputField.focus({ preventScroll: true });
    }
}

// 4. Modais
let modalReturnFocus = null;
let levelUpPendingData = null;

function closeLevelUpModal(options = {}) {
    const modal = document.getElementById('modal-levelup');
    const resume = document.getElementById('resume-levelup');
    if (!modal) return;

    if (options.resolved) levelUpPendingData = null;
    if (modal.open) modal.close();

    const stillPending = Boolean(levelUpPendingData);
    if (resume) resume.hidden = !stillPending;
    setControlsDisabled(stillPending || turnInFlight || stateLoadFailed);
    if (stillPending) {
        setSystemStatus('processing', 'Evolução pendente. Retome a escolha antes de avançar o turno.');
    }
    if (stillPending && resume) {
        resume.focus({ preventScroll: true });
    } else if (modalReturnFocus && document.contains(modalReturnFocus)) {
        modalReturnFocus.focus({ preventScroll: true });
    }
    modalReturnFocus = null;
}

function confirmSkills(dados) {
    const modal = document.getElementById('modal-levelup');
    if (!modal) return;
    const box = modal.querySelector('.modal-box');
    if (!box) return;

    const attrPts = Number(dados.attr_pts || 0);
    const skillPending = Boolean(dados.skill_pending);
    const attrs = Array.isArray(dados.attrs) ? dados.attrs : [];
    const skills = Array.isArray(dados.available_skills) ? dados.available_skills : [];
    const choicesCount = Number(dados.skill_choices_count || 1);
    levelUpPendingData = dados;

    clearElement(box);

    const header = makeEl('div', 'modal-header');
    const title = makeEl('h2', '', attrPts > 0 ? 'Upgrade de atributos' : 'Habilidade passiva');
    title.id = 'levelup-title';
    const closeButton = makeEl('button', 'modal-close', 'Fechar');
    closeButton.type = 'button';
    closeButton.setAttribute('aria-label', 'Fechar por enquanto');
    closeButton.addEventListener('click', () => closeLevelUpModal());
    header.appendChild(title);
    header.appendChild(closeButton);
    box.appendChild(header);

    const modalStatus = makeEl('p', 'modal-status', '');
    modalStatus.setAttribute('role', 'status');
    modalStatus.setAttribute('aria-live', 'polite');

    async function submitLevelUp(endpoint, body, actionButton, busyLabel) {
        const originalLabel = actionButton.textContent;
        actionButton.disabled = true;
        actionButton.textContent = busyLabel;
        modal.setAttribute('aria-busy', 'true');
        modalStatus.dataset.state = 'processing';
        modalStatus.textContent = busyLabel;
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            let result;
            try {
                result = await response.json();
            } catch (_error) {
                throw new Error(`O motor retornou uma resposta inválida (${response.status}).`);
            }
            if (!response.ok || result?.ok === false || result?.error) {
                throw new Error(result?.message || result?.error || 'O motor recusou a evolução.');
            }
            modalStatus.dataset.state = 'success';
            modalStatus.textContent = 'Evolução aplicada. Atualizando o estado local…';
            await loadState();
        } catch (error) {
            modalStatus.dataset.state = 'error';
            modalStatus.textContent = `${error?.message || 'Falha ao aplicar a evolução.'} Suas escolhas permanecem disponíveis.`;
            actionButton.disabled = false;
            actionButton.textContent = originalLabel;
        } finally {
            modal.setAttribute('aria-busy', 'false');
        }
    }

    if (attrPts > 0) {
        const hint = makeEl('p', '', `Distribua ${attrPts} ponto(s) antes de avançar o turno.`);
        box.appendChild(hint);

        const form = makeEl('div', '');
        form.style.display = 'grid';
        form.style.gridTemplateColumns = '1fr 90px';
        form.style.gap = '10px';
        form.style.margin = '18px 0';

        attrs.forEach((attr, index) => {
            const label = makeEl('label', '', `${attr.abbr || attr.key}: ${attr.value}`);
            label.style.textAlign = 'left';
            const input = document.createElement('input');
            input.id = `levelup-attr-${index}`;
            label.htmlFor = input.id;
            input.type = 'number';
            input.min = '0';
            input.max = String(attrPts);
            input.value = '0';
            input.dataset.attrKey = attr.key;
            input.style.width = '90px';
            input.style.background = 'var(--bg-input)';
            input.style.color = 'var(--text-strong)';
            input.style.border = '1px solid var(--line-control)';
            input.style.padding = '6px';
            form.appendChild(label);
            form.appendChild(input);
        });

        const actionBtn = makeEl('button', 'btn-transmit', 'Aplicar atributos');
        actionBtn.type = 'button';
        actionBtn.addEventListener('click', async () => {
            const spent = {};
            let total = 0;
            form.querySelectorAll('input').forEach(input => {
                const val = Math.max(0, Number(input.value || 0));
                if (val > 0) {
                    spent[input.dataset.attrKey] = val;
                    total += val;
                }
            });
            if (total !== attrPts) {
                modalStatus.dataset.state = 'error';
                modalStatus.textContent = `Distribua exatamente ${attrPts} ponto(s).`;
                return;
            }
            await submitLevelUp('/api/levelup', { spent }, actionBtn, 'Aplicando atributos…');
        });

        box.appendChild(form);
        box.appendChild(modalStatus);
        box.appendChild(actionBtn);
    } else if (skillPending) {
        const hint = makeEl('p', '', `Escolha ${choicesCount} habilidade(s) passiva(s).`);
        box.appendChild(hint);

        const list = makeEl('div', '');
        list.style.display = 'grid';
        list.style.gap = '10px';
        list.style.margin = '18px 0';
        list.style.maxHeight = '45vh';
        list.style.overflowY = 'auto';

        if (!skills.length) {
            list.appendChild(makeEl('p', '', 'Nenhuma habilidade elegível retornada pelo motor.'));
        }

        skills.forEach(skill => {
            const row = makeEl('label', '');
            row.style.display = 'grid';
            row.style.gridTemplateColumns = '24px 1fr';
            row.style.gap = '8px';
            row.style.textAlign = 'left';
            row.style.padding = '8px';
            row.style.border = '1px solid var(--line)';

            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = skill.id;
            const body = makeEl('span', '', `${skill.nome || skill.id} — ${skill.efeito || skill.descricao || ''}`);
            row.appendChild(cb);
            row.appendChild(body);
            list.appendChild(row);
        });

        const actionBtn = makeEl('button', 'btn-transmit', 'Confirmar habilidade');
        actionBtn.type = 'button';
        actionBtn.disabled = skills.length === 0;
        actionBtn.addEventListener('click', async () => {
            const selected = Array.from(list.querySelectorAll('input:checked')).map(i => i.value);
            if (selected.length !== choicesCount) {
                modalStatus.dataset.state = 'error';
                modalStatus.textContent = `Selecione exatamente ${choicesCount} habilidade(s).`;
                return;
            }
            await submitLevelUp('/api/skill', { skill_ids: selected }, actionBtn, 'Confirmando habilidade…');
        });

        box.appendChild(list);
        box.appendChild(modalStatus);
        box.appendChild(actionBtn);
    } else {
        box.appendChild(makeEl('p', '', 'Nenhum upgrade pendente.'));
        const actionBtn = makeEl('button', 'btn-transmit', 'Fechar');
        actionBtn.type = 'button';
        actionBtn.addEventListener('click', () => closeLevelUpModal({ resolved: true }));
        box.appendChild(actionBtn);
    }

    const activeElement = document.activeElement;
    modalReturnFocus = activeElement && activeElement !== document.body
        ? activeElement
        : document.getElementById('command-input');
    const resume = document.getElementById('resume-levelup');
    if (resume) resume.hidden = true;
    if (!modal.open) modal.showModal();
    setControlsDisabled(true);
    window.requestAnimationFrame(() => {
        const initialFocus = box.querySelector('input:not(:disabled)') || box.querySelector('button:not(:disabled)');
        (initialFocus || box).focus();
    });
}

// 5. Inicialização e Listeners Globais
const commandForm = document.getElementById('command-form');
if (commandForm && inputField) {
    commandForm.addEventListener('submit', event => {
        event.preventDefault();
        doAction(inputField.value);
    });
    inputField.addEventListener('keydown', event => {
        if (event.key !== 'Enter' || event.isComposing) return;
        event.preventDefault();
        doAction(inputField.value);
    });
    inputField.addEventListener('input', () => {
        if (pendingStructuredAction && inputField.value !== pendingStructuredAction.action) {
            pendingStructuredAction = null;
        }
        inputField.removeAttribute('aria-invalid');
        const feedback = document.getElementById('command-feedback');
        if (feedback) feedback.textContent = '';
    });
}

const retryState = document.getElementById('retry-state');
if (retryState) retryState.addEventListener('click', () => loadState({ userInitiated: true }));

const resumeLevelUp = document.getElementById('resume-levelup');
if (resumeLevelUp) {
    resumeLevelUp.addEventListener('click', () => {
        if (levelUpPendingData) confirmSkills(levelUpPendingData);
    });
}

const codexSearch = document.getElementById('codex-search');
if (codexSearch) {
    codexSearch.addEventListener('input', event => {
        const workspace = document.getElementById('codex-workspace');
        if (workspace) workspace.dataset.view = 'index';
        renderCodex(event.currentTarget.value, { resetPage: true });
    });
    codexSearch.addEventListener('keydown', event => {
        if (event.key === 'ArrowDown') {
            const firstEntry = document.querySelector('.codex-index-entry[aria-current="true"], .codex-index-entry');
            if (firstEntry) {
                event.preventDefault();
                firstEntry.focus();
            }
        }
        if (event.key === 'Escape' && codexSearch.value) {
            event.preventDefault();
            codexSearch.value = '';
            renderCodex('', { resetPage: true });
        }
    });
}

const codexSearchForm = document.getElementById('codex-search-form');
if (codexSearchForm) {
    codexSearchForm.addEventListener('submit', event => {
        event.preventDefault();
        if (codexDisplayedId) selectCodexEntry(codexDisplayedId);
    });
}

const codexClearSearch = document.getElementById('codex-clear-search');
if (codexClearSearch) {
    codexClearSearch.addEventListener('click', () => {
        if (!codexSearch) return;
        codexSearch.value = '';
        const workspace = document.getElementById('codex-workspace');
        if (workspace) workspace.dataset.view = 'index';
        renderCodex('', { resetPage: true });
        codexSearch.focus();
    });
}

const codexIndex = document.getElementById('codex-index');
if (codexIndex) {
    codexIndex.addEventListener('click', event => {
        const entry = event.target.closest('[data-codex-id]');
        if (entry) {
            selectCodexEntry(entry.dataset.codexId);
            return;
        }
        const pager = event.target.closest('[data-codex-page]');
        if (!pager) return;
        const direction = pager.dataset.codexPage === 'next' ? 1 : -1;
        renderCodex(codexSearch?.value || '', { pageStart: codexPageStart + (direction * CODEX_INDEX_PAGE_SIZE) });
        window.requestAnimationFrame(() => document.querySelector('.codex-index-entry')?.focus());
    });
    codexIndex.addEventListener('keydown', event => {
        const current = event.target.closest('.codex-index-entry');
        if (!current) return;
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            selectCodexEntry(current.dataset.codexId);
            return;
        }
        const entries = Array.from(codexIndex.querySelectorAll('.codex-index-entry'));
        const currentIndex = entries.indexOf(current);
        let targetIndex = null;
        if (event.key === 'ArrowDown') targetIndex = Math.min(entries.length - 1, currentIndex + 1);
        if (event.key === 'ArrowUp') targetIndex = Math.max(0, currentIndex - 1);
        if (event.key === 'Home') targetIndex = 0;
        if (event.key === 'End') targetIndex = entries.length - 1;
        if (targetIndex !== null) {
            event.preventDefault();
            entries[targetIndex]?.focus();
        }
    });
}

const codexReader = document.getElementById('codex-reader');
if (codexReader) {
    codexReader.addEventListener('click', event => {
        if (event.target.closest('[data-codex-back]')) returnToCodexIndex();
    });
    codexReader.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            event.preventDefault();
            returnToCodexIndex();
        }
    });
}

const skipLink = document.querySelector('.skip-link');
if (skipLink) {
    skipLink.addEventListener('click', event => {
        const main = document.getElementById('main-content');
        if (!main) return;
        event.preventDefault();
        main.focus({ preventScroll: false });
    });
}

const levelupModal = document.getElementById('modal-levelup');
if (levelupModal) {
    levelupModal.addEventListener('cancel', event => {
        event.preventDefault();
        closeLevelUpModal();
    });
}

window.addEventListener('DOMContentLoaded', () => {
    switchTab('tab-log');
    loadState();
});

