#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
expansion_manager.py — PROTOCOLO DE EXPANSÃO
Chronos RPG Engine v4.0

Responde às duas perguntas do usuário:
  1) "Como a AI cria novos itens e animais?"
  2) "Como a AI salva os novos NPCs/itens?"

FLUXO COMPLETO:
  Python detecta condições → chama Gemini com contexto do mundo →
  Gemini retorna JSON com entidade nova → Python salva nos arquivos reais.

CONDIÇÕES (todas devem ser verdadeiras):
  1. Ação foi exploração ou análise de objeto desconhecido
  2. d20 bruto >= 17
  3. Item/criatura não existe nas tabelas
  4. Compatível com Hard Sci-Fi

USO:
  python expansion_manager.py --type item   --d20 18  --context "explorei ruínas"
  python expansion_manager.py --type criatura --d20 17 --context "área pantanosa"
  python expansion_manager.py --type npc    --d20 17  --context "encontrei sobrevivente"
  python expansion_manager.py --check --d20 14  # apenas verifica se condições passam
"""

import sys, io, os, json, re, argparse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")

_HERE    = os.path.dirname(os.path.abspath(__file__))
_PROJ    = os.path.join(_HERE, "..")
_CTX_DIR = os.path.join(_PROJ, "world_context")

# ── .env ─────────────────────────────────────────────────────────────────────
def _load_env():
    path = os.path.join(_PROJ, ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip(); v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v

_load_env()

try:
    from pydantic import BaseModel, Field # type: ignore
except ImportError:
    print("ERRO: pip install pydantic")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# TABELAS DE TIERS NUMÉRICOS (GUARDRAILS) - Carregados de mechanics_engine.py (I-12)
# ─────────────────────────────────────────────────────────────────────────────

def _load_tiers() -> tuple[dict, dict]:
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("mechanics_engine", os.path.join(_HERE, "mechanics_engine.py"))
    if not _spec or not _spec.loader:
        return {}, {}
    _me = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_me)
    ct = getattr(_me, "CREATURE_TIERS", {})
    it = getattr(_me, "ITEM_TIERS", {})
    if not ct or not it:
        ct = ct or {"fraco": {"hp": 8, "dano": 2, "dc": 10, "bonus_racial": 0, "moral": "40%"}, "medio": {"hp": 15, "dano": 4, "dc": 12, "bonus_racial": 2, "moral": "30%"}, "forte": {"hp": 35, "dano": 8, "dc": 15, "bonus_racial": 4, "moral": "20%"}, "lendario": {"hp": 80, "dano": 15, "dc": 18, "bonus_racial": 6, "moral": "Nunca"}}
        it = it or {"fraco": {"durabilidade": 10, "quantidade_drop": 1, "peso_kg": 0.1}, "medio": {"durabilidade": 25, "quantidade_drop": 2, "peso_kg": 0.5}, "forte": {"durabilidade": 50, "quantidade_drop": 3, "peso_kg": 1.0}, "lendario": {"durabilidade": 100, "quantidade_drop": 1, "peso_kg": 2.0}}
    return ct, it

class ItemExpansion(BaseModel):
    nome: str
    tier: str = Field(description="Deve ser: fraco, medio, forte ou lendario")
    tipo: str
    raridade: str
    efeito: str
    usable: bool
    notas: str
    justificativa: str

class CreatureExpansion(BaseModel):
    nome: str
    tier: str = Field(description="Deve ser: fraco, medio, forte ou lendario")
    classe: str
    arco: int
    tipo_dano: str
    descricao: str
    habitat: str
    comportamento: str
    fraqueza: str
    imunidade: str | None = None
    resistencia: str | None = None
    acerto_critico_efeito: str
    habilidade_especial: str
    drop_item: str = Field(description="Nome do item de drop narrativo")
    justificativa: str

class NpcExpansion(BaseModel):
    nome: str
    funcao: str
    faccao: str
    status: str
    motivacao: str
    notas: str
    justificativa: str

# ─────────────────────────────────────────────────────────────────────────────
# 1. VERIFICAÇÃO DE CONDIÇÕES
# ─────────────────────────────────────────────────────────────────────────────

def check_expansion_conditions(d20_bruto: int, action_type: str) -> dict:
    """
    Verifica se o PROTOCOLO DE EXPANSÃO pode ser ativado.

    Retorna dict com:
      - approved: bool
      - reason: str (por que passou ou falhou)
      - d20: int
    """
    # Condição 1: tipo de ação
    valid_actions = ("exploracao", "explore", "scan", "analise", "investigate")
    action_ok = any(a in action_type.lower() for a in valid_actions)

    # Condição 2: d20 bruto >= 17
    d20_ok = d20_bruto >= 17

    if not action_ok:
        return {
            "approved": False,
            "reason": f"EXPANSAO_NEGADA — ação '{action_type}' não é exploração/análise.",
            "d20": d20_bruto
        }
    if not d20_ok:
        return {
            "approved": False,
            "reason": f"EXPANSAO_NEGADA — d20 bruto {d20_bruto} < 17.",
            "d20": d20_bruto
        }

    raridade = "Raro" if d20_bruto in (17, 18, 19) else "Lendário"
    return {
        "approved": True,
        "reason": f"EXPANSAO_APROVADA — d20={d20_bruto} ({raridade}), ação='{action_type}'.",
        "d20": d20_bruto,
        "raridade": raridade
    }


def check_entity_exists(name: str, entity_type: str) -> bool:
    """
    Verifica se entidade já existe nos arquivos.
    Evita criar duplicatas.
    """
    if not name:
        return False

    name_lower = name.lower()

    if entity_type in ("criatura", "creature"):
        path = os.path.join(_CTX_DIR, "bestiary.md")
    elif entity_type == "npc":
        path = os.path.join(_CTX_DIR, "npc_dossier.md")
    else:  # item
        # Verifica loot_manager.py e inventory.csv
        paths_to_check = [
            os.path.join(_HERE, "loot_manager.py"),
            os.path.join(_PROJ, "current_state", "inventory.csv"),
        ]
        for p in paths_to_check:
            if os.path.exists(p):
                if name_lower in open(p, encoding="utf-8").read().lower():
                    return True
        return False

    if not os.path.exists(path):
        return False
    return name_lower in open(path, encoding="utf-8").read().lower()

def sentinel_heuristic_check(data: dict) -> bool:
    """
    Verifica se o JSON gerado tentou forçar dados abusivos nas strings textuais
    violando as regras de Hard Sci-Fi ou limites de Dano/HP ocultos.
    """
    json_str = json.dumps(data, ensure_ascii=False).lower()
    
    # Block 1: Magia ou divindade (Anti-Hard-Sci-Fi)
    forbidden_words = [
        "magia", "mágica", "mágico", "feitiço", "imortal", "deus", "divino", 
        "infinito", "invencível", "ressurreição", "hit kill", "instakill"
    ]
    for fw in forbidden_words:
        if fw in json_str:
            print(f"  [SENTINEL] Termo proibido detectado: '{fw}'")
            return False
            
    # Block 2: Bypass de status mascarado em texto (ex: "causa 99 de dano")
    # Busca por padrões como "90 dano", "+50 hp", "999 de ataque"
    abusive_pattern = re.compile(r'(\+?\d{2,3})\s*(de)?\s*(dano|hp|vida|ataque|defesa)', re.IGNORECASE)
    match = abusive_pattern.search(json_str)
    if match:
        val = int(match.group(1).replace('+', ''))
        if val > 50: # Threshold generoso para suportar itens de late game (Arco 2/3)
            print(f"  [SENTINEL] Valor numérico em texto muito alto detectado: {match.group(0)}")
            return False

    return True

# ─────────────────────────────────────────────────────────────────────────────
# 2. GERAÇÃO VIA GEMINI
# ─────────────────────────────────────────────────────────────────────────────

def _build_expansion_prompt(entity_type: str, context: str, d20: int, raridade: str) -> str:
    """Constrói o prompt para geração de nova entidade."""

    from world_context_loader import build_world_context_for_expansion  # pyre-ignore[21]
    world_ctx = build_world_context_for_expansion()

    return f"""Você é o PROTOCOLO DE EXPANSÃO do RPG Chronos — um sistema Hard Sci-Fi.

