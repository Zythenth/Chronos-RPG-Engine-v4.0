// ---------------------------------------------------------
// FASE 2: FUNÇÕES DE ESTADO, HUD, CANVAS E EFEITOS
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

// 1. Canvas de Estrelas (Background Dinâmico) — OTIMIZADO
const canvas = document.getElementById('stars');
const ctx = canvas.getContext('2d');
let stars = [];
const numStars = 200;
let warpSpeed = false;
let speedFactor = 1;
let starAnimId = null;
let lastFrameTime = 0;
const TARGET_FPS = 30;
const FRAME_INTERVAL = 1000 / TARGET_FPS;
const CANVAS_SCALE = 0.5; // Renderiza a metade da resolução, CSS escala para tela cheia

function initCanvas() {
    // Buffer interno a metade da resolução → ~75% menos pixels processados
    canvas.width = Math.floor(window.innerWidth * CANVAS_SCALE);
    canvas.height = Math.floor(window.innerHeight * CANVAS_SCALE);
    stars = [];
    for (let i = 0; i < numStars; i++) {
        stars.push({
            x: Math.random() * canvas.width - canvas.width / 2,
            y: Math.random() * canvas.height - canvas.height / 2,
            z: Math.random() * canvas.width,
            prevZ: Math.random() * canvas.width
        });
    }
}

function updateStars() {
    if (warpSpeed) {
        speedFactor += (15 - speedFactor) * 0.1;
    } else {
        speedFactor += (1 - speedFactor) * 0.05;
    }

    const cw = canvas.width;
    const ch = canvas.height;
    for (let i = 0; i < stars.length; i++) {
        const star = stars[i];
        star.prevZ = star.z;
        star.z -= speedFactor * 2;
        if (star.z <= 0) {
            star.x = Math.random() * cw - cw / 2;
            star.y = Math.random() * ch - ch / 2;
            star.z = cw;
            star.prevZ = cw;
        }
    }
}

function drawStars() {
    ctx.fillStyle = 'rgba(2, 4, 8, 0.2)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    const cw = canvas.width;
    const ch = canvas.height;
    const color = warpSpeed ? '#00f5ff' : '#ffffff';
    ctx.strokeStyle = color;

    if (warpSpeed) {
        // Warp: lineWidth uniforme → batch único (200 → 1 draw call)
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 0; i < stars.length; i++) {
            const s = stars[i];
            ctx.moveTo((s.x / s.prevZ) * cw + cx, (s.y / s.prevZ) * ch + cy);
            ctx.lineTo((s.x / s.z) * cw + cx, (s.y / s.z) * ch + cy);
        }
        ctx.stroke();
    } else {
        // Normal: 2 buckets de lineWidth (200 → 2 draw calls)
        const thick = [];
        ctx.lineWidth = 0.5;
        ctx.beginPath();
        for (let i = 0; i < stars.length; i++) {
            const s = stars[i];
            const px = (s.x / s.prevZ) * cw + cx;
            const py = (s.y / s.prevZ) * ch + cy;
            const x  = (s.x / s.z) * cw + cx;
            const y  = (s.y / s.z) * ch + cy;
            if ((1 - s.z / cw) * 2 < 1) {
                ctx.moveTo(px, py);
                ctx.lineTo(x, y);
            } else {
                thick.push(px, py, x, y);
            }
        }
        ctx.stroke();

        ctx.lineWidth = 1.5;
        ctx.beginPath();
        for (let i = 0; i < thick.length; i += 4) {
            ctx.moveTo(thick[i], thick[i + 1]);
            ctx.lineTo(thick[i + 2], thick[i + 3]);
        }
        ctx.stroke();
    }
}

function starLoop(timestamp) {
    starAnimId = requestAnimationFrame(starLoop);
    // Throttle a ~30fps (metade de 60fps)
    const delta = timestamp - lastFrameTime;
    if (delta < FRAME_INTERVAL) return;
    lastFrameTime = timestamp - (delta % FRAME_INTERVAL);
    updateStars();
    drawStars();
}

// Pausa completamente quando a aba não está visível
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        if (starAnimId) { cancelAnimationFrame(starAnimId); starAnimId = null; }
    } else if (!starAnimId) {
        lastFrameTime = performance.now();
        starAnimId = requestAnimationFrame(starLoop);
    }
});

window.addEventListener('resize', initCanvas);
initCanvas();
starAnimId = requestAnimationFrame(starLoop);

function warpStart() { warpSpeed = true; }
function warpStop() { warpSpeed = false; }


