"""
loot_manager.py
Chronos RPG Engine v3.1

Motor de geração de loot. Usado pelo System_Engine (Passo 1) e pelo Architect (Passo 2).
Contém: tabelas de saque A/B/C/D, schema de todos os itens, drops de combate
e utilitários de inventário (CSV).

REGRA DE OURO (Architect): NUNCA altere entradas existentes.
Novas entradas são adicionadas APENAS ao final de LOOT_TABLE e ITEM_SCHEMA.
"""

import csv
import io

# ─────────────────────────────────────────────────────────────────────────────
# 1. SCHEMA COMPLETO DE ITENS
#    Cada entrada é a definição canônica para o inventory.csv.
#    Chave = name (case-sensitive, igual ao CSV).
# ─────────────────────────────────────────────────────────────────────────────

ITEM_SCHEMA = {
    # ── Campos Obrigatórios para Validação ────────────────────────────────────
    "nome": None,
    "tipo": None,
    "raridade": None,
    "quantidade": None,
    "peso_kg": None,
    "usavel": None,
    "efeito": None,
    "notas": None,
    "durabilidade": None,
    "durabilidade_max": None,

    # ── Tabela A — Sucata Industrial ──────────────────────────────────────────
    "Cabo de Cobre": {
        "type": "Material", "rarity": "Comum", "weight_kg": 0.2,
        "effect": "Componente genérico de crafting.",
        "usable": False, "notes": "",
    },
    "Placa de Metal": {
        "type": "Material", "rarity": "Comum", "weight_kg": 1.5,
        "effect": "Input para Reparo de Casco (crafting_recipes.md).",
        "usable": False, "notes": "",
    },
    "Parafusos de Titânio": {
        "type": "Material", "rarity": "Comum", "weight_kg": 0.1,
        "effect": "Componente estrutural.",
        "usable": False, "notes": "",
    },
    "Fusível Queimado": {
        "type": "Lixo", "rarity": "Comum", "weight_kg": 0.1,
        "effect": "Sem uso. Ocupa slot de inventário.",
        "usable": False, "notes": "",
    },

    # ── Tabela B — Suprimentos Vitais ─────────────────────────────────────────
    "Ração de Emergência": {
        "type": "Consumível", "rarity": "Incomum", "weight_kg": 0.3,
        "effect": "+5 HP se usada como ação.",
        "usable": True, "notes": "Último alimento que Ferro carregava antes do salto.",
    },
    "Bateria de Íon Pequena": {
        "type": "Consumível", "rarity": "Incomum", "weight_kg": 0.4,
        "effect": "+10 Energy se usada como ação.",
        "usable": True, "notes": "",
    },
    "Injetor Médico": {
        "type": "Consumível", "rarity": "Incomum", "weight_kg": 0.2,
        "effect": "+10 HP se usado como ação.",
        "usable": True, "notes": "",
    },

    # ── Tabela C — Tecnologia Avançada ────────────────────────────────────────
    "Célula de Combustível": {
        "type": "Recurso", "rarity": "Raro", "weight_kg": 2.0,
        "effect": "+1 Fuel Cell ao tanque da nave.",
        "usable": True, "notes": "Inutilizável sem nave presente (Arco 2 final+).",
    },
    "Módulo de Upgrade de Scanner": {
        "type": "Equipamento Passivo", "rarity": "Raro", "weight_kg": 0.5,
        "effect": "+1 permanente em testes de Scan.",
        "usable": False, "notes": "Aplicar ao character_sheet.json uma única vez.",
    },
    "Chip de IA Corrompido": {
        "type": "Quest", "rarity": "Raro", "weight_kg": 0.1,
        "effect": "Sem efeito mecânico. Alto valor de troca.",
        "usable": False, "notes": "Registrar em active_quests.md.",
    },

    # ── Tabela D — Anomalia ───────────────────────────────────────────────────
    "Artefato Precursor": {
        "type": "Anomalia", "rarity": "Lendário", "weight_kg": 0.8,
        "effect": "Função desconhecida. Alto valor de troca.",
        "usable": False, "notes": "Aciona PROTOCOLO DE EXPANSÃO.",
    },

    # ── Materiais de Crafting (inventário inicial) ────────────────────────────
    "Biomassa": {
        "type": "Material", "rarity": "Comum", "weight_kg": 0.3,
        "effect": "Input para Filtro de O2 (crafting_recipes.md).",
        "usable": False, "notes": "",
    },
    "Sucata Eletrônica": {
        "type": "Material", "rarity": "Comum", "weight_kg": 0.5,
        "effect": "Input para Munição Energética e Drone Auxiliar.",
        "usable": False, "notes": "",
    },
    "Bateria de Íon": {
        "type": "Material", "rarity": "Incomum", "weight_kg": 0.6,
        "effect": "Input para Munição Energética e Drone Auxiliar.",
        "usable": False, "notes": "Versão maior que a Bateria de Íon Pequena.",
    },
    "Solda": {
        "type": "Material", "rarity": "Comum", "weight_kg": 0.2,
        "effect": "Input para Reparo de Casco.",
        "usable": False, "notes": "",
    },
    "Plástico": {
        "type": "Material", "rarity": "Comum", "weight_kg": 0.3,
        "effect": "Input para Filtro de O2.",
        "usable": False, "notes": "",
    },

    # ── Drops de Combate — Arco 1 (Selva) ────────────────────────────────────
    "Couro Bruto": {
        "type": "Material", "rarity": "Comum", "weight_kg": 0.8,
        "effect": "Crafting primitivo. Pode ser improvisado como armadura leve (-1 dano recebido).",
        "usable": False, "notes": "Drop: Predador Selva.",
    },
    "Osso Denso": {
        "type": "Material", "rarity": "Comum", "weight_kg": 0.4,
        "effect": "Componente estrutural primitivo. Pode fabricar ponta de lança ou ferramenta.",
        "usable": False, "notes": "Drop: Javali Blindado, Predador Alfa.",
    },
    "Lança Primitiva": {
        "type": "Arma", "rarity": "Comum", "weight_kg": 1.2,
        "effect": "+2 em testes de Combate ranged (arremesso). Alcance: 1 turno de distância.",
        "usable": False, "notes": "Equipar em weapon_primary ou secondary. Drop: Guerreiro Tribal.",
    },
    "Erva Medicinal": {
        "type": "Consumível", "rarity": "Comum", "weight_kg": 0.1,
        "effect": "Remove status Envenenado ou recupera +3 HP se usado como ação.",
        "usable": True, "notes": "Drop: Guerreiro Tribal. Ingrediente para cura primitiva.",
    },
    "Carapaça Térmica": {
        "type": "Equipamento Passivo", "rarity": "Incomum", "weight_kg": 1.5,
        "effect": "-2 de dano recebido do tipo Físico quando equipada. Resistente a fogo.",
        "usable": False, "notes": "Drop: Predador Alfa. Equipar como armor no character_sheet.json.",
    },

    # ── Drops de Combate — Arco 2 (Nova Carthage) ────────────────────────────
    "Cargas de Rifle": {
        "type": "Consumível", "rarity": "Incomum", "weight_kg": 0.05,
        "effect": "Munição para Rifle Energético. 1 carga = 1 ataque ranged.",
        "usable": True, "notes": "Drop: Mercenário Corporativo (×4). Sem arma = sem uso.",
    },
    "Módulo de Blindagem": {
        "type": "Equipamento Passivo", "rarity": "Raro", "weight_kg": 0.9,
        "effect": "-3 de dano recebido do tipo Balístico quando integrado à nave ou traje.",
        "usable": False, "notes": "Drop: Exoesqueleto Elite. Requer Engineering DC 12 para instalar.",
    },

    # ── Drops de Combate — Arco 3 (Planetas) ─────────────────────────────────
    "Carapaça Ácido-Resistente": {
        "type": "Material", "rarity": "Raro", "weight_kg": 1.8,
        "effect": "Revestimento anti-ácido para nave ou traje. -3 suit_integrity/turno → 0 quando instalada.",
        "usable": False, "notes": "Drop: Leviatã da Ferrugem (×3). Necessária Cap. 28.",
    },
    "Cristal Sônico": {
        "type": "Material", "rarity": "Raro", "weight_kg": 0.3,
        "effect": "Componente para armas sônicas e motores experimentais.",
        "usable": False, "notes": "Drop: Espectro de Gelo (×2). Receita disponível Cap. 34.",
    },
    "Membrana Orgânica": {
        "type": "Material", "rarity": "Incomum", "weight_kg": 0.5,
        "effect": "Isolante biológico. Revestimento de casco: -1 dano de impacto em gravidade zero.",
        "usable": False, "notes": "Drop: Criatura do Vácuo (×2).",
    },
    "Escama de Abismo": {
        "type": "Material", "rarity": "Raro", "weight_kg": 1.2,
        "effect": "Blindagem contra pressão extrema. Necessária para descer abaixo de 800m no Abismo Oceânico.",
        "usable": False, "notes": "Drop: Leviatã das Profundezas (×2).",
    },
    "Glândula Elétrica": {
        "type": "Material", "rarity": "Incomum", "weight_kg": 0.2,
        "effect": "Componente para armas de choque improvisadas. Receita disponível Cap. 40.",
        "usable": False, "notes": "Drop: Revoada Relâmpago (×1 por unidade).",
    },
    "Pele Isolante": {
        "type": "Material", "rarity": "Incomum", "weight_kg": 0.6,
        "effect": "Isolamento térmico extremo. -2 HP/turno no Mundo Órfão → 0 quando integrada ao traje.",
        "usable": False, "notes": "Drop: Caçador Cego (×2). Essencial Caps. 47–49.",
    },
    "Biomassa Fúngica Viva": {
        "type": "Material", "rarity": "Raro", "weight_kg": 0.4,
        "effect": "Integração simbiótica com sistemas da nave. +5% energy_reserves por turno (passivo).",
        "usable": False, "notes": "Drop: Parasita Mental Fúngico (após dominação). Requer Engineering DC 14 para instalar.",
    },

    # ── Fabricados ────────────────────────────────────────────────────────────
    "Drone Auxiliar": {
        "type": "Equipamento Passivo", "rarity": "Raro", "weight_kg": 1.2,
        "effect": "+2 fixo em todos os testes de Engineering futuros.",
        "usable": False, "notes": "Fabricado. Aplicar bônus ao character_sheet.json → skills.engineering.bonus.",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# 2. TABELA DE SAQUE (d20 bruto → item)
# ─────────────────────────────────────────────────────────────────────────────

LOOT_TABLE = {
    # Tabela A — Sucata Industrial (d20: 1–10)
    1:  "Cabo de Cobre",
    2:  "Cabo de Cobre",
    3:  "Cabo de Cobre",
    4:  "Cabo de Cobre",
    5:  "Placa de Metal",
    6:  "Placa de Metal",
    7:  "Placa de Metal",
    8:  "Parafusos de Titânio",
    9:  "Parafusos de Titânio",
    10: "Fusível Queimado",

    # Tabela B — Suprimentos Vitais (d20: 11–16)
    11: "Ração de Emergência",
    12: "Ração de Emergência",
    13: "Bateria de Íon Pequena",
    14: "Bateria de Íon Pequena",
    15: "Injetor Médico",
    16: "Injetor Médico",

    # Tabela C — Tecnologia Avançada (d20: 17–19)
    17: "Célula de Combustível",
    18: "Módulo de Upgrade de Scanner",
    19: "Chip de IA Corrompido",

    # Tabela D — Anomalia (d20: 20)
    20: "Artefato Precursor",
}

LOOT_TABLE_LABELS = {
    range(1,  11): "A",
    range(11, 17): "B",
    range(17, 20): "C",
    range(20, 21): "D",
}

def roll_loot(d20_raw: int) -> dict:
    """
    Resolve a geração de loot a partir do valor bruto do d20 (sem modificador).

    Retorna dict com:
      item_name:  str — nome canônico do item
      table:      str — "A" | "B" | "C" | "D" | "EXPANSAO"
      schema:     dict — schema completo do item (de ITEM_SCHEMA)
    """
    if d20_raw not in LOOT_TABLE:
        return {"item_name": None, "table": "EXPANSAO", "schema": None}

    item_name = LOOT_TABLE[d20_raw]
    table_label = next(
        (v for k, v in LOOT_TABLE_LABELS.items() if d20_raw in k), "?"
    )
    schema = ITEM_SCHEMA.get(item_name)

    return {
        "item_name":  item_name,
        "table":      table_label,
        "schema":     schema,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. DROPS DE COMBATE (fixos — sem rolagem de d20)
# ─────────────────────────────────────────────────────────────────────────────

COMBAT_DROPS = {
    # ── Arco 1 ────────────────────────────────────────────────────────────────
    "Predador Selva":              [("Biomassa", 2), ("Couro Bruto", 1)],
    "Javali Blindado":             [("Biomassa", 3), ("Osso Denso", 1)],
    "Enxame de Insetos Ácidos":    [],
    "Guerreiro Tribal":            [("Lança Primitiva", 1), ("Erva Medicinal", 1)],
    "Predador Alfa da Encosta":    [("Carapaça Térmica", 1), ("Biomassa", 3), ("Osso Denso", 2)],

    # ── Arco 2 ────────────────────────────────────────────────────────────────
    "Mercenário Corporativo":      [("Sucata Eletrônica", 1), ("Bateria de Íon", 1), ("Cargas de Rifle", 4)],
    "Drone de Vigilância Corporativo": [("Chip de IA Corrompido", 1), ("Bateria de Íon Pequena", 1)],
    "Exoesqueleto Mercenário Elite":   [("Placa de Metal", 2), ("Módulo de Blindagem", 1), ("Sucata Eletrônica", 2)],

    # ── Arco 3 ────────────────────────────────────────────────────────────────
    "Leviatã da Ferrugem":         [("Carapaça Ácido-Resistente", 3)],
    "Espectro de Gelo":            [("Cristal Sônico", 2)],
    "Autômato de Segurança Reativado": [("Sucata Eletrônica", 2), ("Bateria de Íon", 1)],
    "Parasita Mental Fúngico":     [("Biomassa Fúngica Viva", 1)],    # após dominação
    "Criatura do Vácuo":           [("Membrana Orgânica", 2)],
    "Leviatã das Profundezas":     [("Escama de Abismo", 2)],
    "Revoada Relâmpago":           [("Glândula Elétrica", 1)],        # × por unidade destruída
    "Caçador Cego":                [("Pele Isolante", 2)],
    "Medusa Abissal":              [],
    "Predador de Tempestade":      [],
    "Colônia Gasosa":              [],
    "Eco Temporal":                [],
    "Nano-Assimilador":            [],
    "O Silêncio":                  [],
}

def get_combat_drops(enemy_name: str) -> list[tuple[str, int]]:
    """
    Retorna a lista de drops de um inimigo pelo nome exato do bestiário.
    Cada elemento é (nome_item, quantidade).
    Retorna lista vazia se o inimigo não tem drop ou não está cadastrado.
    """
    return COMBAT_DROPS.get(enemy_name, [])

def get_drop_schemas(enemy_name: str) -> list[dict]:
    """
    Retorna os schemas completos dos drops de um inimigo,
    prontos para inserção no inventory.csv.
    """
    results = []
    for item_name, qty in get_combat_drops(enemy_name):
        schema = ITEM_SCHEMA.get(item_name)
        if schema:
            results.append({"name": item_name, "quantity": qty, **schema})
    return results


# ─────────────────────────────────────────────────────────────────────────────
# 4. UTILITÁRIOS DE INVENTÁRIO (CSV)
# ─────────────────────────────────────────────────────────────────────────────

CSV_COLUMNS = ["id", "name", "type", "rarity", "quantity", "weight_kg",
               "effect", "usable", "durability", "durability_max", "notes"]

def parse_inventory(csv_text: str) -> list[dict]:
    """
    Lê o texto completo do inventory.csv e retorna lista de dicts.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = []
    for row in reader:
        row["quantity"]  = int(row["quantity"])
        row["weight_kg"] = float(row["weight_kg"])
        row["usable"]    = row["usable"].lower() == "true"
        rows.append(row)
    return rows

def serialize_inventory(rows: list[dict]) -> str:
    """
    Converte lista de dicts de volta para texto CSV (separador vírgula).
    Remove automaticamente linhas com quantity <= 0.
    """
    rows = [r for r in rows if r.get("quantity", 0) > 0]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in CSV_COLUMNS})
    return out.getvalue()

def add_item(rows: list[dict], item_name: str, quantity: int = 1) -> list[dict]:
    """
    Adiciona ou incrementa um item no inventário.
    Se o item já existe, soma a quantidade.
    Se não existe, cria nova entrada usando ITEM_SCHEMA.
    Retorna a lista atualizada.
    """
    for row in rows:
        if row["name"] == item_name:
            row["quantity"] += quantity
            return rows

    schema = ITEM_SCHEMA.get(item_name)
    if not schema:
        raise ValueError(f"Item '{item_name}' não encontrado em ITEM_SCHEMA. "
                         "Crie a entrada antes de persistir.")

    next_id = max((int(r["id"]) for r in rows if str(r["id"]).isdigit()), default=0) + 1
    new_row = {
        "id":        next_id,
        "name":      item_name,
        "quantity":  quantity,
        **schema,
    }
    rows.append(new_row)
    return rows

def remove_item(rows: list[dict], item_name: str, quantity: int = 1) -> list[dict]:
    """
    Decrementa um item no inventário.
    Remove a linha se quantity chegar a 0.
    Levanta ValueError se o item não existir ou quantidade insuficiente.
    """
    for row in rows:
        if row["name"] == item_name:
            if row["quantity"] < quantity:
                raise ValueError(f"Quantidade insuficiente de '{item_name}': "
                                 f"disponível={row['quantity']}, solicitado={quantity}")
            row["quantity"] -= quantity
            break
    else:
        raise ValueError(f"Item '{item_name}' não encontrado no inventário.")

    return [r for r in rows if r["quantity"] > 0]

def has_item(rows: list[dict], item_name: str, quantity: int = 1) -> bool:
    """Verifica se o inventário tem ao menos `quantity` unidades do item."""
    for row in rows:
        if row["name"] == item_name:
            return row["quantity"] >= quantity
    return False