## MISSÃO
Criar uma nova entidade do tipo "{entity_type}" que:
1. NÃO existe nas tabelas atuais (isso já foi verificado)
2. É compatível com Hard Sci-Fi — física real, sem magia, sem tecnologia arbitrária
3. Tem raridade "{raridade}" (d20 bruto = {d20})
4. É coerente com o contexto da descoberta: "{context}"

## CONTEXTO DO MUNDO
{world_ctx}

## REGRAS DE CRIAÇÃO
- Hard Sci-Fi: tudo tem explicação física. Nada de magia.
- Compatível com o arco atual (Arco 1 = selva primitiva, tecnologia mínima)
- Raridade Raro (d20 17-19): incomum mas existente
- Raridade Lendário (d20 20): único, jamais visto antes
- NUNCA crie duplicata de entidade já existente
- A IA NUNCA gera números como HP, Dano ou Quantidade. Apenas escolhe um "tier" (fraco, medio, forte, lendario) e gera a narrativa e os atributos textuais.

Todos os campos são obrigatórios no output estruturado. Se desconhecido, use "???" — nunca deixe null onde não faz sentido."""


def call_gemini_expansion(prompt: str, entity_type: str) -> dict:
    """Chama Gemini para gerar nova entidade com retry e schema."""
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
    except ImportError:
        print("ERRO: pip install google-genai")
        return {}

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("ERRO: GEMINI_API_KEY não definida em .env")
        return {}

    target_schema = None
    if entity_type == "item":
        target_schema = ItemExpansion
    elif entity_type == "criatura":
        target_schema = CreatureExpansion
    else:
        target_schema = NpcExpansion

    client = genai.Client(api_key=api_key)

    base_temp = 0.75
    last_text = ""
    for attempt in range(3):
        try:
            temp = base_temp + (attempt * 0.05)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction="Você é um gerador de conteúdo para RPG Hard Sci-Fi. Responda estritamente seguindo o schema.",
                    temperature=temp,
                    max_output_tokens=1500,
                    response_mime_type="application/json",
                    response_schema=target_schema,
                ),
            )
            raw = response.text.strip()
            return json.loads(raw)
        except Exception as e:
            try: last_text = response.text
            except: last_text = str(e)
            print(f"Tentativa {attempt+1} falhou - {e}")
    print("TODAS AS TENTATIVAS FALHARAM. Salvando output bruto.")
    fail_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "drafts", "expansion_raw_fail.txt")
    os.makedirs(os.path.dirname(fail_path), exist_ok=True)
    with open(fail_path, "w", encoding="utf-8") as f:
        f.write(last_text)
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# 3. SALVAMENTO NOS ARQUIVOS REAIS
#    Esta é a resposta à pergunta: "Como a AI salva novos NPCs/itens?"
#
#    Gemini gera o JSON → Python lê cada campo → Python escreve nos arquivos.
#    A IA nunca escreve diretamente — ela DESCREVE o que criar.
#    Python executa a escrita com validação.
# ─────────────────────────────────────────────────────────────────────────────

def save_new_item(data: dict) -> bool:
    """
    Salva novo item em:
    1. loot_manager.py  (ITEM_SCHEMA dict)
    2. Retorna True para que o Architect adicione ao inventory.csv
    """
    nome = data.get("nome", "").strip()
    if not nome:
        print("ERRO: item sem nome")
        return False

    loot_path = os.path.join(_HERE, "loot_manager.py")
    if not os.path.exists(loot_path):
        print(f"ERRO: {loot_path} não encontrado")
        return False

    # Verifica se já existe
    if check_entity_exists(nome, "item"):
        print(f"  ⚠ Item '{nome}' já existe — expansão cancelada.")
        return False

    _, ITEM_TIERS = _load_tiers()
    tier_name = data.get("tier", "medio").lower()
    if tier_name not in ITEM_TIERS:
        tier_name = "medio"
    item_tier = ITEM_TIERS.get(tier_name, {})

    entry = f"""    '{nome}': {{
        'type': '{data.get("tipo", "Material")}',
        'rarity': '{data.get("raridade", "Raro")}',
        'weight_kg': {item_tier['peso_kg']},
        'effect': '{data.get("efeito", "Efeito desconhecido.")}',
        'usable': {str(data.get("usable", False))},
        'notes': '{data.get("notas", "")}',
        'durabilidade': {item_tier['durabilidade']},
        'quantidade_drop': {item_tier['quantidade_drop']}
    }},"""

    # Insere no ITEM_SCHEMA — busca pela linha de fechamento do dict
    content = open(loot_path, encoding="utf-8").read()

    # Procura o marcador de inserção de novos itens
    marker = "# ── EXPANSÃO: novos itens adicionados pelo expansion_manager ──"
    if marker in content:
        content = content.replace(marker, f"{marker}\n{entry}")
    else:
        # Fallback: insere antes do último } do ITEM_SCHEMA
        # Procura "ITEM_SCHEMA = {" e adiciona antes do fechamento
        pattern = r'(ITEM_SCHEMA\s*=\s*\{.*?)(^\})'
        match = re.search(pattern, content, re.DOTALL | re.MULTILINE)
        if match:
            insert_pos = match.end(1)
            # pyre-ignore[6, 58]
            content = content[:insert_pos] + f"\n{entry}\n    # FIM ITEM_SCHEMA\n" + content[insert_pos:]
        else:
            # Último recurso: appenda ao arquivo
            content += f"\n\n# ITEM ADICIONADO PELO expansion_manager\n# {nome}\n# {entry}\n"

    with open(loot_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"  ✓ Item '{nome}' salvo em loot_manager.py")
    return True


def save_new_creature(data: dict) -> bool:
    """
    Salva nova criatura em bestiary.md e retorna o bloco para
    que o Architect preencha o active_combat.json se necessário.
    """
    nome = data.get("nome", "").strip()
    if not nome:
        print("ERRO: criatura sem nome")
        return False

    if check_entity_exists(nome, "criatura"):
        print(f"  ⚠ Criatura '{nome}' já existe no bestiário — expansão cancelada.")
        return False

    CREATURE_TIERS, _ = _load_tiers()
    tier_name = data.get("tier", "medio").lower()
    if tier_name not in CREATURE_TIERS:
        tier_name = "medio"
    ct = CREATURE_TIERS.get(tier_name, {})

    bestiary_block = f"""---