// 2. Widget de Coordenadas (Odômetro)
function updateCoordinates(ano, setor, turno) {
    const slots = document.querySelectorAll('.coordinate-slot');
    if (slots.length >= 3) {
        animateOdometer(slots[0], ano);
        animateOdometer(slots[1], setor);
        animateOdometer(slots[2], turno);
    }
}

function animateOdometer(element, newValue) {
    if (element.innerText === String(newValue)) return;
    
    // Animação inline de translate
    element.style.transition = 'all 0.2s';
    element.style.transform = 'translateY(-10px)';
    element.style.opacity = '0';
    
    setTimeout(() => {
        element.innerText = newValue;
        element.style.transform = 'translateY(10px)';
        
        setTimeout(() => {
            element.style.transform = 'translateY(0)';
            element.style.opacity = '1';
        }, 50);
    }, 200);
}


// 3. Efeito Glitch
function triggerGlitch() {
    const body = document.body;
    body.classList.add('glitch-active'); // marcador de estado
    
    // Hacker visual via DOM style manipulation das bordas/fontes globais
    document.documentElement.style.filter = 'hue-rotate(90deg) contrast(150%) blur(1px)';
    document.querySelectorAll('.app-container').forEach(el => {
        el.style.transform = 'translate(2px, 2px)';
    });
    
    // Desliga após 1500ms
    setTimeout(() => {
        document.documentElement.style.filter = '';
        document.querySelectorAll('.app-container').forEach(el => {
            el.style.transform = '';
        });
        body.classList.remove('glitch-active');
    }, 1500);
}


// 4. Integração de Estado (GET /api/state)
async function loadState() {
    try {
        const response = await fetch('/api/state');
        if (!response.ok) throw new Error('Falha ao sincronizar o motor narrativo.');
        
        const state = await response.json();
        
        // Narrative e Histórico do Chat
        const chat = document.querySelector('.chat-history');
        if (state.chat_history && state.chat_history.length > 0) {
            if (chat) clearElement(chat);
            state.chat_history.forEach(msg => {
                const div = document.createElement('div');
                div.className = `chat-msg ${msg.role}`;
                if (msg.role === 'gm') {
                    div.innerHTML = formatLimitedMarkdown(msg.text);
                } else {
                    div.textContent = msg.text;
                }
                if (chat) chat.appendChild(div);
            });
            scrollToBottom(true);
        } else if (state.narrative) {
            if (chat) clearElement(chat);
            appendMessage('gm', state.narrative);
        }
        
        // Popula barras e Status do HUD
        if (state.state && state.state.character) {
            updateHUD(state.state.character, state.state.inventory);
            if (state.state.character.level_up_pending || state.state.character.skill_pending) {
                confirmSkills(state.state.character);
            } else {
                const modal = document.getElementById('modal-levelup');
                if (modal) modal.style.display = 'none';
            }
            
            // Popula a Tela de DADOS
            const char = state.state.character;
            const container = document.getElementById('dados-container');
            if (container) {
                container.style.color = 'inherit';
                container.style.fontStyle = 'normal';
                
                window._lastAttrs = char.attrs || [];
                const activeAttr = state.state.last_roll ? state.state.last_roll.attr_nome : null;
                let attrsHtml = renderAttrsGrid(char.attrs, activeAttr);
                
                let logsHtml = (state.log && state.log.length > 0) ? state.log.map(l => {
                    let color = 'inherit';
                    if (l.includes('⚠') || l.includes('✗')) color = 'var(--cyber-red)';
                    else if (l.includes('✓')) color = '#00ffaa'; 
                    return `<div style="font-family: monospace; font-size: 0.85em; margin-bottom: 4px; color: ${color}; opacity: 0.9;">${escapeHtml(l)}</div>`;
                }).join('') : '<div style="font-style:italic;">Nenhum registro de sistema.</div>';

                let rollHtml = renderRollSection(state.state.last_roll);
                const worldHtml = renderWorldSection(state.state.mapa, state.state.quests);

                container.innerHTML = `
                    <h3 style="color:var(--cyber-cyan); border-bottom:1px solid var(--cyber-cyan); padding-bottom:5px;">DIAGNÓSTICO DO HOSPEDEIRO</h3>
                    <p style="margin:8px 0;"><strong>Nível:</strong> ${escapeHtml(char.level)} &nbsp;|&nbsp; <strong>Experiência:</strong> ${escapeHtml(char.xp_cur)}/${escapeHtml(char.xp_next)}</p>
                    <p style="margin:8px 0;"><strong>Integridade do Traje:</strong> ${escapeHtml(char.suit)}%</p>
                    <p style="margin:8px 0;"><strong>Carga do Chip CHRONOS:</strong> ${escapeHtml(char.chip_carga)}%</p>

                    <h3 style="color:var(--cyber-cyan); border-bottom:1px solid var(--cyber-cyan); padding-bottom:5px; margin-top:25px;">ATRIBUTOS BASE</h3>
                    <ul id="attrs-grid" style="list-style:none; padding:0; display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:10px;">
                        ${attrsHtml}
                    </ul>

                    <h3 style="color:var(--cyber-cyan); border-bottom:1px solid var(--cyber-cyan); padding-bottom:5px; margin-top:25px;">ÚLTIMA ROLAGEM DE DADOS</h3>
                    <div id="roll-display" style="background: rgba(0,0,0,0.5); padding: 15px; border: 1px solid rgba(0, 245, 255, 0.2); border-radius: 4px;">
                        ${rollHtml}
                    </div>

                    <h3 style="color:var(--cyber-cyan); border-bottom:1px solid var(--cyber-cyan); padding-bottom:5px; margin-top:25px;">REGISTROS DO MOTOR E ROLAGENS</h3>
                    <div class="engine-log-container" style="background: rgba(0,0,0,0.5); padding: 10px; height: 180px; overflow-y: auto; border: 1px solid rgba(0, 245, 255, 0.2); border-radius: 4px; display: flex; flex-direction: column;">
                        ${logsHtml}
                    </div>
                    ${worldHtml}
                `;
                
                // Auto-scroll log
                const logCont = container.querySelector('.engine-log-container');
                if(logCont) logCont.scrollTop = logCont.scrollHeight;
            }
        }
        
        // Coordenadas via Chapter Tracker
        if (state.state && state.state.world) {
            updateCoordinates(
                state.state.world.capitulo || 2142, 
                state.state.world.ambiente || "X", 
                state.state.world.interacoes || 0
            );
        }

        // Action Chips de narrativa
        if (state.options && Array.isArray(state.options)) {
            renderChips(state.options);
        }

        // Codex Data
        if (state.state) updateCodex(state.state.bestiary, state.state.npc_dossier);

    } catch (error) {
        console.error("Erro na API:", error);
    }
}


