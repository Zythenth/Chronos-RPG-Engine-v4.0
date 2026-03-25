#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scene_processor.py — Passo 3.5: Extrator de Deltas Narrativos
Chronos RPG Engine v4.0

RESPONSABILIDADE:
  Le a cena gerada pelo Game_Master e extrai deltas de vitais/inventario
  usando uma chamada Gemini separada, pequena e focada (temperature=0, JSON puro).

FLUXO:
  Passo 3 (GM) -> current_scene.md -> Passo 3.5 (este) -> aplica deltas -> Passo 4 (Archivist)

USO como modulo (web_server.py):
  from scene_processor import run as sp_run
  logs = sp_run()

USO como CLI:
  python scene_processor.py
  python scene_processor.py --dry-run
"""

import sys, io, os, json, csv, re, argparse, traceback

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore

_HERE      = os.path.dirname(os.path.abspath(__file__))
_PROJ      = os.path.join(_HERE, "..")
_STATE_DIR = os.path.join(_PROJ, "current_state")
_DRAFT_DIR = os.path.join(_PROJ, "drafts")

_CS_PATH     = os.path.join(_STATE_DIR, "character_sheet.json")
_INV_PATH    = os.path.join(_STATE_DIR, "inventory.csv")
_SCENE_PATH  = os.path.join(_DRAFT_DIR, "current_scene.md")
_REPORT_PATH = os.path.join(_DRAFT_DIR, "scene_processor_report.txt")

_INV_FIELDNAMES = [
    "id", "name", "type", "rarity", "quantity",
    "weight_kg", "effect", "usable", "durability", "durability_max", "notes",
]


# Carrega .env tanto ao importar quanto ao rodar como script
def _load_env() -> None:
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

_load_env()  # executa sempre, mesmo ao importar


def _read(path: str, default: str = "") -> str:
    if not os.path.exists(path):
        return default
    return open(path, encoding="utf-8").read()


def _read_json(path: str) -> dict:
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return {}


def _read_csv(path: str) -> list:
    try:
        return list(csv.DictReader(open(path, encoding="utf-8")))
    except Exception:
        return []


# =============================================================================
# Prompt do extrator
# =============================================================================

EXTRACTOR_PROMPT = """Voce e um extrator de dados para um RPG de sobrevivencia sci-fi.

Recebera uma cena narrativa e o estado atual do personagem.
Sua tarefa: identificar APENAS eventos explicitamente descritos na cena que causam
mudancas imediatas nos vitais ou no inventario DO PERSONAGEM PRINCIPAL.

IGNORAR COMPLETAMENTE:
- Decay automatico de fome/sede/exaustao (isso ja acontece por turno)
- Dano de combate (ja processado pelo system_engine)
- Eventos hipoteticos ou futuros
- Tentativas FRACASSADAS de usar itens (ex: "tentativa inutil", "falhou", "nao funcionou")
- Item que foi CONSUMIDO/USADO (o sistema ja decrementou a quantidade)

REGISTRAR SE EXPLICITAMENTE DESCRITO:
- Personagem bebe agua/liquido                -> sede: +15 a +35
- Personagem come algo                        -> fome: +15 a +35
- Personagem descansa (nao apenas senta)      -> exaustao: +15 a +30
- Personagem carrega chip/bateria             -> energia: +20 a +50
- Personagem ENCONTRA ou PEGA item fisico     -> itens_adicionados
- Personagem CRAFT/CRIA item com sucesso      -> itens_adicionados (1 objeto por item criado)
- Dano externo nao-combate (queda, acido)     -> hp: negativo

ESCALA DE VALORES:
- Evento rapido (gole, mordida):    10 a 20
- Evento normal (beber, refeicao):  20 a 35
- Evento intenso (descanso longo):  35 a 55

RESPONDA SOMENTE EM JSON VALIDO. Sem texto extra, sem markdown:
{
  "fome": 0,
  "sede": 0,
  "exaustao": 0,
  "energia": 0,
  "hp": 0,
  "itens_adicionados": [],
  "justificativa": "breve descricao do evento, ou Nenhum evento relevante"
}