## Nome: {nome}

**HP:** {ct["hp"]} / {ct["hp"]}

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 10 |
| Destreza (DES) | 10 |
| Inteligência (INT) | 10 |
| Sobrevivência (SOB) | 10 |
| Percepção (PER) | 10 |
| Carisma (CAR) | 10 |

### Combate
- **DC de Defesa:** {ct["dc"]}
- **Dano por Turno:** {ct["dano"]} *(tipo: {data.get("tipo_dano", "Físico")})*
- **Bônus Racial de Dano:** {ct["bonus_racial"]}
- **Acerto Crítico:** {data.get("acerto_critico_efeito", "Nenhum efeito especial.")}
- **Threshold Moral:** {ct["moral"]}
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** {data.get("classe", "Biológico")}
- **Arco / Capítulo:** Arco {data.get("arco", "?")} — adicionado via PROTOCOLO DE EXPANSÃO
- **Habitat:** {data.get("habitat", "???")}
- **Comportamento:** {data.get("comportamento", "???")}
- **Fraqueza:** {data.get("fraqueza", "???")}
- **Imunidade:** {data.get("imunidade") or "Nenhuma"}
- **Resistência:** {data.get("resistencia") or "Nenhuma"}
- **Drop (Loot):** {data.get("drop_item", "Nenhum")}
"""

    # Importa e usa a função de append
    import sys as _sys
    _sys.path.insert(0, _HERE)
    from world_context_loader import append_to_bestiary  # pyre-ignore[21]
    append_to_bestiary(bestiary_block)

    print(f"  ✓ Criatura '{nome}' salva em bestiary.md")
    # data["hp"/"dc_defesa"/"dano_por_turno"] não existem no Gemini response (CreatureExpansion).
    # Os valores reais vêm de CREATURE_TIERS[tier] — usar ct para o print correto.
    tier_name_print = data.get("tier", "medio").lower()
    if tier_name_print not in CREATURE_TIERS:
        tier_name_print = "medio"
    ct_print = CREATURE_TIERS.get(tier_name_print, {})
    if ct_print:
        print(f"  → HP: {ct_print.get('hp')} | DC: {ct_print.get('dc')} | Dano: {ct_print.get('dano')} | Tier: {tier_name_print}")
    return True


def save_new_npc(data: dict) -> bool:
    """
    Salva novo NPC em npc_dossier.md.
    """
    nome = data.get("nome", "").strip()
    if not nome:
        print("ERRO: NPC sem nome")
        return False

    if check_entity_exists(nome, "npc"):
        print(f"  ⚠ NPC '{nome}' já existe no dossier — expansão cancelada.")
        return False

    npc_block = data.get("npc_block", "")
    if not npc_block:
        npc_block = f"""**{nome}**