// Utils para append no chat
function appendMessage(role, text) {
    const chat = document.querySelector('.chat-history');
    if (!chat) return;
    
    const div = document.createElement('div');
    div.className = `chat-msg ${role}`;
    
    if (role === 'gm') {
        div.innerHTML = formatLimitedMarkdown(text);
    } else {
        div.textContent = `> COMANDO: ${text}`;
    }
    
    chat.appendChild(div);
    scrollToBottom(true);
}

function populateActionChips(options) {
    const container = document.querySelector('.action-chips-container');
    if (!container) return;
    clearElement(container);
    options.forEach(opt => {
        if (typeof opt === 'object' && opt.type === 'separator') return;
        const optLabel = typeof opt === 'object' ? (opt.action_label || opt.label || opt.acao) : opt;
        const btn = document.createElement('button');
        btn.className = 'action-chip';
        btn.textContent = `[→ ${optLabel}]`;
        container.appendChild(btn);
    });
}

function renderWorldSection(mapa, quests) {
    const areas = Array.isArray(mapa) ? mapa : [];
    const questList = Array.isArray(quests) ? quests : [];
    const areasHtml = areas.length
        ? areas.slice(0, 6).map(a => `<li>${escapeHtml(a.nome || a.id || 'Área')} — ${escapeHtml(a.status || 'desconhecida')}</li>`).join('')
        : '<li>Nenhuma área descoberta.</li>';
    const questsHtml = questList.length
        ? questList.slice(0, 4).map(q => {
            const objectives = Array.isArray(q.objetivos) ? q.objetivos.slice(0, 4) : [];
            const objHtml = objectives.length
                ? objectives.map(o => `<li>${o.feito ? '[x]' : '[ ]'} ${escapeHtml(o.texto || '')}</li>`).join('')
                : '<li>Sem objetivos rastreados.</li>';
            return `<div style="margin:10px 0;">
                <strong>${escapeHtml(q.tipo || 'QUEST')} — ${escapeHtml(q.nome || '')}</strong>
                <ul style="margin-top:6px; padding-left:18px;">${objHtml}</ul>
            </div>`;
        }).join('')
        : '<div style="font-style:italic;">Nenhuma missão ativa rastreada.</div>';

    return `
        <h3 style="color:var(--cyber-cyan); border-bottom:1px solid var(--cyber-cyan); padding-bottom:5px; margin-top:25px;">MAPA E MISSÕES</h3>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
            <div style="background: rgba(0,0,0,0.35); padding:10px; border:1px solid rgba(0,245,255,0.15);">
                <strong>Áreas</strong>
                <ul style="margin-top:8px; padding-left:18px;">${areasHtml}</ul>
            </div>
            <div style="background: rgba(0,0,0,0.35); padding:10px; border:1px solid rgba(0,245,255,0.15);">
                <strong>Missões</strong>
                ${questsHtml}
            </div>
        </div>`;
}