SCHEMA OBRIGATORIO para cada objeto em itens_adicionados.
Preencha TODOS os campos — nenhum pode ficar em branco ou ser omitido:
{
  "nome":             "Nome exato do item (string nao vazia)",
  "tipo":             "consumivel|recurso|material|arma|armadura|equipamento passivo|quest",
  "raridade":         "comum|incomum|raro|epico|lendario",
  "quantidade":       "1",
  "peso_kg":          "0.1",
  "efeito":           "efeito ao usar, ou string vazia se nao aplicavel",
  "usavel":           "true|false",
  "durabilidade":     "null",
  "durabilidade_max": "null",
  "notas":            "contexto narrativo de onde/como o item foi obtido"
}

EXEMPLOS CORRETOS:
Item encontrado:
{"nome":"Faca Enferrujada","tipo":"arma","raridade":"comum","quantidade":"1","peso_kg":"0.4","efeito":"+1 dano melee","usavel":"true","durabilidade":"5","durabilidade_max":"10","notas":"Encontrada no chao da selva"}

Item coletado:
{"nome":"Biomassa Esverdeada","tipo":"recurso","raridade":"comum","quantidade":"1","peso_kg":"0.3","efeito":"","usavel":"false","durabilidade":"null","durabilidade_max":"null","notas":"Coletada das plantas da selva"}

Item criado via craft:
{"nome":"Injetor Medico","tipo":"consumivel","raridade":"incomum","quantidade":"1","peso_kg":"0.3","efeito":"+10 HP se usado como acao","usavel":"true","durabilidade":"null","durabilidade_max":"null","notas":"Criado via Kit de Sintese Improvisado"}

Se nenhum evento relevante ocorreu: todos os numeros = 0, lista vazia."""



# =============================================================================
# Prompt de reparo de item inválido
# =============================================================================

REPAIR_PROMPT = """Voce e um validador de schema de itens para um RPG sci-fi.

Recebera um item JSON com erros e a lista de erros encontrados.
Sua tarefa: corrigir APENAS os campos com erro. Nao altere campos validos.

SCHEMA OBRIGATORIO (todos os 10 campos devem existir e ser validos):
{
  "nome":             "string nao vazia",
  "tipo":             "consumivel|recurso|material|arma|armadura|equipamento passivo|quest",
  "raridade":         "comum|incomum|raro|epico|lendario",
  "quantidade":       "string numerica >= 1",
  "peso_kg":          "string numerica > 0",
  "efeito":           "string (pode ser vazia)",
  "usavel":           "true ou false (string)",
  "durabilidade":     "null ou string numerica (obrigatorio numerico se tipo=arma ou armadura)",
  "durabilidade_max": "null ou string numerica (obrigatorio numerico se tipo=arma ou armadura)",
  "notas":            "string (pode ser vazia)"
}

REGRAS DE CORRECAO:
- tipo invalido -> inferir pelo nome/efeito, ou usar "material" como fallback
- raridade invalida -> usar "comum"
- quantidade invalida -> usar "1"
- peso_kg invalido -> usar "0.1"
- usavel invalido -> "true" se tipo consumivel/arma/armadura, senao "false"
- durabilidade/durabilidade_max null em arma/armadura -> usar "10"/"10"
- durabilidade/durabilidade_max com valor em nao-arma -> converter para "null"