- **Função:** {data.get("funcao", "Desconhecida")}
- **Facção:** {data.get("faccao", "Desconhecida")}
- **Status:** `{data.get("status", "NEUTRO")}`
- **Motivação Conhecida:** {data.get("motivacao", "Desconhecida")}
- **Notas:** {data.get("notas", "Adicionado via PROTOCOLO DE EXPANSÃO.")}"""

    import sys as _sys
    _sys.path.insert(0, _HERE)
    from world_context_loader import update_npc_dossier  # pyre-ignore[21]
    update_npc_dossier(nome, npc_block)

    print(f"  ✓ NPC '{nome}' salvo em npc_dossier.md")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# 4. FUNÇÃO PRINCIPAL (chamada pelo run_turn.py ou architect.py)
# ─────────────────────────────────────────────────────────────────────────────

def run_expansion(
    d20_bruto: int,
    action_type: str,
    context: str,
    entity_type: str = "auto",
    dry_run: bool = False
) -> dict:
    """
    Ponto de entrada principal do PROTOCOLO DE EXPANSÃO.

    Args:
        d20_bruto:   valor bruto do dado (sem modificador de atributo)
        action_type: tipo de ação ("explore", "scan", "analise", etc.)
        context:     descrição do que foi encontrado/explorado
        entity_type: "item" | "criatura" | "npc" | "auto" (Gemini decide)
        dry_run:     se True, apenas mostra o que faria sem salvar

    Retorna dict com resultado da expansão.
    """
    print("\n" + "="*55)
    print("  PROTOCOLO DE EXPANSÃO")
    print("="*55)

    # Verifica condições
    check = check_expansion_conditions(d20_bruto, action_type)
    print(f"  {check['reason']}")

    if not check["approved"]:
        return {"status": "NEGADO", "reason": check["reason"]}

    raridade = check.get("raridade", "Raro")

    # Se entity_type = "auto", decide baseado no contexto
    if entity_type == "auto":
        ctx_lower = context.lower()
        if any(w in ctx_lower for w in ["criatura", "animal", "ser", "fera", "monstro", "rasteja"]):
            entity_type = "criatura"
        elif any(w in ctx_lower for w in ["pessoa", "humano", "sobrevivente", "figura", "voz"]):
            entity_type = "npc"
        else:
            entity_type = "item"
        print(f"  Auto-detectado: tipo = {entity_type}")

    print(f"  Gerando {entity_type} via Gemini... (raridade: {raridade})")

    if dry_run:
        print("  [DRY RUN — sem chamada ao Gemini e sem salvamento]")
        return {"status": "DRY_RUN", "entity_type": entity_type, "raridade": raridade}

    # Gera via Gemini
    prompt = _build_expansion_prompt(entity_type, context, d20_bruto, raridade)
    data   = call_gemini_expansion(prompt, entity_type)

    if not data:
        return {"status": "ERRO", "reason": "Gemini não retornou dados"}

    nome = data.get("nome", "???")
    print(f"\n  Entidade gerada: '{nome}'")
    print(f"  Justificativa: {data.get('justificativa', '—')}")

    # Verifica se já existe (condição 3 do protocolo)
    if check_entity_exists(nome, entity_type):
        print(f"  ⚠ '{nome}' já existe. EXPANSAO_NEGADA (condição 3).")
        return {"status": "NEGADO", "reason": f"'{nome}' já existe nas tabelas."}

    # Sentinel Heuristic Check (Anti-Power Creep)
    if not sentinel_heuristic_check(data):
        print(f"  ⚠ '{nome}' foi rejeitado pela heurística anti-creep. EXPANSAO_NEGADA.")
        return {"status": "NEGADO", "reason": f"A narrativa da IA violou regras de balanceamento para '{nome}'."}

    if dry_run:
        print("  [DRY RUN — não salvando]")
        print(f"  Prévia:\n{json.dumps(data, ensure_ascii=False, indent=2)}")
        return {"status": "DRY_RUN", "data": data}

    # Salva nos arquivos reais
    print("\n  Salvando...")
    saved = False
    if entity_type == "item":
        saved = save_new_item(data)
    elif entity_type == "criatura":
        saved = save_new_creature(data)
    elif entity_type == "npc":
        saved = save_new_npc(data)

    if saved:
        print(f"\n  ✓ PROTOCOLO DE EXPANSÃO CONCLUÍDO: '{nome}' adicionado ao universo.")
        return {
            "status": "ATIVADO",
            "entity_type": entity_type,
            "nome": nome,
            "data": data,
            "raridade": raridade
        }
    else:
        return {"status": "ERRO", "reason": "Falha ao salvar entidade"}


# ─────────────────────────────────────────────────────────────────────────────
# 5. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(prog="expansion_manager.py")
    parser.add_argument("--type", default="auto",
                        choices=["item","criatura","npc","auto"],
                        help="Tipo de entidade a criar")
    parser.add_argument("--d20", type=int, required=True,
                        help="Valor bruto do d20 (sem modificador)")
    parser.add_argument("--action", default="explore",
                        help="Tipo de ação ('explore', 'scan', 'analise'...)")
    parser.add_argument("--context", default="",
                        help="Descrição do que foi encontrado/explorado")
    parser.add_argument("--check", action="store_true",
                        help="Apenas verifica condições sem gerar")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula sem chamar Gemini nem salvar arquivos")
    args = parser.parse_args()

    if args.check:
        result = check_expansion_conditions(args.d20, args.action)
        print(result["reason"])
        return

    result = run_expansion(
        d20_bruto=args.d20,
        action_type=args.action,
        context=args.context,
        entity_type=args.type,
        dry_run=args.dry_run
    )
    print(f"\n  Status final: {result.get('status')}")


if __name__ == "__main__":
    main()