function updateCodex(bestiary, npcs) {
    const codexGrid = document.querySelector('.codex-cards-grid');
    if (!codexGrid) return;
    clearElement(codexGrid);
    
    const objToCards = (obj, tipo) => {
        if (!obj) return;
        Object.entries(obj).forEach(([name, data]) => {
            const card = makeEl('div', 'codex-card');
            card.appendChild(makeEl('h3', '', `${tipo}: ${name}`));
            card.appendChild(makeEl('p', '', data.descricao || data.description || 'Nenhum registro extra encontrado.'));
            codexGrid.appendChild(card);
        });
    }

    objToCards(npcs, 'ENTIDADE');
    objToCards(bestiary, 'CRIATURA');
}


// 5. Atualização visual completa do HUD (updateHUD)
function updateHUD(characterSheet, inventoryJson) {
    if (!characterSheet) return;

    // Vitais Mapeados: HP, Energy, Fome, Sede, Exaustão, O2
    const vitalsMap = {
        'hp': { value: characterSheet.hp_cur, max: characterSheet.hp_max || 25, selector: '.vital-block.hp' },
        'energy': { value: characterSheet.energy, max: 100, selector: '.vital-block.energy' },
        'fome': { value: characterSheet.fome, max: 100, selector: '.vital-block.survival:nth-child(4)' },
        'sede': { value: characterSheet.sede, max: 100, selector: '.vital-block.survival:nth-child(5)' },
        'exaustao': { value: characterSheet.exaustao, max: 100, selector: '.vital-block.survival:nth-child(6)' },
        'o2': { value: characterSheet.o2, max: 100, selector: '.vital-block.o2' }
    };

    Object.values(vitalsMap).forEach(vital => {
        const block = document.querySelector(vital.selector);
        if (block && vital.value !== undefined) {
            const fill = block.querySelector('.vital-fill');
            const pct = Math.max(0, Math.min(100, (vital.value / vital.max) * 100));
            if(fill) {
               fill.style.width = `${pct}%`;
            }
            
            const valSpan = block.querySelector('.vital-label span:nth-child(2)');
            if (valSpan) {
                if (vital.selector.includes('hp')) {
                    valSpan.textContent = `${vital.value}/${vital.max}`;
                } else if (vital.selector.includes('survival')) {
                    valSpan.textContent = vital.value;
                } else {
                    valSpan.textContent = `${vital.value}%`;
                }
            }
        }
    });

    // Inventário
    if (inventoryJson && Array.isArray(inventoryJson)) {
        const invList = document.querySelector('.hud-section:nth-child(2) .hud-list');
        if (invList) {
            clearElement(invList);
            inventoryJson.forEach(item => {
                invList.appendChild(makeEl('li', '', `${item.name || '?'} (Qt: ${item.qty !== undefined ? item.qty : 1})`));
            });
        }
    }

    // Skills/Passivas
    if (characterSheet.passivas && Array.isArray(characterSheet.passivas)) {
        const skillList = document.querySelector('.hud-section:nth-child(3) .hud-list');
        if (skillList) {
            clearElement(skillList);
            characterSheet.passivas.forEach(p => {
                skillList.appendChild(makeEl('li', '', typeof p === 'string' ? p : p.id));
            });
        }
    }

    // Status Ativos
    if (characterSheet.status_effects && Array.isArray(characterSheet.status_effects)) {
        const statusList = document.querySelector('.hud-section:nth-child(4) .hud-list');
        if (statusList) {
            clearElement(statusList);
            characterSheet.status_effects.forEach(st => {
                const name = typeof st === 'string' ? st : st.id;
                const li = makeEl('li', 'glitch', name);
                li.setAttribute('data-text', name);
                statusList.appendChild(li);
            });
        }
    }
}


// 6. Holografia de Dados (renderAttrsGrid + renderRollSection + updateRoll)

