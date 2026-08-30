# Priory Schema & Reference Ontology Additions (Proposals)

This document formalizes the ontology extensions identified during blind extraction trials on player-written guides and unstructured domain prose.

The corresponding W3C RDF Turtle files are prepared in:
- **TBox Schema (`gw2-priory-def`)**: [`ontologies/proposals/priory_def_additions.ttl`](file:///Users/clementd/Documents/GitHub/gw2-ume/ontologies/proposals/priory_def_additions.ttl)
- **ABox Controlled Vocabularies (`gw2-priory-ref`)**: [`ontologies/proposals/priory_ref_additions.ttl`](file:///Users/clementd/Documents/GitHub/gw2-ume/ontologies/proposals/priory_ref_additions.ttl)

---

## 1. TBox Extensions (`gw2-priory-def`)

### 1.1 Attribute Combinations & Stat System
```turtle
priory:AttributeCombination a owl:Class ;
    rdfs:label "Attribute Combination"@en ;
    skos:altLabel "Stat Prefix"@en , "Stat Combination"@en , "Prefix"@en ;
    rdfs:comment "A standardized set of combat attributes assigned to equipment in Guild Wars 2."@en .

priory:Attribute a owl:Class ;
    rdfs:label "Combat Attribute"@en ;
    skos:altLabel "Stat"@en ;
    rdfs:comment "Primary or secondary combat attribute (Power, Precision, Ferocity, etc.)."@en .

priory:ExpansionRelease a owl:Class ;
    rdfs:label "Expansion Release"@en ;
    rdfs:comment "Game release tier (Core, Heart of Thorns, Path of Fire, etc.)."@en .

# Predicates
priory:hasAttribute a owl:ObjectProperty ;
    rdfs:domain priory:AttributeCombination ;
    rdfs:range priory:Attribute .

priory:hasAscendedPrefix a owl:DatatypeProperty ;
    rdfs:domain priory:AttributeCombination ;
    rdfs:range xsd:string .

priory:hasExoticPrefix a owl:DatatypeProperty ;
    rdfs:domain priory:AttributeCombination ;
    rdfs:range xsd:string .

priory:releasedInExpansion a owl:ObjectProperty ;
    rdfs:domain priory:AttributeCombination ;
    rdfs:range priory:ExpansionRelease .

priory:hasAttributeCombination a owl:ObjectProperty ;
    rdfs:domain priory:EquipableItem ;
    rdfs:range priory:AttributeCombination .
```

---

## 2. ABox Reference Vocabularies (`gw2-priory-ref`)

### 2.1 Meta Stat Prefixes & Lore Mappings
* **Berserker's** (`priory-ref:stat/berserker`): Exotic `Berserker's` $\leftrightarrow$ Ascended `Zojja's` (Power, Precision, Ferocity).
* **Viper's** (`priory-ref:stat/viper`): Exotic `Viper's` $\leftrightarrow$ Ascended `Yassith's` (Power, Condition Damage, Precision, Expertise).
* **Harrier's** (`priory-ref:stat/harrier`): Exotic `Harrier's` $\leftrightarrow$ Ascended `Zehtuka's` (Power, Healing Power, Concentration).
* **Marauder** (`priory-ref:stat/marauder`): Exotic `Marauder` $\leftrightarrow$ Ascended `Svaard's` (Power, Precision, Vitality, Ferocity).
* **Diviner's** (`priory-ref:stat/diviner`): Exotic `Diviner's` $\leftrightarrow$ Ascended `Forgemaster's` (Power, Concentration, Precision, Ferocity).

### 2.2 Expansion & Progression Currencies
* **Living World**: `Unbound Magic`, `Volatile Magic`, `Fresh Winterberry`, `Eternal Ice Shard`, `Bandit Crest`.
* **Fractals & Raids**: `Pristine Fractal Relic`, `Fractal Relic`, `Magnetite Shard`.
* **WvW & Guild**: `Badge of Honor`, `Guild Commendation`, `Tyrian Defense Seal`.