RESPONDA SOMENTE COM O JSON DO ITEM CORRIGIDO. Sem texto extra, sem markdown."""

# =============================================================================
# Validação e reparo de item
# =============================================================================

_TIPOS_VALIDOS     = {"consumivel", "recurso", "material", "arma", "armadura", "equipamento passivo", "quest"}
_RARIDADES_VALIDAS = {"comum", "incomum", "raro", "epico", "lendario"}
_TIPOS_COM_DURABILIDADE = {"arma", "armadura"}


def _is_numeric(value: str) -> bool:
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def _validate_item(item: dict) -> list:
    """
    Valida um item contra o schema canonico.
    Retorna lista de strings descrevendo cada erro encontrado.
    Lista vazia = item valido.
    """
    erros = []

    nome = str(item.get("nome", "")).strip()
    if not nome:
        erros.append("campo 'nome' vazio ou ausente")

    tipo = str(item.get("tipo", "")).strip().lower()
    if tipo not in _TIPOS_VALIDOS:
        erros.append(f"campo 'tipo' invalido: '{tipo}' — valores aceitos: {sorted(_TIPOS_VALIDOS)}")

    raridade = str(item.get("raridade", "")).strip().lower()
    if raridade not in _RARIDADES_VALIDAS:
        erros.append(f"campo 'raridade' invalido: '{raridade}' — valores aceitos: {sorted(_RARIDADES_VALIDAS)}")

    try:
        qty = int(str(item.get("quantidade", "1")).strip())
        if qty < 1:
            erros.append(f"campo 'quantidade' deve ser >= 1, recebido: {qty}")
    except (ValueError, TypeError):
        erros.append(f"campo 'quantidade' nao e numerico: '{item.get('quantidade')}'")

    try:
        peso = float(str(item.get("peso_kg", "0.1")).strip())
        if peso <= 0:
            erros.append(f"campo 'peso_kg' deve ser > 0, recebido: {peso}")
    except (ValueError, TypeError):
        erros.append(f"campo 'peso_kg' nao e numerico: '{item.get('peso_kg')}'")

    if "efeito" not in item:
        erros.append("campo 'efeito' ausente")

    usavel = str(item.get("usavel", "")).strip().lower()
    if usavel not in ("true", "false"):
        erros.append(f"campo 'usavel' invalido: '{usavel}' — aceito: 'true' ou 'false'")

    dur     = str(item.get("durabilidade",     "null")).strip()
    dur_max = str(item.get("durabilidade_max", "null")).strip()

    if tipo in _TIPOS_COM_DURABILIDADE:
        if not _is_numeric(dur):
            erros.append(f"tipo '{tipo}' exige 'durabilidade' numerica, recebido: '{dur}'")
        if not _is_numeric(dur_max):
            erros.append(f"tipo '{tipo}' exige 'durabilidade_max' numerica, recebido: '{dur_max}'")
    else:
        if dur not in ("null", "None", "") and _is_numeric(dur) and float(dur) != 0:
            erros.append(f"tipo '{tipo}' deve ter 'durabilidade' null, recebido: '{dur}'")
        if dur_max not in ("null", "None", "") and _is_numeric(dur_max) and float(dur_max) != 0:
            erros.append(f"tipo '{tipo}' deve ter 'durabilidade_max' null, recebido: '{dur_max}'")

    if "notas" not in item:
        erros.append("campo 'notas' ausente")

    return erros


def _repair_item_via_gemini(item: dict, erros: list) -> tuple:
    """
    Envia o item com erros ao Gemini Flash para corrigir.
    Retorna (item_corrigido_dict, erro_str).
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return {}, "ERRO: google-genai nao instalado"

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {}, "ERRO: GEMINI_API_KEY ausente"

    client = genai.Client(api_key=api_key)
    user_msg = (
        f"ITEM COM ERROS:\n{json.dumps(item, ensure_ascii=False, indent=2)}\n\n"
        f"ERROS ENCONTRADOS:\n" + "\n".join(f"- {e}" for e in erros)
    )

    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(
                system_instruction=REPAIR_PROMPT,
                temperature=0.0,
                max_output_tokens=600,
                response_mime_type="application/json",
            ),
        )
        raw = (resp.text or "").strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"```$", "", raw).strip()
        repaired = json.loads(raw)
        if not isinstance(repaired, dict):
            return {}, "Gemini retornou formato invalido no reparo"
        return repaired, ""
    except Exception as e:
        err = str(e)
        if "503" in err or "UNAVAILABLE" in err:
            return {}, "Gemini 503 UNAVAILABLE"
        if "429" in err:
            return {}, "Gemini 429 rate limit"
        return {}, f"Erro no reparo: {err}"


def _validate_and_repair(items: list, log: list) -> list:
    """
    Para cada item:
      1. Valida contra o schema (Python puro, sem IA)
      2. Se invalido → repara via Gemini Flash
      3. Valida novamente → descarta se ainda invalido
    Retorna lista de itens validos.
    """
    validos = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            log.append(f"[SP] VALIDACAO: item #{i+1} ignorado — nao e dict")
            continue

        nome_display = str(item.get("nome", f"item#{i+1}"))
        erros = _validate_item(item)

        if not erros:
            log.append(f"[SP] VALIDACAO OK: '{nome_display}'")
            validos.append(item)
            continue

        log.append(f"[SP] VALIDACAO FALHOU: '{nome_display}' — {len(erros)} erro(s):")
        for e in erros:
            log.append(f"[SP]   → {e}")
        log.append(f"[SP] REPARO: enviando '{nome_display}' ao Gemini Flash...")

        repaired, err_repair = _repair_item_via_gemini(item, erros)

        if err_repair:
            log.append(f"[SP] REPARO FALHOU: {err_repair} — '{nome_display}' descartado")
            continue

        erros_pos = _validate_item(repaired)
        if erros_pos:
            log.append(f"[SP] REPARO INSUFICIENTE: '{nome_display}' ainda invalido — descartado")
            for e in erros_pos:
                log.append(f"[SP]   → {e}")
            continue

        nome_reparado = str(repaired.get("nome", nome_display))
        log.append(f"[SP] REPARO OK: '{nome_reparado}' corrigido e aceito")
        validos.append(repaired)

    return validos