function renderAttrsGrid(attrs, activeAttr) {
    if (!attrs) return '';
    return attrs.map(a => {
        const isActive = activeAttr && a.abbr === activeAttr;
        const border = isActive ? '1px solid var(--cyber-amber)' : '1px solid rgba(0,245,255,0.2)';
        const bg = isActive ? 'rgba(255,170,0,0.12)' : 'rgba(0,0,0,0.4)';
        const glow = isActive ? 'box-shadow:0 0 10px rgba(255,170,0,0.3);' : '';
        const nameColor = isActive ? 'color:var(--cyber-amber);' : 'color:var(--cyber-cyan);';
        const badge = isActive ? '<span style="font-size:0.6rem; color:var(--cyber-amber); float:right; letter-spacing:1px;">TESTADO</span>' : '';
        return `<li style="background:${bg}; padding:8px; border:${border}; ${glow}">
            ${badge}<span style="${nameColor} font-weight:bold;">${escapeHtml(a.abbr)}</span>: ${escapeHtml(a.value)}
        </li>`;
    }).join('');
}

function renderRollSection(roll) {
    if (!roll || !roll.dado) {
        return '<div style="font-style:italic; color:rgba(0,245,255,0.4);">Nenhuma rolagem registrada.</div>';
    }

    const dado = roll.dado;
    const total = roll.total || dado;
    const isCrit = dado === 20;
    const isFumble = dado === 1;

    let statusColor = 'var(--cyber-cyan)';
    let statusText = 'NORMAL';
    if (isCrit)  { statusColor = 'var(--cyber-green)'; statusText = 'SUCESSO CRÍTICO!'; }
    if (isFumble){ statusColor = 'var(--cyber-red)';   statusText = 'FALHA CRÍTICA!'; }

    // Bloco do dado principal
    let diceVisual = `<span style="font-size:2.2rem; font-family:var(--font-header); color:${statusColor}; text-shadow:0 0 12px ${statusColor};">${escapeHtml(dado)}</span>`;

    // Fórmula: D20(valor) + MOD(bonus) = TOTAL vs DC
    let formulaParts = [`<span style="color:${statusColor}; font-weight:bold;">D20(${escapeHtml(dado)})</span>`];
    if (roll.attr_nome && roll.bonus != null) {
        formulaParts.push(`<span style="color:var(--cyber-amber); font-weight:bold;">${escapeHtml(roll.attr_nome)}(${roll.bonus >= 0 ? '+' : ''}${escapeHtml(roll.bonus)})</span>`);
    }
    let formula = formulaParts.join(' + ');
    formula += ` = <span style="color:#fff; font-weight:bold; font-size:1.1em;">${escapeHtml(total)}</span>`;
    if (roll.dc != null) {
        const passed = total >= roll.dc;
        const dcColor = passed ? 'var(--cyber-green)' : 'var(--cyber-red)';
        formula += ` &nbsp;vs&nbsp; <span style="color:${dcColor}; font-weight:bold;">DC ${escapeHtml(roll.dc)} ${passed ? '✓ PASSOU' : '✗ FALHOU'}</span>`;
    }

    // Todos os dados rolados
    let allRolls = '';
    if (roll.all_rolls && roll.all_rolls.length > 1) {
        const criterioLabel = roll.criterio === 'MELHOR' ? 'VANTAGEM' : roll.criterio === 'PIOR' ? 'DESVANTAGEM' : '';
        const criterioColor = roll.criterio === 'MELHOR' ? 'var(--cyber-green)' : 'var(--cyber-red)';
        allRolls = `<div style="margin-top:10px; padding-top:8px; border-top:1px solid rgba(255,255,255,0.05);">
            ${criterioLabel ? `<span style="font-family:var(--font-header); font-size:0.7rem; color:${criterioColor}; letter-spacing:1px;">[${criterioLabel}]</span><br>` : ''}
            <span style="color:#8c9baf; font-size:0.8rem;">Dados rolados: </span>
            ${roll.all_rolls.map(r => {
                const chosen = r === dado;
                const c = chosen ? statusColor : '#555';
                return `<span style="display:inline-block; min-width:28px; text-align:center; padding:2px 6px; margin:2px; background:${chosen ? 'rgba(255,255,255,0.08)' : 'transparent'}; border:1px solid ${c}; border-radius:3px; color:${c}; font-weight:${chosen ? 'bold' : 'normal'}; font-size:0.9rem;">${escapeHtml(r)}</span>`;
            }).join(' ')}
        </div>`;
    }

    return `
        <div style="display:flex; align-items:center; gap:20px;">
            <div style="min-width:65px; text-align:center; background:rgba(0,0,0,0.6); border:1px solid ${statusColor}; padding:12px 10px; border-radius:4px;">
                <div style="font-size:0.6rem; color:#8c9baf; letter-spacing:2px; margin-bottom:4px;">D20</div>
                ${diceVisual}
            </div>
            <div style="flex:1;">
                <div style="font-family:var(--font-header); font-size:0.85rem; color:${statusColor}; letter-spacing:1px; margin-bottom:8px;">${statusText}</div>
                <div style="font-size:0.9rem; line-height:1.6;">${formula}</div>
                ${allRolls}
            </div>
        </div>`;
}


