# BESTIÁRIO & AMEAÇAS CONHECIDAS
## Versão Claude-Optimizada v3

---

> **INSTRUÇÃO AO ARCHITECT E LORE_ARCHIVIST:**
> Toda criatura nova deve obrigatoriamente seguir o template abaixo. Nenhuma entrada é válida sem todos os campos preenchidos. Campos desconhecidos recebem `???` (não deixe em branco).

---

## TEMPLATE OBRIGATÓRIO DE FICHA DE MONSTRO

```
---
## Nome: _______________________

**HP:** ___ / ___

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | ___ |
| Destreza (DES) | ___ |
| Inteligência (INT) | ___ |
| Sobrevivência (SOB) | ___ |
| Percepção (PER) | ___ |
| Carisma (CAR) | ___ |

### Combate
- **DC de Defesa:** ___
- **Dano por Turno:** ___ (tipo: Balístico / Físico / Químico / Biológico / Elétrico / Anomalia)
- **Bônus Racial de Dano:** ___ *(derivado: `max(0, (FOR−10)//2)` — somado ao d4 do contra-ataque)*
- **Acerto Crítico:** (efeito especial se rolar 20 natural)
- **Threshold Moral:** ___ *(% HP em que foge — ou `Nunca` para bosses/mecânicos)*
- **Fase 2 (Boss):** `Não` | `Sim — ver mechanics_engine Seção 27`

### Informações de Campo
- **Classe:** (Biológico / Mecânico / Humano / Anomalia)
- **Arco / Capítulo:** (onde pode ser encontrado)
- **Habitat:** ___
- **Comportamento:** ___
- **Fraqueza:** ___
- **Drop (Loot):** ___
---
```


---

## CLASSE A: BIOLÓGICOS — SELVA PRIMITIVA (Arco 1, Caps. 1–14)

---
## Nome: Predador Selva (Felino de Emboscada)

**HP:** 18 / 18

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 14 |
| Destreza (DES) | 18 |
| Inteligência (INT) | 3 |
| Sobrevivência (SOB) | 10 |
| Percepção (PER) | 16 |
| Carisma (CAR) | 1 |

### Combate
- **DC de Defesa:** 14
- **Dano por Turno:** 4 *(tipo: Físico — Mordida e garra)*
- **Acerto Crítico:** Derruba o jogador. Próxima ação obrigatória: `Levantar` (DC 10 SOB) ou permanece caído com -2 em todos os testes.
- **Threshold Moral:** 30% (Biológico)
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** Biológico
- **Arco / Capítulo:** Arco 1 — Caps. 1 a 9
- **Habitat:** Selva densa, bordas de trilha, proximidade de rios.
- **Comportamento:** Solitário. Observa 1–2 turnos antes de atacar. Prioriza presas isoladas e imóveis.
- **Fraqueza:** Fogo (recua imediatamente). Barulho súbito pode interromper o ataque (PER DC 12 para usá-lo como distração).
- **Drop (Loot):** Biomassa × 2, Couro Bruto × 1.

---
## Nome: Javali Blindado (Herbívoro Territorial)

**HP:** 24 / 24

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 18 |
| Destreza (DES) | 6 |
| Inteligência (INT) | 1 |
| Sobrevivência (SOB) | 14 |
| Percepção (PER) | 8 |
| Carisma (CAR) | 1 |

### Combate
- **DC de Defesa:** 12
- **Dano por Turno:** 5 *(tipo: Físico — Chifrada)*
- **Acerto Crítico:** Arremessa o jogador. Aplica status `Atordoado` — perde 1 ação no próximo turno.
- **Threshold Moral:** 30% (Biológico — territorial, não foge no habitat)
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** Biológico
- **Arco / Capítulo:** Arco 1 — Caps. 2 a 10
- **Habitat:** Clareiras, rotas de água.
- **Comportamento:** Não ataca primeiro. Reage a proximidade (< 5m) ou barulho alto. Carrega em linha reta sem desviar.
- **Fraqueza:** Esquivar lateralmente (DES DC 14) para que ele passe sem acertar. Não persegue além de 30 metros.
- **Drop (Loot):** Biomassa × 3, Osso Denso × 1.

---
## Nome: Enxame de Insetos Ácidos

**HP:** 8 / 8 *(HP coletivo — imune a ataque físico direto)*

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 1 |
| Destreza (DES) | 18 |
| Inteligência (INT) | 1 |
| Sobrevivência (SOB) | 6 |
| Percepção (PER) | 14 |
| Carisma (CAR) | 1 |

### Combate
- **DC de Defesa:** 18 *(imune a ataques físicos — apenas fogo ou fumaça os destrói/dispersa)*
- **Dano por Turno:** 3 *(tipo: Químico — Ácido. Corrói equipamento: -1% suit_integrity por turno de exposição)*
- **Acerto Crítico:** Invade rosto exposto. Aplica status `Queimadura` (-2 PER por 3 turnos).
- **Threshold Moral:** Nunca (coletivo — sem instinto individual)
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** Biológico
- **Arco / Capítulo:** Arco 1 — Caps. 1 a 14
- **Habitat:** Troncos ocos, tocas no solo (identificável: terra esbranquiçada ao redor).
- **Comportamento:** Dormentes até vibração de pisada. O enxame inteiro ataca em conjunto.
- **Fraqueza:** Fogo destrói o enxame em 1 turno. Fumaça os dispersa por 2 turnos.
- **Drop (Loot):** Nenhum.

---
## Nome: Guerreiro Tribal

**HP:** 14 / 14

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 12 |
| Destreza (DES) | 12 |
| Inteligência (INT) | 6 |
| Sobrevivência (SOB) | 12 |
| Percepção (PER) | 14 |
| Carisma (CAR) | 8 |

### Combate
- **DC de Defesa:** 13
- **Dano por Turno:** 3 *(tipo: Físico — Lança ou Clava)*
- **Acerto Crítico:** Lança envenenada. Aplica status `Envenenado` — -1 HP passivo por turno por 4 turnos. Cura: Erva Medicinal + ação Medicina DC 12.
- **Threshold Moral:** 40% (Humano — recua se o líder cair)
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** Humano
- **Arco / Capítulo:** Arco 1 — Caps. 4 a 12
- **Habitat:** Território tribal — floresta marcada com estacas e ossos.
- **Comportamento:** Patrulha em pares ou grupos de 3. Usa armadilhas antes de atacar. Recua se o líder cair.
- **Fraqueza:** CAR pode iniciar negociação (DC 18 — muito difícil sem mediação do chip). Fuga para fora do território encerra a perseguição.
- **Drop (Loot):** Lança Primitiva × 1, Erva Medicinal × 1.

---
## Nome: Predador Alfa da Encosta *(Boss — Cap. 9)*

**HP:** 40 / 40

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 20 |
| Destreza (DES) | 14 |
| Inteligência (INT) | 4 |
| Sobrevivência (SOB) | 18 |
| Percepção (PER) | 16 |
| Carisma (CAR) | 1 |

### Combate
- **DC de Defesa:** 16
- **Dano por Turno:** 7 *(tipo: Físico — Impacto maciço)*
- **Acerto Crítico:** Esmaga membro. Status `Membro Inutilizado` — penalidade permanente -3 DES até Medicina DC 18.
- **Threshold Moral:** Nunca (Boss — territorial absoluto)
- **Fase 2 (Boss):** Sim — ver mechanics_engine Seção 27

### Informações de Campo
- **Classe:** Biológico
- **Arco / Capítulo:** Arco 1 — Cap. 9 (Boss da encosta vulcânica)
- **Habitat:** Encostas rochosas e cráteras vulcânicas.
- **Comportamento:** Territorial absoluto. Não recua. Resiste a fogo por tolerância à temperatura.
- **Fraqueza:** Rocha vulcânica nos olhos (DES DC 15) — cega por 2 turnos. Despenhadeiro próximo pode ser usado como fuga (DES DC 12).
- **Drop (Loot):** Carapaça Térmica × 1, Biomassa × 3, Osso Denso × 2.

---

## CLASSE B: HUMANOS / MECÂNICOS — NOVA CARTHAGE (Arco 2, Caps. 15–25)

---
## Nome: Mercenário Corporativo (Padrão)

**HP:** 16 / 16

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 12 |
| Destreza (DES) | 14 |
| Inteligência (INT) | 8 |
| Sobrevivência (SOB) | 10 |
| Percepção (PER) | 12 |
| Carisma (CAR) | 6 |

### Combate
- **DC de Defesa:** 14
- **Dano por Turno:** 4 *(tipo: Balístico — Rifle urbano)*
- **Acerto Crítico:** Tiro no chip — CHRONOS-7 offline por 1 turno (sem interface, sem bônus).
- **Threshold Moral:** 40% (Humano — chama reforço antes de fugir)
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** Humano
- **Arco / Capítulo:** Arco 2 — Caps. 16 a 25
- **Habitat:** Setores corporativos de Nova Carthage, esgotos quando rastreando.
- **Comportamento:** Opera em duplas. Usa cobertura. Chama reforço após 3 turnos (d20 ≥ 15 = reforço no turno seguinte).
- **Fraqueza:** Hackear transponder via chip (INT DC 18) os confunde por 1 turno.
- **Drop (Loot):** Sucata Eletrônica × 1, Bateria de Íon × 1, Cargas de Rifle × 4.

---
## Nome: Drone de Vigilância Corporativo

**HP:** 12 / 12

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 4 |
| Destreza (DES) | 16 |
| Inteligência (INT) | 12 |
| Sobrevivência (SOB) | 6 |
| Percepção (PER) | 20 |
| Carisma (CAR) | 1 |

### Combate
- **DC de Defesa:** 15
- **Dano por Turno:** 3 *(tipo: Elétrico — Descarga de atordoamento)*
- **Acerto Crítico:** Pulso EMP — desativa CHRONOS-7 por 2 turnos, apaga o HUD.
- **Threshold Moral:** Nunca (Mecânico)
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** Mecânico
- **Arco / Capítulo:** Arco 2 — Caps. 17 a 24
- **Habitat:** Tetos e conduítes de Nova Carthage, zonas restritas.
- **Comportamento:** Emite 1 aviso sonoro antes de atacar. Alerta rede de segurança se não destruído em 2 turnos.
- **Fraqueza:** Interface do chip via toque (INT DC 15) redireciona sua rota por 3 turnos. Ataque à câmera central (DES DC 16) o cega permanentemente.
- **Drop (Loot):** Chip de IA Corrompido × 1, Bateria de Íon Pequena × 1.

---
## Nome: Exoesqueleto Mercenário Elite *(Boss — Cap. 23)*

**HP:** 35 / 35

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 20 |
| Destreza (DES) | 8 |
| Inteligência (INT) | 10 |
| Sobrevivência (SOB) | 16 |
| Percepção (PER) | 10 |
| Carisma (CAR) | 4 |

### Combate
- **DC de Defesa:** 17
- **Dano por Turno:** 8 *(tipo: Balístico — Minigun integrada)*
- **Acerto Crítico:** Destrói a cobertura que o jogador usa permanentemente.
- **Threshold Moral:** Nunca (Boss — piloto fanático)
- **Fase 2 (Boss):** Sim — ver mechanics_engine Seção 27

### Informações de Campo
- **Classe:** Mecânico / Humano
- **Arco / Capítulo:** Arco 2 — Cap. 23 (Cerco Corporativo)
- **Habitat:** Ruas e interior da oficina.
- **Comportamento:** Avança diretamente. Sem recuo. Piloto humano interno — negociável via CAR DC 20 ou hackável via chip INT DC 20.
- **Fraqueza:** Juntas das pernas (DES DC 16 para mirar) — imobiliza. Sobrecarga com 2 Baterias de Íon simultâneas (Engineering DC 14) derruba os sistemas.
- **Drop (Loot):** Placa de Metal × 2, Módulo de Blindagem × 1, Sucata Eletrônica × 2.

---

## CLASSE C: BIOLÓGICOS — PLANETAS (Arco 3, Caps. 26–55)

---
## Nome: Leviatã da Ferrugem *(Boss — Caps. 26–28)*

**HP:** 45 / 45

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 20 |
| Destreza (DES) | 6 |
| Inteligência (INT) | 2 |
| Sobrevivência (SOB) | 20 |
| Percepção (PER) | 8 |
| Carisma (CAR) | 1 |

### Combate
- **DC de Defesa:** 15
- **Dano por Turno:** 8 *(tipo: Físico + Químico — Esmagamento e saliva ácida)*
- **Acerto Crítico:** Corrói casco da nave — `-15 hull_integrity` imediatamente.
- **Threshold Moral:** Nunca (Boss — ativado por vibração, sem instinto de fuga)
- **Fase 2 (Boss):** Sim — ver mechanics_engine Seção 27

### Informações de Campo
- **Classe:** Biológico
- **Arco / Capítulo:** Arco 3 — Caps. 26 a 28 (Mundo Corrosivo)
- **Habitat:** Terreno derretido por ácido sulfúrico.
- **Comportamento:** Ativado por vibração mecânica (motores). Não para enquanto detectar vibração.
- **Fraqueza:** Parar todos os sistemas da nave por 1 turno o desorientar (Engineering DC 14). Carapaça coletável após morte.
- **Drop (Loot):** Carapaça Ácido-Resistente × 3 *(necessária para o Cap. 28)*.

---
## Nome: Espectro de Gelo *(Caps. 32–34)*

**HP:** 20 / 20

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 10 |
| Destreza (DES) | 20 |
| Inteligência (INT) | 2 |
| Sobrevivência (SOB) | 16 |
| Percepção (PER) | 20 |
| Carisma (CAR) | 1 |

### Combate
- **DC de Defesa:** 18 *(quase transparente)*
- **Dano por Turno:** 5 *(tipo: Físico — Impacto de cauda cristalina)*
- **Acerto Crítico:** Vibração ativa cristais próximos — explosão sônica `-8 HP` adicional e pode chamar +1 Espectro.
- **Threshold Moral:** Nunca (Mecânico/Biológico — sem consciência de fuga)
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** Biológico
- **Arco / Capítulo:** Arco 3 — Caps. 32 a 34 (Deserto de Vidro)
- **Habitat:** Planícies cristalinas. Emerge do subsolo via vibração.
- **Comportamento:** Cego para luz e forma — caça exclusivamente por vibração sonora. Qualquer barulho acima de sussurro os ativa.
- **Fraqueza:** Chip em frequência ultrassônica (INT DC 14) os confunde por 2 turnos. Completamente imóveis sem vibração.
- **Drop (Loot):** Cristal Sônico × 2 *(material para armas e motores — Cap. 34)*.

---
## Nome: Autômato de Segurança Reativado *(Caps. 35–37)*

**HP:** 22 / 22

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 16 |
| Destreza (DES) | 10 |
| Inteligência (INT) | 14 |
| Sobrevivência (SOB) | 12 |
| Percepção (PER) | 18 |
| Carisma (CAR) | 1 |

### Combate
- **DC de Defesa:** 14
- **Dano por Turno:** 5 *(tipo: Elétrico — Descarga de guerra antiga)*
- **Acerto Crítico:** Sobrecarga no chip — CHRONOS-7 em modo emergência. Apenas tradução ativa por 3 turnos.
- **Threshold Moral:** Nunca (Mecânico)
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** Mecânico
- **Arco / Capítulo:** Arco 3 — Caps. 35 a 37 (Cemitério de Silício)
- **Habitat:** Campo de batalha fossilizado sob areia de silício.
- **Comportamento:** Enxame — quando 1 é destruído, 2 novos acordam nos próximos 2 turnos (máximo 6 simultâneos).
- **Fraqueza:** Tempestade eletromagnética os cega completamente (Cap. 37). Interface do chip (INT DC 16) apaga protocolo de segurança de 1 unidade por vez.
- **Drop (Loot):** Sucata Eletrônica × 2, Bateria de Íon × 1.

---
## Nome: Parasita Mental Fúngico *(Caps. 41–43)*

**HP:** 6 / 6 *(HP representa integridade do chip, não corpo físico)*

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 1 |
| Destreza (DES) | 14 |
| Inteligência (INT) | 18 |
| Sobrevivência (SOB) | 10 |
| Percepção (PER) | 20 |
| Carisma (CAR) | 1 |

### Combate
- **DC de Defesa:** 20 *(entidade de esporos — ataque físico ineficaz)*
- **Dano por Turno:** 0 direto *(tipo: Biológico — distorce percepções: -2 em TODOS os testes enquanto ativo)*
- **Acerto Crítico:** Hackeamento profundo — jogador age involuntariamente por 1 turno sob controle do fungo.
- **Threshold Moral:** Nunca (Anomalia)
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** Anomalia / Biológico
- **Arco / Capítulo:** Arco 3 — Caps. 41 a 43 (Mundo Simbiótico)
- **Habitat:** Qualquer local com névoa fúngica bioluminescente.
- **Comportamento:** Não possui corpo físico — é a rede neural do planeta tentando assimilar o chip.
- **Fraqueza:** Dominação via chip (INT DC 18 — Cap. 43) o transforma em aliado. Máscara improvisada (Engineering DC 14) bloqueia esporos por 5 turnos.
- **Drop (Loot):** Nenhum *(após dominação: Biomassa Fúngica Viva integrada à nave)*.

---
## Nome: Criatura do Vácuo *(Caps. 44–46)*

**HP:** 28 / 28

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 16 |
| Destreza (DES) | 18 |
| Inteligência (INT) | 2 |
| Sobrevivência (SOB) | 20 |
| Percepção (PER) | 14 |
| Carisma (CAR) | 1 |

### Combate
- **DC de Defesa:** 16
- **Dano por Turno:** 6 *(tipo: Físico — Impacto em gravidade zero)*
- **Acerto Crítico:** Rompe cabo de segurança — drift para o espaço (DES DC 14 para agarrar estrutura próxima).
- **Threshold Moral:** 30% (Biológico)
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** Biológico
- **Arco / Capítulo:** Arco 3 — Caps. 44 a 46 (Orbe Estilhaçado)
- **Habitat:** Campo de asteroides e gravidade zero. Vive no vácuo absoluto.
- **Comportamento:** Territorial nos fragmentos do núcleo. Ataca durante mineração (Cap. 46).
- **Fraqueza:** Mudar de plano espacial rapidamente os faz ultrapassar o alvo (DES DC 15 para esquivar e atacar com +3 no próximo turno).
- **Drop (Loot):** Membrana Orgânica × 2 *(material isolante para revestimento da nave)*.

---

---
## Nome: Revoada Relâmpago *(Caps. 38–40)*

**HP:** 6 / 6 por unidade *(enxame de 4–8 criaturas — ataque simultâneo)*

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 4 |
| Destreza (DES) | 20 |
| Inteligência (INT) | 1 |
| Sobrevivência (SOB) | 8 |
| Percepção (PER) | 16 |
| Carisma (CAR) | 1 |

### Combate
- **DC de Defesa:** 17 *(velocidade extrema nas correntes gasosas)*
- **Dano por Turno:** 2 por unidade ativa *(tipo: Elétrico — descarga acumulada pelo voo nos furacões)* 
- **Acerto Crítico:** Descarga em cadeia — se 3+ unidades ativas, sobrecarga de `-12 HP` imediata e desativa sistemas elétricos da nave por 1 turno.
- **Threshold Moral:** 30% (Biológico — enxame debanda se reduzido a 1 unidade)
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** Biológico
- **Arco / Capítulo:** Arco 3 — Caps. 38 a 40 (Gigante Gasoso)
- **Habitat:** Bandas atmosféricas de hidrogênio e hélio. Vivem nas correntes de furacão.
- **Comportamento:** Atacam em bando. Cada unidade destruída reduz o dano total do enxame. Reorganizam-se a cada 2 turnos se restarem ≥ 3 unidades.
- **Fraqueza:** Gaiola de Faraday improvisada (Engineering DC 12) cria campo neutro — enxame perde o alvo por 3 turnos. Individualmente: fáceis de abater, perigosos em grupo.
- **Drop (Loot):** Glândula Elétrica × 1 por unidade destruída *(componente para armas elétricas — Cap. 40)*.


---
## Nome: Leviatã das Profundezas *(Boss — Caps. 29–31)*

**HP:** 50 / 50

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 20 |
| Destreza (DES) | 10 |
| Inteligência (INT) | 3 |
| Sobrevivência (SOB) | 20 |
| Percepção (PER) | 18 |
| Carisma (CAR) | 1 |

### Combate
- **DC de Defesa:** 15
- **Dano por Turno:** 9 *(tipo: Físico — Impacto de mandíbula abissal)*
- **Acerto Crítico:** Prende o jogador/nave em tentáculo. Aplica status `Imobilizado` — nenhuma ação de movimento por 2 turnos. Requer FOR DC 16 ou DES DC 16 para libertar.
- **Threshold Moral:** Nunca (Boss — territorial absoluto abaixo de 500m)
- **Fase 2 (Boss):** Sim — ver mechanics_engine Seção 27

### Informações de Campo
- **Classe:** Biológico
- **Arco / Capítulo:** Arco 3 — Caps. 29 a 31 (Abismo Oceânico)
- **Habitat:** Zona abissal abaixo de 800m de profundidade. Jamais sobe acima de 500m (pressão os desestabiliza).
- **Comportamento:** Territorial absoluto. Detecta vibrações da nave a 2km. Ataca apenas quando a nave desce abaixo de 500m. Não persegue se a nave subir.
- **Fraqueza:** Subir acima de 500m encerra o confronto imediatamente. Luz de alta intensidade (Engineering DC 13) o desorientar por 1 turno — abre janela de fuga ou ataque com +2.
- **Drop (Loot):** Escama de Abismo × 2 *(coletadas do terreno durante a fuga — Cap. 31)*.

---
## Nome: Medusa Abissal *(Caps. 29–30)*

**HP:** 14 / 14

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 4 |
| Destreza (DES) | 16 |
| Inteligência (INT) | 2 |
| Sobrevivência (SOB) | 8 |
| Percepção (PER) | 12 |
| Carisma (CAR) | 1 |

### Combate
- **DC de Defesa:** 13
- **Dano por Turno:** 3 *(tipo: Biológico — Neurotoxina de tentáculo. Acumula: +1 dano por turno consecutivo de contato)*
- **Acerto Crítico:** Neurotoxina concentrada — aplica status `Paralisado` (FOR DC 14). Próxima ação é obrigatoriamente `Resistir ao veneno` ou perde o turno inteiro.
- **Threshold Moral:** 30% (Biológico — passiva por natureza)
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** Biológico
- **Arco / Capítulo:** Arco 3 — Caps. 29 a 30 (Abismo Oceânico — zona intermediária)
- **Habitat:** Colônias de 3–6 indivíduos entre 200m e 600m de profundidade. Bioluminescentes — visíveis no escuro.
- **Comportamento:** Passivas enquanto a nave não emite luz. Curiosas — se aproximam da nave. Atacam se tocadas ou se luz intensa for usada.
- **Fraqueza:** Bioluminescência própria as torna rastreáveis no escuro. Mantendo a nave às escuras e movendo-se devagar, podem ser contornadas (PER DC 11).
- **Drop (Loot):** Nenhum *(tentáculos se dissolvem ao morrer — sem material coletável)*.

---
## Nome: Predador de Tempestade *(Caps. 38–40)*

**HP:** 30 / 30

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 14 |
| Destreza (DES) | 20 |
| Inteligência (INT) | 4 |
| Sobrevivência (SOB) | 16 |
| Percepção (PER) | 18 |
| Carisma (CAR) | 1 |

### Combate
- **DC de Defesa:** 17 *(velocidade extrema em correntes de vento — difícil de mirar)*
- **Dano por Turno:** 6 *(tipo: Elétrico — Descarga estática de suas membranas alares)*
- **Acerto Crítico:** Sobrecarga nos sistemas da nave — `-10% energy_reserves` imediatamente e todos os sistemas ficam instáveis por 1 turno (DCs aumentam em +2).
- **Threshold Moral:** Nunca (Boss em bando — não foge, reorganiza)
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** Biológico
- **Arco / Capítulo:** Arco 3 — Caps. 38 a 40 (Gigante Gasoso)
- **Habitat:** Correntes de vento supersônicas nas camadas superiores do gigante gasoso. Vivem e caçam em bandos de 4–8.
- **Comportamento:** Territorial em relação a objetos metálicos (a nave gera campo eletromagnético que os atrai). Atacam em mergulho a partir das nuvens — primeiro ataque é sempre surpresa (PER DC 15 para detectar antes do impacto).
- **Fraqueza:** Dentro das correntes de vento opostas (DES DC 15 para navegar), sua velocidade os desorientar — ficam vulneráveis por 1 turno. Pulso EMP os incapacita completamente por 2 turnos mas drena `-20% energy_reserves` da nave.
- **Drop (Loot):** Nenhum *(corpo desintegra na atmosfera após a morte)*.

---
## Nome: Caçador Cego *(Caps. 47–49)*

**HP:** 22 / 22

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 16 |
| Destreza (DES) | 14 |
| Inteligência (INT) | 2 |
| Sobrevivência (SOB) | 18 |
| Percepção (PER) | 20 |
| Carisma (CAR) | 1 |

### Combate
- **DC de Defesa:** 15
- **Dano por Turno:** 5 *(tipo: Físico — Garras adaptadas ao frio absoluto. Cada golpe também aplica `-1 HP` por turno por hipotermia por 3 turnos, acumulativo)*
- **Acerto Crítico:** Hipotermia aguda — aplica status `Congelando`. Sem fonte de calor no próximo turno: `-5 HP` adicional e -3 em todos os testes.
- **Threshold Moral:** 30% (Biológico)
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** Biológico
- **Arco / Capítulo:** Arco 3 — Caps. 47 a 49 (Mundo Órfão)
- **Habitat:** Superfície de rocha negra sob escuridão absoluta. Temperatura: -180°C.
- **Comportamento:** Completamente cego para luz (não existe luz neste planeta). Caça por ecolocalização ultrassônica e calor corporal. A nave e Ferro irradiam calor detectável a centenas de metros.
- **Fraqueza:** Reduzir a assinatura térmica ao mínimo (Engineering DC 15 para desligar sistemas não essenciais) os desorientar. Fonte de fogo/calor intenso os repele por 2 turnos — paradoxalmente, a mesma coisa que os atrai de longe os cega de perto.
- **Drop (Loot):** Pele Isolante × 2 *(extraída nos primeiros segundos após o abate, antes do corpo congelar)*.

## CLASSE D: ANOMALIAS (Física Quebrada)

---
## Nome: Eco Temporal *(Caps. 50–52)*

**HP:** ??? / ???

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | ??? |
| Destreza (DES) | 20 |
| Inteligência (INT) | ??? |
| Sobrevivência (SOB) | ??? |
| Percepção (PER) | 20 |
| Carisma (CAR) | ??? |

### Combate
- **DC de Defesa:** ??? *(ataques físicos ineficazes — é uma projeção temporal do próprio jogador)*
- **Dano por Turno:** Espelha o dano que o jogador causaria a si mesmo *(tipo: Anomalia)*
- **Acerto Crítico:** Dilatação temporal — jogador perde 2 turnos enquanto o Eco age livremente.
- **Threshold Moral:** Nunca (Anomalia)
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** Anomalia
- **Arco / Capítulo:** Arco 3 — Caps. 50 a 52 (Horizonte de Eventos)
- **Habitat:** Zona de distorção gravitacional extrema próxima ao buraco negro.
- **Comportamento:** Replica decisões passadas do jogador. Não pode ser destruído — apenas superado.
- **Fraqueza:** Ação `Ceder` encerra o confronto sem custo. Combatê-lo prolonga o dano. Chip (INT DC 18) prevê próximo movimento.
- **Drop (Loot):** Nenhum *(resolução abre rota para manobra de estilingue)*.

---
## Nome: Nano-Assimilador *(Boss Final — Caps. 53–55)*

**HP:** ??? / ???

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 1 |
| Destreza (DES) | 20 |
| Inteligência (INT) | 20 |
| Sobrevivência (SOB) | ??? |
| Percepção (PER) | 20 |
| Carisma (CAR) | ??? |

### Combate
- **DC de Defesa:** ??? *(não possui forma física — é o planeta inteiro)*
- **Dano por Turno:** `-5% suit_integrity` e `-1 HP` por turno que o jogador permanecer no planeta *(tipo: Biológico — assimilação molecular)*
- **Acerto Crítico:** Nanobots infiltram o chip — CHRONOS-7 reporta leituras falsas por 3 turnos (INT DC 20 para detectar).
- **Threshold Moral:** Nunca (Anomalia — é o planeta inteiro)
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** Anomalia
- **Arco / Capítulo:** Arco 3 — Caps. 53 a 55 (Paraíso Artificial — Boss Final)
- **Habitat:** O planeta inteiro.
- **Comportamento:** Passivo até o jogador reconhecer a ilusão. Depois disso, assimilação ativa em todos os sistemas.
- **Fraqueza:** Não pode ser derrotado — apenas escapado. Decolagem imediata é a única saída. Cada turno extra aumenta dano permanente à nave.
- **Drop (Loot):** Nenhum *(êxodo bem-sucedido é a recompensa)*.

---
## Nome: Colônia Gasosa *(Anomalia — Caps. 38–39)*

**HP:** ??? / ???

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | 1 |
| Destreza (DES) | 6 |
| Inteligência (INT) | 8 |
| Sobrevivência (SOB) | ??? |
| Percepção (PER) | 16 |
| Carisma (CAR) | ??? |

### Combate
- **DC de Defesa:** ??? *(entidade gasosa — imune a projéteis e físico)*
- **Dano por Turno:** 0 direto *(tipo: Anomalia — corrói o casco da nave: `-3% hull_integrity` por turno de contato)*
- **Acerto Crítico:** Penetra nas juntas do casco — sistema de pressurização da nave entra em alerta (`-15 hull_integrity` imediatamente).
- **Threshold Moral:** Nunca (Anomalia)
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** Anomalia / Biológico
- **Arco / Capítulo:** Arco 3 — Caps. 38 a 39 (Gigante Gasoso — zona de névoa densa)
- **Habitat:** Camadas inferiores do gigante gasoso onde pressão é alta o suficiente para compactar gases em pseudo-colônias.
- **Comportamento:** Não inteligente no sentido convencional — reage a calor (motores da nave). Envolve a nave gradualmente. Não pode ser combatida diretamente.
- **Fraqueza:** Desligar motores e derivar por 1 turno a faz se dissipar (perde a fonte de calor). Manter velocidade máxima (DES DC 14) atravessa a colônia em 1 turno com dano reduzido (-1 hull em vez de -3).
- **Drop (Loot):** Nenhum.

---
## Nome: O Silêncio *(Boss Ambiental — Cap. 49)*

**HP:** ??? / ???

### Atributos
| Atributo | Valor |
|:---|:---:|
| Força (FOR) | ??? |
| Destreza (DES) | ??? |
| Inteligência (INT) | ??? |
| Sobrevivência (SOB) | ??? |
| Percepção (PER) | ??? |
| Carisma (CAR) | ??? |

### Combate
- **DC de Defesa:** ??? *(não é uma entidade — é o ambiente inteiro)*
- **Dano por Turno:** `-3 HP` por turno sem fonte de calor ativa *(tipo: Físico — hipotermia progressiva)* + `-1% energy_reserves` extra por dilatação do frio nos sistemas
- **Acerto Crítico:** N/A — o "boss" é a situação, não uma criatura.
- **Threshold Moral:** Nunca (Anomalia ambiental)
- **Fase 2 (Boss):** Não

### Informações de Campo
- **Classe:** Anomalia
- **Arco / Capítulo:** Arco 3 — Cap. 49 (Mundo Órfão — clímax do arco)
- **Habitat:** Planeta inteiro. Ausência de luz, calor e som externo.
- **Comportamento:** O Silêncio não age — ele espera. Qualquer sistema não essencial consome energia extra para manter temperatura operacional. A ameaça real é a matemática: energia limitada vs frio infinito.
- **Fraqueza:** Decolagem antes que a energia caia abaixo de 20% (Cap. 49). O chip (INT DC 16) pode calcular a janela exata antes que os sistemas congelem.
- **Drop (Loot):** Nenhum *(sobreviver ao Mundo Órfão é a recompensa — o chip desbloqueia função de mapeamento térmico após o arco)*.

---

## APÊNDICE: SCHEMA DE DROPS DE COMBATE

> **INSTRUÇÃO AO ARCHITECT:** Quando um inimigo morrer e seu `Drop (Loot)` precisar ser adicionado ao `inventory.csv`, use os schemas abaixo como fonte de verdade. PROIBIDO inventar campos. Se o item não estiver listado aqui, crie a entrada completa antes de persistir.

---

### Arco 1 — Selva Primitiva

| id* | name | type | rarity | weight_kg | effect | usable | notes |
|:---:|:---|:---|:---:|:---:|:---|:---:|:---|
| — | Couro Bruto | Material | Comum | 0.8 | Crafting primitivo. Pode ser improvisado como armadura leve (-1 dano recebido). | false | Drop: Predador Selva. |
| — | Osso Denso | Material | Comum | 0.4 | Componente estrutural primitivo. Pode fabricar ponta de lança ou ferramenta. | false | Drop: Javali Blindado, Predador Alfa. |
| — | Lança Primitiva | Arma | Comum | 1.2 | +2 em testes de Combate ranged (arremesso). Alcance: 1 turno de distância. | false | Equipar em weapon_primary ou secondary. Drop: Guerreiro Tribal. |
| — | Erva Medicinal | Consumível | Comum | 0.1 | Remove status `Envenenado` ou recupera +3 HP se usado como ação. | true | Drop: Guerreiro Tribal. Ingrediente para cura primitiva. |
| — | Carapaça Térmica | Equipamento Passivo | Incomum | 1.5 | -2 de dano recebido do tipo Físico quando equipada. Resistente a fogo. | false | Drop: Predador Alfa. Equipar como armor no character_sheet.json. |

---

### Arco 2 — Nova Carthage

| id* | name | type | rarity | weight_kg | effect | usable | notes |
|:---:|:---|:---|:---:|:---:|:---|:---:|:---|
| — | Cargas de Rifle | Consumível | Incomum | 0.05 | Munição para Rifle Energético. 1 carga = 1 ataque ranged. | true | Drop: Mercenário Corporativo (×4). Sem arma = sem uso. |
| — | Chip de IA Corrompido | Quest | Raro | 0.1 | Sem efeito mecânico. Alto valor de troca com facções tech. | false | Drop: Drone de Vigilância. Registrar em active_quests.md. |
| — | Módulo de Blindagem | Equipamento Passivo | Raro | 0.9 | -3 de dano recebido do tipo Balístico quando integrado à nave ou traje. | false | Drop: Exoesqueleto Elite. Requer Engineering DC 12 para instalar. |

---

### Arco 3 — Planetas

| id* | name | type | rarity | weight_kg | effect | usable | notes |
|:---:|:---|:---|:---:|:---:|:---|:---:|:---|
| — | Carapaça Ácido-Resistente | Material | Raro | 1.8 | Revestimento anti-ácido para nave ou traje. -3 suit_integrity por turno → 0 quando instalada. | false | Drop: Leviatã da Ferrugem (×3). Necessária Cap. 28. |
| — | Cristal Sônico | Material | Raro | 0.3 | Componente para armas sônicas e motores experimentais. | false | Drop: Espectro de Gelo (×2). Receita disponível Cap. 34. |
| — | Membrana Orgânica | Material | Incomum | 0.5 | Isolante biológico. Revestimento de casco: -1 dano de impacto em gravidade zero. | false | Drop: Criatura do Vácuo (×2). |
| — | Escama de Abismo | Material | Raro | 1.2 | Blindagem contra pressão extrema. Necessária para descer abaixo de 800m no Abismo Oceânico. | false | Drop: Leviatã das Profundezas (×2). |
| — | Glândula Elétrica | Material | Incomum | 0.2 | Componente para armas de choque improvisadas. Receita disponível Cap. 40. | false | Drop: Revoada Relâmpago (×1 por unidade). |
| — | Pele Isolante | Material | Incomum | 0.6 | Isolamento térmico extremo. -2 HP por turno no Mundo Órfão → 0 quando integrada ao traje. | false | Drop: Caçador Cego (×2). Essencial para sobrevivência Caps. 47–49. |
| — | Biomassa Fúngica Viva | Material | Raro | 0.4 | Integração simbiótica com sistemas da nave. Efeito: +5% energy_reserves por turno passivo. | false | Drop: Parasita Mental Fúngico (após dominação). Requer Engineering DC 14 para instalar. |

---

> *O campo `id` é atribuído sequencialmente pelo Architect no momento da adição ao `inventory.csv`. Nunca reutilize IDs deletados.