# =============================================================================
# Chamada Gemini
# =============================================================================

def _call_gemini(scene: str, vitals_ctx: str) -> tuple:
    """
    Retorna (dict, erro_str).
    Sucesso: (data_dict, "")
    Falha:   ({}, "mensagem de erro")
    """
    try:
        from google import genai       # type: ignore
        from google.genai import types # type: ignore
    except ImportError:
        return {}, "ERRO: google-genai nao instalado (pip install google-genai)"

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {}, "ERRO: GEMINI_API_KEY nao encontrada no ambiente nem no .env"

    client = genai.Client(api_key=api_key)
    user_msg = (
        f"CENA NARRATIVA:\n{scene}\n\n"
        f"VITAIS ATUAIS (referencia):\n{vitals_ctx}"
    )

    last_err = ""
    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_msg,
                config=types.GenerateContentConfig(
                    system_instruction=EXTRACTOR_PROMPT,
                    temperature=0.0,
                    max_output_tokens=1200,  # ampliado para suportar multiplos itens com schema completo
                    response_mime_type="application/json",
                ),
            )
            raw = (resp.text or "").strip()
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"```$", "", raw).strip()
            data = json.loads(raw)
            return data, ""
        except Exception as e:
            last_err = str(e)
            if "503" in last_err or "UNAVAILABLE" in last_err:
                return {}, "Gemini 503 UNAVAILABLE"
            if "429" in last_err:
                return {}, "Gemini 429 rate limit"

    return {}, f"Gemini falhou apos 3 tentativas: {last_err}"


# =============================================================================
# Helpers de vitais
# =============================================================================

def _get_vital(vitals: dict, key: str) -> int:
    vd = vitals.get(key, {})
    if isinstance(vd, dict):
        try:
            return int(vd.get("current", 100))
        except Exception:
            return 100
    try:
        return int(vd)
    except Exception:
        return 100


def _get_vital_max(vitals: dict, key: str) -> int:
    vd = vitals.get(key, {})
    if isinstance(vd, dict):
        try:
            return int(vd.get("max", 100))
        except Exception:
            return 100
    return 100


def _set_vital(vitals: dict, key: str, new_val: int) -> None:
    """Seta vital com clamping. Preserva todos os campos existentes."""
    if key not in vitals:
        vitals[key] = {"current": 100, "max": 100}
    vd = vitals[key]
    if not isinstance(vd, dict):
        vitals[key] = {"current": int(new_val), "max": 100}
        return
    mx = int(vd.get("max", 100))
    vd["current"] = max(0, min(int(new_val), mx))


_VITAL_KEY_MAP = {
    "fome":     "fome",
    "sede":     "sede",
    "exaustao": "exaustao",
    "energia":  "energy_reserves",
    "hp":       "hp",
}


# =============================================================================
# Aplicacao dos deltas
# =============================================================================