function updateRoll(rollData) {
    if (!rollData || !rollData.dado) return;

    const appContainer = document.querySelector('.app-container');
    const dado = rollData.dado;

    // Efeito visual
    if (dado === 20) {
        appContainer.style.boxShadow = "inset 0 0 100px var(--cyber-green)";
        setTimeout(() => appContainer.style.boxShadow = "none", 800);
    } else if (dado === 1) {
        appContainer.style.boxShadow = "inset 0 0 100px var(--cyber-red)";
        triggerGlitch();
        setTimeout(() => appContainer.style.boxShadow = "none", 1500);
    }

    // Atualiza painel de rolagem
    const rollDisplay = document.getElementById('roll-display');
    if (rollDisplay) rollDisplay.innerHTML = renderRollSection(rollData);

    // Destaca atributo usado na grid
    const attrGrid = document.getElementById('attrs-grid');
    if (attrGrid && rollData.attr_nome && window._lastAttrs) {
        attrGrid.innerHTML = renderAttrsGrid(window._lastAttrs, rollData.attr_nome);
    }
}


// 7. Navegação (Tabs)
function switchTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(tc => {
        tc.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    const targetContent = document.getElementById(tabName);
    if (targetContent) targetContent.classList.add('active');

    const targetBtn = document.querySelector(`.tab-btn[data-target="${tabName}"]`);
    if (targetBtn) targetBtn.classList.add('active');
}

// Bind Tabs
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        switchTab(e.target.getAttribute('data-target'));
    });
});

// ---------------------------------------------------------
// FASE 3: LÓGICA DE TURNOS, CHAT COM TYPEWRITER E ANIMAÇÕES
// ---------------------------------------------------------

// 1. Sistema de Chat Assíncrono com Auto-scroll
const _chatViewport = document.querySelector('.tab-viewport');

function isNearBottom() {
    if (!_chatViewport) return true;
    return _chatViewport.scrollHeight - _chatViewport.scrollTop - _chatViewport.clientHeight < 80;
}

function scrollToBottom(force) {
    if (!_chatViewport) return;
    if (force || isNearBottom()) {
        _chatViewport.scrollTop = _chatViewport.scrollHeight;
    }
}

// Em JavaScript global as funções declarativamente aqui substituem as da Fase 2 pela ordem de inicialização.
async function addMessage(texto, tipo) {
    const chat = document.querySelector('.chat-history');
    if (!chat) return;
    
    switchTab('tab-log'); // Garante que você esteja olhando o chat
    
    const div = document.createElement('div');
    div.className = `chat-msg ${tipo}`;
    chat.appendChild(div);

    if (tipo === 'player') {
        div.textContent = `> COMANDO: ${texto}`;
        scrollToBottom(true);
        return Promise.resolve();
    } else if (tipo === 'gm') {
        const fmtText = formatLimitedMarkdown(texto);
        div.innerHTML = `<span class="typing-content"></span><span class="blinking-block"></span>`;
        const textSpan = div.querySelector('.typing-content');
        
        let index = 0;
        let isTag = false;
        let charBuffer = "";
        
        return new Promise((resolve) => {
            function typeWriter() {
                if (index < fmtText.length) {
                    const char = fmtText.charAt(index);
                    charBuffer += char;
                    
                    if (char === '<') isTag = true;
                    if (char === '>') isTag = false;
                    
                    textSpan.innerHTML = charBuffer;
                    scrollToBottom();
                    index++;
                    
                    if (isTag) {
                        typeWriter();
                    } else {
                        setTimeout(typeWriter, 30);
                    }
                } else {
                    const cursor = div.querySelector('.blinking-block');
                    if (cursor) cursor.remove();
                    resolve();
                }
            }
            typeWriter();
        });
    }
}

// 2. Chips de Sugestões Interativas
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