def apply_deltas(data: dict, dry_run: bool = False) -> list:
    """
    Aplica deltas no character_sheet.json e inventory.csv.
    Retorna lista de strings de log.
    NUNCA lanca excecao — erros sao capturados e retornados como log.
    """
    log: list = []

    if not data:
        log.append("[SP] Nenhum dado para aplicar.")
        return log

    justificativa = str(data.get("justificativa", "")).strip()
    log.append(f"[SP] Gemini: {justificativa or 'sem justificativa'}")

    # Normaliza deltas — Gemini as vezes retorna float
    vitals_deltas: dict = {}
    for field in _VITAL_KEY_MAP:
        try:
            v = data.get(field, 0)
            vitals_deltas[field] = int(float(v)) if v is not None else 0
        except Exception:
            vitals_deltas[field] = 0

    itens: list = data.get("itens_adicionados", []) or []
    if not isinstance(itens, list):
        itens = []

    has_vital = any(v != 0 for v in vitals_deltas.values())
    has_items = len(itens) > 0

    if not has_vital and not has_items:
        log.append("[SP] Nenhuma mudanca detectada — nenhum arquivo alterado.")
        return log

    # Carrega arquivos
    try:
        cs = _read_json(_CS_PATH)
        if not cs:
            log.append(f"[SP] AVISO: character_sheet.json vazio ou nao encontrado: {_CS_PATH}")
            return log
    except Exception as e:
        log.append(f"[SP] ERRO ao ler character_sheet.json: {e}")
        return log

    try:
        inv = _read_csv(_INV_PATH)
    except Exception as e:
        log.append(f"[SP] AVISO: inventory.csv nao lido: {e}")
        inv = []

    vitals    = cs.setdefault("vitals", {})
    cs_dirty  = False
    inv_dirty = False

    # ── Aplica vitais ────────────────────────────────────────────────────────
    for field, cs_key in _VITAL_KEY_MAP.items():
        delta = vitals_deltas.get(field, 0)
        if delta == 0:
            continue
        old      = _get_vital(vitals, cs_key)
        vmax     = _get_vital_max(vitals, cs_key)
        clamped  = max(0, min(old + delta, vmax))
        sign     = "+" if delta >= 0 else ""
        prefix   = "[DRY] " if dry_run else ""
        log.append(f"[SP] {prefix}{cs_key}: {old} -> {clamped} ({sign}{delta})")
        if not dry_run:
            _set_vital(vitals, cs_key, old + delta)
            cs_dirty = True

    # ── Aplica itens ─────────────────────────────────────────────────────────
    for item in itens:
        if not isinstance(item, dict):
            continue
        try:
            # Aceita nomes em portugues (schema novo) e ingles (legado)
            nome      = str(item.get("nome",             item.get("name",           "Item"))).strip()
            tipo      = str(item.get("tipo",             item.get("type",           "material"))).strip().lower()
            raridade  = str(item.get("raridade",         item.get("rarity",         "comum"))).strip().lower()
            peso      = str(item.get("peso_kg",          item.get("weight_kg",      "0.1"))).strip()
            efeito    = str(item.get("efeito",           item.get("effect",         ""))).strip()
            usavel    = str(item.get("usavel",           item.get("usable",         "false"))).strip().lower()
            dur       = str(item.get("durabilidade",     item.get("durability",     "null"))).strip()
            dur_max   = str(item.get("durabilidade_max", item.get("durability_max", "null"))).strip()
            notas     = str(item.get("notas",            item.get("notes",          "Obtido via narrativa"))).strip()

            # Quantidade: Gemini pode sugerir mais de 1 (ex: craft produz 2 unidades)
            try:
                qty_nova = max(1, int(str(item.get("quantidade", item.get("quantity", "1"))).strip()))
            except Exception:
                qty_nova = 1

            # Sanitiza campos
            if usavel not in ("true", "false"):
                usavel = "true" if tipo in ("consumivel", "arma", "armadura") else "false"
            if dur in ("", "None"):
                dur = "null"
            if dur_max in ("", "None"):
                dur_max = "null"
            if not nome:
                log.append("[SP] AVISO: item sem nome ignorado")
                continue

            prefix = "[DRY] " if dry_run else ""

            # Empilha se ja existe no inventario (compara nome case-insensitive)
            found = False
            for row in inv:
                if str(row.get("name", "")).lower() == nome.lower():
                    try:
                        old_qty = int(str(row.get("quantity", 0)).strip())
                        row["quantity"] = str(old_qty + qty_nova)
                    except Exception:
                        row["quantity"] = str(qty_nova)
                    log.append(f"[SP] {prefix}INV +{qty_nova}x {nome} (empilhado — total {row['quantity']})")
                    found = True
                    break

            if not found:
                # Gera novo ID: max(ids existentes) + 1
                eids: list = []
                for row in inv:
                    try:
                        eids.append(int(row.get("id", 0)))
                    except Exception:
                        pass
                new_id = str(max(eids, default=0) + 1)
                inv.append({
                    "id":             new_id,
                    "name":           nome,
                    "type":           tipo,
                    "rarity":         raridade,
                    "quantity":       str(qty_nova),
                    "weight_kg":      peso,
                    "effect":         efeito,
                    "usable":         usavel,
                    "durability":     dur,
                    "durability_max": dur_max,
                    "notes":          notas,
                })
                ef_txt = f" — {efeito}" if efeito else ""
                log.append(f"[SP] {prefix}INV ADD [id={new_id}]: {qty_nova}x {nome} ({tipo}/{raridade}){ef_txt}")
            inv_dirty = True
        except Exception as e:
            log.append(f"[SP] AVISO: erro ao processar item: {e}")

    # ── Salva ────────────────────────────────────────────────────────────────
    if dry_run:
        log.append("[SP] DRY RUN — nenhum arquivo foi alterado.")
        return log

    if cs_dirty:
        try:
            with open(_CS_PATH, "w", encoding="utf-8") as f:
                json.dump(cs, f, ensure_ascii=False, indent=2)
            log.append("[SP] character_sheet.json salvo com sucesso.")
        except Exception as e:
            log.append(f"[SP] ERRO ao salvar character_sheet.json: {e}")
            log.append(traceback.format_exc())

    if inv_dirty:
        try:
            fieldnames = list(inv[0].keys()) if inv else _INV_FIELDNAMES
            with open(_INV_PATH, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore",
                                   quoting=csv.QUOTE_ALL)
                w.writeheader()
                w.writerows(inv)
            log.append("[SP] inventory.csv salvo com sucesso.")
        except Exception as e:
            log.append(f"[SP] ERRO ao salvar inventory.csv: {e}")

    return log


# =============================================================================
# Contexto de vitais atual
# =============================================================================

def _build_vitals_context() -> str:
    cs  = _read_json(_CS_PATH)
    v   = cs.get("vitals", {})
    hp      = _get_vital(v, "hp")
    hp_max  = _get_vital_max(v, "hp")
    fome    = _get_vital(v, "fome")
    sede    = _get_vital(v, "sede")
    exau    = _get_vital(v, "exaustao")
    energia = _get_vital(v, "energy_reserves")
    return (
        f"HP: {hp}/{hp_max}  FOME: {fome}%  SEDE: {sede}%  "
        f"EXAUSTAO: {exau}%  ENERGIA: {energia}%"
    )


# =============================================================================
# Parser da PARTE 4 — lê itens declarados diretamente pelo GM
# =============================================================================

def _extract_parte4(scene: str) -> dict:
    """
    Extrai o bloco JSON da PARTE 4 do current_scene.md gerado pelo GM.

    Novo formato (GM atual):
      { "vitais": {fome,sede,exaustao,energia,hp}, "itens": [...], "justificativa": "..." }

    Formato legado (GM antigo — só lista de itens):
      [ {...}, ... ]

    Retorna:
      None = PARTE 4 ausente (GM muito antigo — fallback Gemini total)
      dict = PARTE 4 presente (novo ou legado, normalizado)
    """
    idx = scene.upper().find("PARTE 4")
    if idx == -1:
        return None  # type: ignore[return-value]

    bloco = scene[idx:]

    m = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", bloco, re.DOTALL | re.IGNORECASE)
    if not m:
        m = re.search(r"(\{.*?\}|\[.*?\])", bloco, re.DOTALL)
        if not m:
            return None  # PARTE 4 sem JSON → fallback Gemini (B-05)

    raw_json = m.group(1).strip()
    try:
        parsed = json.loads(raw_json)
    except Exception:
        return None  # JSON malformado → fallback Gemini (B-05)

    # Novo formato: objeto com vitais + itens
    if isinstance(parsed, dict):
        return {
            "vitais":        parsed.get("vitais", {}),
            "itens":         parsed.get("itens", []) if isinstance(parsed.get("itens"), list) else [],
            "justificativa": str(parsed.get("justificativa", "")).strip(),
        }

    # Formato legado: lista de itens sem vitais
    if isinstance(parsed, list):
        return {
            "vitais":        {},
            "itens":         parsed,
            "justificativa": "Formato legado — vitais nao declarados",
        }

    return {"vitais": {}, "itens": [], "justificativa": "PARTE 4 formato desconhecido"}