function renderChips(opcoes) {
    const container = document.querySelector('.action-chips-container');
    if (!container) return;
    
    clearElement(container);
    
    if(!opcoes || !Array.isArray(opcoes)) return;

    opcoes.forEach(opt => {
        if (typeof opt === 'object' && opt.type === 'separator') return;
        const textStr = typeof opt === 'object' ? (opt.action_label || opt.label || opt.acao) : opt;
        
        const btn = document.createElement('button');
        btn.className = 'action-chip';
        btn.style.opacity = '0';
        btn.textContent = `[→ ${textStr}]`;
        
        btn.addEventListener('click', () => {
            const input = document.querySelector('.cmd-input-field');
            if (input) {
                input.value = textStr;
                pendingStructuredAction = buildTurnPayload(textStr, opt);
                input.focus();
            }
        });

        container.appendChild(btn);
        
        setTimeout(() => {
            btn.style.transition = 'opacity 0.5s ease-in';
            btn.style.opacity = '1';
        }, 100);
    });
}

// Sobrescrevendo helper da Fase 2 para ser redirecionado aos chips novos
window.populateActionChips = renderChips;
window.appendMessage = (role, text) => addMessage(text, role); // garante que chamadas internas usem o Typewriter


// 3. Ciclo Lógico Primário: doAction(texto)
const inputField = document.querySelector('.cmd-input-field');
const btnTransmit = document.querySelector('.btn-transmit');
const loaderOverlay = document.getElementById('loader-overlay');
const pipelineList = document.querySelector('.pipeline-stages');

async function doAction(texto, payload) {
    if (!texto.trim()) return;
    const turnPayload = payload || (
        pendingStructuredAction && pendingStructuredAction.action === texto
            ? pendingStructuredAction
            : { action: texto }
    );
    pendingStructuredAction = null;
    
    // Oculta/Trava interface e lança player msg
    await addMessage(texto, 'player');
    inputField.value = '';
    inputField.disabled = true;
    btnTransmit.disabled = true;
    
    const chipContainer = document.querySelector('.action-chips-container');
    if(chipContainer) clearElement(chipContainer);

    warpStart();
    loaderOverlay.style.display = 'flex';
    clearElement(pipelineList);

    const stages = ["System Engine", "World Ticker", "Architect", "Game Master", "Scene Processor", "Lore Archivist"];
    
    const displayStages = async () => {
        for (const stage of stages) {
            const li = document.createElement('li');
            li.textContent = `> [ ${stage.toUpperCase()} ] Processando dados...`;
            pipelineList.appendChild(li);
            await new Promise(r => setTimeout(r, 2000));
        }
        const exportedLi = document.createElement('li');
        exportedLi.innerHTML = `<span class="glitch" data-text="> EXPORTANDO PACOTE">> EXPORTANDO PACOTE</span>`;
        pipelineList.appendChild(exportedLi);
        await new Promise(r => setTimeout(r, 500));
    };

    const fetchEngine = async () => {
        try {
            const res = await fetch('/api/turn', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(turnPayload)
            });
            return await res.json();
        } catch (err) {
            console.error("Link quebrado.", err);
            return {
                ok: false,
                scene: `[ERRO NA TRANSMISSÃO] O motor neural do servidor Python encontra-se inacessível ou ocorreu Falha Crítica na chamada (503). O ciclo reverterá as interações pendentes.`,
                state: null,
                options: ["TENTAR NOVAMENTE UMA OPÇÃO", "ATIRAR NO TERMINAL"]
            };
        }
    };

    // Bloqueia pelos 12+ segundos visuais exigidos pelo design + latência de API
    const [_, resultState] = await Promise.all([
        displayStages(),
        fetchEngine()
    ]);
    
    warpStop();
    loaderOverlay.style.display = 'none';
    
    triggerGlitch();
    
    setTimeout(async () => {
        if (resultState) {
            if (resultState.error && !resultState.scene) {
                await addMessage(`[ERRO DO MOTOR] ${resultState.error}`, 'gm');
            }
            if (resultState.scene) {
                await addMessage(resultState.scene, 'gm');
            }
            if (resultState.state && resultState.state.character) {
                updateHUD(resultState.state.character, resultState.state.inventory);
                window._lastAttrs = resultState.state.character.attrs || [];
            }
            if (resultState.state && resultState.state.world) {
                updateCoordinates(
                    resultState.state.world.capitulo || 2142,
                    resultState.state.world.ambiente || "X",
                    resultState.state.world.interacoes || 0
                );
            }
            if (resultState.state) {
                updateCodex(resultState.state.bestiary, resultState.state.npc_dossier);
            }
            if (resultState.state && resultState.state.last_roll) {
                updateRoll(resultState.state.last_roll);
            }
            if (resultState.options) {
                renderChips(resultState.options);
            }
        }
        
        inputField.disabled = false;
        btnTransmit.disabled = false;
        inputField.focus();
    }, 1500);
}