# =============================================================================
# Entry point — chamado in-process pelo web_server.py
# =============================================================================

def run(dry_run: bool = False) -> list:
    """
    Executa o processador. Retorna lista de linhas de log visíveis no pipeline.
    Chamado diretamente por web_server.py (sem subprocess).
    NUNCA lanca excecao.

    Estratégia:
      1. Lê PARTE 4 do current_scene.md (declarada pelo GM).
         Contém vitais + itens. Nenhuma IA é chamada.
         Itens são validados/reparados via _validate_and_repair().
      2. Se PARTE 4 ausente (GM muito antigo): fallback Gemini Flash para tudo.
      3. Se PARTE 4 legada (só lista de itens, sem vitais): vitais zerados + itens validados.
    """
    log: list = []
    try:
        scene = _read(_SCENE_PATH)
        if not scene or len(scene.strip()) < 50:
            log.append("[SP] AVISO: cena vazia ou curta — extração ignorada.")
            return log

        vitals_ctx = _build_vitals_context()
        log.append(f"[SP] Vitais: {vitals_ctx}")

        parte4 = _extract_parte4(scene)

        # ── PARTE 4 ausente: fallback Gemini total (GM muito antigo) ──────────
        if parte4 is None:
            log.append("[SP] PARTE 4 ausente — fallback: Gemini infere vitais e itens.")
            data, err = _call_gemini(scene, vitals_ctx)
            if err:
                log.append(f"[SP] AVISO: {err}")
                return log
            if not isinstance(data, dict):
                log.append("[SP] AVISO: Gemini retornou formato invalido.")
                return log

        # ── PARTE 4 presente: Python puro, sem IA ─────────────────────────────
        else:
            log.append(f"[SP] PARTE 4 detectada — fonte: GM. Sem chamada Gemini.")
            justificativa = parte4.get("justificativa") or "Deltas via PARTE 4"
            log.append(f"[SP] Justificativa: {justificativa}")

            # Extrai vitais declarados pelo GM
            vitais_raw = parte4.get("vitais", {})
            data = {
                "fome":     0,
                "sede":     0,
                "exaustao": 0,
                "energia":  0,
                "hp":       0,
                "itens_adicionados": [],
                "justificativa": justificativa,
            }
            for campo in ("fome", "sede", "exaustao", "energia", "hp"):
                try:
                    val = vitais_raw.get(campo, 0)
                    data[campo] = int(float(val)) if val is not None else 0
                except Exception:
                    data[campo] = 0

            # Valida e repara itens declarados pelo GM
            itens_raw = parte4.get("itens", [])
            n_raw = len(itens_raw)
            if n_raw > 0:
                itens_validos = _validate_and_repair(itens_raw, log)
                n_validos = len(itens_validos)
                n_descartados = n_raw - n_validos
                if n_descartados > 0:
                    log.append(f"[SP] VALIDACAO: {n_validos} aceito(s), {n_descartados} descartado(s)")
                else:
                    log.append(f"[SP] VALIDACAO: todos os {n_validos} item(s) aceitos")
                data["itens_adicionados"] = itens_validos
            else:
                log.append("[SP] PARTE 4: nenhum item declarado")

        delta_log = apply_deltas(data, dry_run=dry_run)
        log.extend(delta_log)

        # Salva relatorio de debug
        os.makedirs(_DRAFT_DIR, exist_ok=True)
        with open(_REPORT_PATH, "w", encoding="utf-8") as f:
            f.write("# SCENE PROCESSOR REPORT\n")
            f.write(f"dry_run: {dry_run}\n")
            f.write(f"fonte: {'PARTE4_GM_PYTHON_PURO' if parte4 is not None else 'GEMINI_FALLBACK'}\n\n")
            f.write("## JSON final\n")
            f.write(json.dumps(data, ensure_ascii=False, indent=2))
            f.write("\n\n## Log\n")
            f.write("\n".join(log) + "\n")

    except Exception as e:
        log.append(f"[SP] ERRO inesperado: {e}")
        log.append(traceback.format_exc())

    return log


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="scene_processor.py",
        description="Passo 3.5 — Extrator de deltas narrativos (Chronos RPG v4.0)"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    for line in run(dry_run=args.dry_run):
        print(line)


if __name__ == "__main__":
    main()