// 4. Modais 
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

    clearElement(box);

    const title = makeEl('h2', 'glitch', attrPts > 0 ? 'UPGRADE DE ATRIBUTOS' : 'HABILIDADE PASSIVA');
    title.setAttribute('data-text', title.textContent);
    box.appendChild(title);

    const errorLine = makeEl('p', '', '');
    errorLine.style.color = 'var(--cyber-red)';
    errorLine.style.minHeight = '1.2em';

    if (attrPts > 0) {
        const hint = makeEl('p', '', `Distribua ${attrPts} ponto(s) antes de avançar o turno.`);
        hint.style.color = 'var(--cyber-cyan)';
        box.appendChild(hint);

        const form = makeEl('div', '');
        form.style.display = 'grid';
        form.style.gridTemplateColumns = '1fr 90px';
        form.style.gap = '10px';
        form.style.margin = '18px 0';

        attrs.forEach(attr => {
            const label = makeEl('label', '', `${attr.abbr || attr.key}: ${attr.value}`);
            label.style.textAlign = 'left';
            label.style.color = '#d9fbff';
            const input = document.createElement('input');
            input.type = 'number';
            input.min = '0';
            input.max = String(attrPts);
            input.value = '0';
            input.dataset.attrKey = attr.key;
            input.style.width = '90px';
            input.style.background = 'rgba(0,0,0,0.5)';
            input.style.color = 'var(--cyber-cyan)';
            input.style.border = '1px solid var(--glass-border)';
            input.style.padding = '6px';
            form.appendChild(label);
            form.appendChild(input);
        });

        const actionBtn = makeEl('button', 'btn-transmit', '[APLICAR ATRIBUTOS]');
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
                errorLine.textContent = `Distribua exatamente ${attrPts} ponto(s).`;
                return;
            }
            actionBtn.disabled = true;
            try {
                const res = await fetch('/api/levelup', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ spent })
                });
                const out = await res.json();
                if (!res.ok) throw new Error(out.error || 'Falha ao aplicar atributos.');
                await loadState();
            } catch (err) {
                errorLine.textContent = err.message || String(err);
                actionBtn.disabled = false;
            }
        });

        box.appendChild(form);
        box.appendChild(errorLine);
        box.appendChild(actionBtn);
    } else if (skillPending) {
        const hint = makeEl('p', '', `Escolha ${choicesCount} habilidade(s) passiva(s).`);
        hint.style.color = 'var(--cyber-cyan)';
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
            row.style.border = '1px solid rgba(0,245,255,0.2)';

            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = skill.id;
            const body = makeEl('span', '', `${skill.nome || skill.id} — ${skill.efeito || skill.descricao || ''}`);
            row.appendChild(cb);
            row.appendChild(body);
            list.appendChild(row);
        });

        const actionBtn = makeEl('button', 'btn-transmit', '[CONFIRMAR HABILIDADE]');
        actionBtn.type = 'button';
        actionBtn.disabled = skills.length === 0;
        actionBtn.addEventListener('click', async () => {
            const selected = Array.from(list.querySelectorAll('input:checked')).map(i => i.value);
            if (selected.length !== choicesCount) {
                errorLine.textContent = `Selecione exatamente ${choicesCount} habilidade(s).`;
                return;
            }
            actionBtn.disabled = true;
            try {
                const res = await fetch('/api/skill', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ skill_ids: selected })
                });
                const out = await res.json();
                if (!res.ok) throw new Error(out.error || 'Falha ao aplicar habilidade.');
                await loadState();
            } catch (err) {
                errorLine.textContent = err.message || String(err);
                actionBtn.disabled = false;
            }
        });

        box.appendChild(list);
        box.appendChild(errorLine);
        box.appendChild(actionBtn);
    } else {
        box.appendChild(makeEl('p', '', 'Nenhum upgrade pendente.'));
        const actionBtn = makeEl('button', 'btn-transmit', '[FECHAR]');
        actionBtn.type = 'button';
        actionBtn.addEventListener('click', () => { modal.style.display = 'none'; });
        box.appendChild(actionBtn);
    }

    modal.style.display = 'flex';
}

// 5. Inicialização e Listeners Globais
if (btnTransmit && inputField) {
    btnTransmit.addEventListener('click', () => {
        doAction(inputField.value);
    });
    
    inputField.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            doAction(inputField.value);
        }
    });

    inputField.addEventListener('input', () => {
        if (pendingStructuredAction && inputField.value !== pendingStructuredAction.action) {
            pendingStructuredAction = null;
        }
    });
}

window.addEventListener('DOMContentLoaded', () => {
    console.log("> Iniciando rotinas do Terminal da Nave... v4.0");
    // Kick inicial da UI lendo do servidor
    loadState();
    if (inputField) inputField.focus();
});

