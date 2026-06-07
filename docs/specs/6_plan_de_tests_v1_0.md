# Plan de tests — Bitcoin Retirement Forecast (migration Python)

**Projet :** Bitcoin Retirement Forecast (application Python)
**Périmètre :** Système complet — non-régression par module (Moteur de prix, Flux), sensibilité de calibration (MM_WINDOW), limites et rejets par module, intégration/contrat
**Version :** v1.0
**Date :** 4 juin 2026
**Documents parents :** Cadrage v2.1 ; REF v1.0 (réf. moteur de prix) ; `forecast_bear_final.ods` (pilote, oracle moteur) ; `Bitcoin_Subsidy.ods` (réf. flux, oracle flux — profils Yoan/Charles) ; Spec Synchronisation v1.3 ; Spec Agrégation v1.2 ; Spec Flux **v1.1** ; Spec Moteur de prix v1.0
**Convention de langue :** identifiants de test, noms de champs et logs en **anglais** ; prose en **français**.
**Statut :** Prêt pour validation.

---

## 1. Objectifs de la campagne de tests

Verrouiller les **critères d'acceptation avant toute ligne de code** (garde-fou principal contre le risque « Haut » de dérive Python ↔ fichiers de référence, cadrage §7). Cinq familles :

| Famille | Objet | Nature | Risque cadrage |
|---|---|---|---|
| **TF1** | Non-régression **Moteur de prix** vs pilote `forecast_bear_final.ods` | Unitaire + golden file | Haut |
| **TF2** | Non-régression **Flux** vs `Bitcoin_Subsidy.ods` (Yoan, Charles) | Unitaire + golden file | Haut |
| **TF3** | Sensibilité **`MM_WINDOW_YEARS`** ∈ {4, 6, 8, 6\pic2021} | **Descriptive (non bloquante)** | Décision Niko |
| **TF4** | **Limites & rejets** par module (Synchro / Agrégation / Moteur / Flux) | Unitaire | Moyen/Haut |
| **TF5** | **Intégration / contrat** + chevauchement (synthétique) + non-déterminisme | Intégration | Haut |

**Deux points structurels actés (cadrage B5) :**

1. **Pas d'oracle « end-to-end » dans un seul fichier.** Le pilote valide le **moteur** (prix) mais sa propre colonne flux tourne avec stack = 15 / runway ∞ et **n'est pas** la référence de flux (DEC-SOURCES-01). Subsidy valide le **flux** mais **avec son propre modèle de prix** (colonne F, « Saylor's Forecast »), pas le moteur Bear. La chaîne combinée est donc validée **par composition** (chaque tête sur son domaine) + tests synthétiques d'intégration, **jamais** contre un golden file unique.
2. **Non-déterminisme assumé.** La non-régression est **structurelle**, au point fixe `anchor_year = 2025`. En production, ancre et MM viennent du glissant : le modèle **diverge alors volontairement** de REF (objectif de la migration, cadrage). Les tests de non-régression ne valident donc *pas* la production glissante — ils valident que la **mécanique** reproduit le pilote quand on lui réinjecte les entrées du pilote.

**Horizon de test = 2072** (= horizon produit verrouillé). Couverture intégrale : les runways de référence tombent tôt (Yoan 2038, Charles 2045, **vérifié**) et la récurrence de flux est uniforme — aucune perte de couverture vs 2100.

---

## 2. Cas de test nominaux

### 2.1 TF1 — Non-régression Moteur de prix (point fixe `anchor_year = 2025`)

**Double injection** (les entrées du pilote, réinjectées comme scalaires) :
`anchor_year = 2025` · `anchor_price = 101 700` (= `L35`) · `mm_anchor = 0,361334851…` (= `C12`, MM4) · constantes Bear aux valeurs du pilote (exposant 5,7675 / origine 2008 / discount 0,60 / blend 6 / plateau 3 % = `F7` / année plateau 2055 = `F8` / origine sigmoïde 2026).

| ID | Description | Input | Output attendu (oracle) | Prio |
|---|---|---|---|---|
| MOT-NR-001 | ARR théorique annuel | années 2026–2072 | reproduit `K37:K83` ; spot 2026 = **0,210231258** (21,02 %) | Haute |
| MOT-NR-002 | Prix nominal capitalisé | années 2026–2072 | reproduit `L37:L83` ; spot 2026 = **123 080,52 $** ; 2072 ≈ **2 373 743 $** | Haute |
| MOT-NR-003 | Année d'ancre sans ARR théo | 2025 | `nominal_price(2025) = anchor_price = 101 700` (pas d'ARR appliqué à l'ancre — garde anti-bug V4 côté prix) | Haute |
| MOT-NR-004 | Diagnostics sigmoïde | — | `sigmoid_midpoint = 2040,5` ; `k = ln(19)/14,5` (rails calendaires figés, option B) | Moyenne |

### 2.2 TF2 — Non-régression Flux (profils Yoan & Charles)

**Méthode d'isolation (validée) :** injecter la **colonne F résolue de Subsidy** comme vecteur `nominal_price(année)` (fixture de prix gelée), pour reproduire `J/K/L/M` **bit-exact** indépendamment du modèle de prix. Vecteurs de paramètres (**vérifié** dans les feuilles) :

| Paramètre | Yoan (Paris) | Charles (NY) |
|---|---|---|
| `initial_stack` | 0,1 BTC | 1 BTC |
| `monthly_dca` | 500 | 3 000 |
| `dca_growth_rate` | 5 % | 5 % |
| `dca_end_year` | 2031 | 2031 |
| `btc_spending_start_year` | 2032 | 2032 |
| `monthly_living_cost` | 2 500 | 12 000 |
| `spending_growth_rate` | 8 % | 8 % |
| `inflation_rate` | 3 % | 3 % |

| ID | Description | Output attendu (oracle) | Prio |
|---|---|---|---|
| FLX-NR-Y-001 | Entrées BTC (`btc_in`, incl. injection ancre) | reproduit colonne `J` Yoan, 2025–2072 | Haute |
| FLX-NR-Y-002 | Sorties BTC (`btc_out`) | reproduit colonne `K` Yoan | Haute |
| FLX-NR-Y-003 | Stack net cumulé | reproduit colonne `L` Yoan | Haute |
| FLX-NR-Y-004 | Portefeuille | reproduit colonne `M` Yoan | Haute |
| FLX-NR-Y-005 | **Runway** | 1ʳᵉ année stack < 0 = **2038** ; `runway = 13` | Haute |
| FLX-NR-C-001…004 | `J/K/L/M` Charles | reproduit colonnes Charles, 2025–2072 | Haute |
| FLX-NR-C-005 | **Runway** Charles | 1ʳᵉ année stack < 0 = **2045** ; `runway = 20` | Haute |
| FLX-NR-X-001 | Composition dépense (DEC-DCA-03) | `cdv_train` compose inflation 3 % × croissance 8 % (vérifié via reproduction de `K`) | Haute |

### 2.3 TF3 — Campagne de sensibilité `MM_WINDOW_YEARS` (descriptive, non bloquante)

Le moteur consomme `mm_anchor` comme **scalaire** (agnostique à la fenêtre, Agrégation v1.2). On balaie la fenêtre **sans toucher au moteur**, sur la série d'ARR historiques (colonne `J` du pilote). **Fil rouge quantifié (vérifié) :** MM4 = **36,13 %** → ARR 2026 = **21,0 %** ; MM6 = **86,9 %** (la fenêtre 6 réabsorbe le +326,7 % de 2021) → ARR 2026 ≈ **46 %**. Effet : le « Bear » est nettement **moins** bearish en début de projection avec MM6.

| ID | `MM_WINDOW_YEARS` | Mesures rapportées |
|---|---|---|
| SENS-MM-4 | 4 (héritage MM4) | `mm_anchor`, ARR 2026, prix nominal à 2030/2040/2050/2072, runway (profil flux de réf.) |
| SENS-MM-6 | 6 (défaut V1) | idem |
| SENS-MM-8 | 8 | idem |
| SENS-MM-6X | 6 **hors pic 2021** | idem (variante d'exclusion du blow-off) |

> **Sortie = tableau comparatif descriptif.** Pas de seuil de rejet automatique. La **décision finale de calibration** (`MM_WINDOW_YEARS` retenu en V1) est `[OUVERT]` — elle revient à Niko, sur lecture des résultats. Principe : *valider un label de scénario contre ses valeurs projetées, pas contre sa description.*

---

## 3. Cas de test aux limites

### 3.1 Flux — comportements limites

| ID | Cas | Définition | Output attendu | Prio |
|---|---|---|---|---|
| LIM-FLX-01 | **Bankrun au bord d'horizon** `[DÉCISION — à valider]` | profils **synthétiques** : (A) épuise en 2070-2071 ; (B) épuiserait en 2073 | (A) `runway` fini (≈ 45-46) ; (B) `runway = ∞` *dans la fenêtre 2072* (illustre l'enjeu d'un élargissement à 2100). Oracle = recomputation indépendante | Haute |
| LIM-FLX-02 | **Pas de DCA** | `monthly_dca = 0` | drawdown pur = comportement REF ; seuls stack initial + dépenses jouent | Haute |
| LIM-FLX-03 | **DCA, départ 0 BTC** | `initial_stack = 0`, `monthly_dca > 0` | **nominal valide (Flux v1.1)** : `stack = Σ btc_in_dca` (accumulation pure depuis zéro) | Haute |
| LIM-FLX-04 | **Runway infini** | gros stack / faibles dépenses | stack jamais < 0 sur l'horizon → `runway = ∞` | Moyenne |
| LIM-FLX-05 | **Retraite « année 0 »** | `spending_start = anchor_year + 1` | consommation dès la 1ʳᵉ année projetée (`C = 1`, jamais `C = 0`) | Moyenne |
| LIM-FLX-06 | **Hold pur** | `dca_end < spending_start` avec gap | années intermédiaires sans flux ; stack revalorisé par le prix seul | Moyenne |
| LIM-FLX-07 | **Chevauchement** | `dca_end ≥ spending_start` | → traité en **TF5** (synthétique, sans oracle de référence) | Haute |

> **Note quirk pilote (documenté, dormant) :** dans Subsidy, l'ancre teste `B<dca_end` (strict) alors que les années projetées testent `≤`. La borne `dca_end` est **inclusive** côté spec (Flux §4.1) ; le `<` de l'ancre est dormant (l'ancre 2025 ≠ `dca_end` 2031 dans les profils de réf.) et n'affecte aucun vecteur de non-régression.

### 3.2 Synchronisation — limites

| ID | Cas | Condition | Output attendu | Prio |
|---|---|---|---|---|
| LIM-SYNC-01 | Volume hors plage | nb points < 360 ou > 370 | **WARN non bloquant** `SYNC_VOLUME_WARN` ; poursuite si clôtures dérivables | Moyenne |
| LIM-SYNC-02 | Fraîcheur dégradée | point récent daté 1–6 j | **WARN non bloquant** `SYNC_STALE_WARN` ; poursuite | Moyenne |
| LIM-SYNC-03 | Interpolation bornée | mois absent encadré de deux `real` | interpolation linéaire, `origin = interpolated` | Haute |
| LIM-SYNC-04 | Trou non bornable | mois absent sans deux bornes `real` | reste `absent`, signalé | Haute |
| LIM-SYNC-05 | Mois en cours non clos | mois courant UTC | ignoré, jamais stocké ni calculé | Haute |
| LIM-SYNC-06 | Priorité `real` | mois déjà `real` en base | jamais écrasé (ni par récup., ni par interpolation) | Haute |

### 3.3 Agrégation — limites

| ID | Cas | Condition | Output attendu | Prio |
|---|---|---|---|---|
| LIM-AGG-01 | Profondeur MM dérivée | `(W−1)×12 + 24` mois (**84 pour W=6**) | `mm_anchor` calculable ; en deçà → non calculable (cas théorique impossible depuis 2010) | Haute |
| LIM-AGG-02 | ARR glissant | < 24 mois clos | ARR non calculable pour la date | Moyenne |
| LIM-AGG-03 | Moyenne annuelle | < 12 mois clos | moyenne non calculable | Moyenne |
| LIM-AGG-04 | Balayage fenêtre | W ∈ {4,6,8} | profondeur recalculée auto (60/84/108) ; moteur inchangé | Moyenne |

### 3.4 Moteur de prix — limites

| ID | Cas | Condition | Output attendu | Prio |
|---|---|---|---|---|
| LIM-MOT-01 | `ARR_FLOOR` | ARR calculé < 3 % | ramené au plateau via `MAX(…; PLATEAU_ARR)` ; nominal, pas une erreur ; spot années tardives ARR → 3,00 % | Haute |
| LIM-MOT-02 | Lancement post-plateau | `anchor_year ≥ 2055` | sigmoïde ≈ 1 sur tout l'horizon → `ARR_théo ≈ 3 %` ; comportement sain | Moyenne |
| LIM-MOT-03 | `SIGMOID_GUARD` | `PLATEAU_YEAR − midpoint ≤ ε` | **inactif sous option B** (dénominateur = 14,5 constant) ; documenté, non déclenchable en V1 | Faible |
| LIM-MOT-04 | `POWERLAW_DIV0` | année = 2009 (`t−1 = 0`) | **inatteignable** : projection démarre à `anchor_year+1 ≥ 2026` | Faible |

---

## 4. Cas de test d'erreur (rejets)

| ID | Motif (EN) | Condition | Output attendu | Prio |
|---|---|---|---|---|
| ERR-FLX-01 | Paramètre obligatoire manquant | `initial_stack` / `spending_start` / `living_cost` / `spending_growth` / `inflation` absent | calcul non lancé ; signalé UI | Haute |
| ERR-FLX-02 | `dca_end` manquant avec DCA actif | `monthly_dca > 0` et `dca_end_year` vide | rejet de saisie | Haute |
| ERR-FLX-03 | Stack initial invalide | `initial_stack < 0` | rejet (plage `≥ 0`, Flux v1.1) — `= 0` n'est **pas** un rejet | Haute |
| ERR-SYNC-01 | `SYNC_STRUCT_ERR` | `prices` absent / format inattendu | **bloquant** → mode dégradé, base conservée | Haute |
| ERR-SYNC-02 | `SYNC_GRANULARITY_ERR` | écart médian ≠ ~24 h (±10 %) | **bloquant** → mode dégradé | Haute |
| ERR-SYNC-03 | `SYNC_API_ERR` | réseau / API / rate limit | **bloquant** → mode dégradé, pas de retry ; interpolation étape 2 quand même | Haute |
| ERR-AGG-01 | Profondeur insuffisante | < 84 mois (W=6) | `mm_anchor` non calculable, signalé | Moyenne |
| ERR-MOT-01 | `ANCHOR_MISSING` | `anchor_price` absent ou ≤ 0 | calcul non lançable, signalé (dépend d'Agrégation) | Haute |
| ERR-MOT-02 | `MM_MISSING` | `mm_anchor` absent | calcul non lançable, signalé | Haute |

---

## 5. Critères d'acceptation

Formulés en binaire (vrai/faux). Tolérances **validées** :

- **Prix (USD)** : arrondi au cent puis **égalité exacte**, doublé d'une garde diagnostique `|Δ brut| / |ref| ≤ 1e-9` (sépare un écart de modèle d'un artefact d'arrondi).
- **ARR (taux) et quantités BTC** : tolérance **relative ≤ 1e-9**.

Conditions nécessaires et suffisantes :

- [ ] **TF1** : `MOT-NR-001/002/003` passent — `K37:K83` et `L37:L83` reproduits dans la tolérance ci-dessus.
- [ ] **TF2** : `FLX-NR-Y-*` et `FLX-NR-C-*` passent — `J/K/L/M` reproduits (BTC : rel ≤ 1e-9 ; USD : au cent) ; **runways exacts** (Yoan 2038 / `13`, Charles 2045 / `20`).
- [ ] **TF4/TF5** : tous les cas de priorité **Haute** passent ; aucun **rejet non documenté** produit.
- [ ] **Déterminisme** : aucun appel réseau en test (CoinGecko mocké) ; exécutions reproductibles à l'identique.
- [ ] **TF3** : tableau de sensibilité produit pour les 4 fenêtres (critère = *livré et lisible*, **pas** un seuil — la décision de calibration est hors recette).
- [ ] **Cohérence de contrat** : les champs de jointure (`mm_anchor`, `anchor_year`, `anchor_price` → `nominal_price` → flux) circulent aux types attendus (TF5).

---

## 6. Données de test

**Principe : geler les oracles une fois, les versionner.** Les `.ods` ne sont **pas** relus à chaque exécution — un script d'extraction (odfpy) en sort des **fixtures figées** (JSON/CSV) déposées sous `tests/fixtures/`, sous contrôle de version. Cela garantit la stabilité de l'oracle et l'indépendance vis-à-vis de LibreOffice.

| Fixture | Source | Contenu | Usage |
|---|---|---|---|
| `moteur_pointfixe.json` | `forecast_bear_final.ods` | injection (2025 / 101 700 / 0,3613 + constantes Bear) + oracle `K37:K83`, `L37:L83` | TF1 |
| `flux_yoan.json` | Subsidy / Yoan | 8 paramètres + **vecteur prix = colonne F résolue** 2025–2072 + oracle `J/K/L/M` + runway | TF2 |
| `flux_charles.json` | Subsidy / Charles | idem Charles | TF2 |
| `arr_historique.json` | `forecast_bear_final.ods` col `J` | série ARR 2011–2025 (+ variante sans 2021) | TF3 |
| `coingecko_*.json` | mock | réponses `market_chart` synthétiques (journalier OK / granularité KO / volume bas / trous) | TF4 Synchro |
| profils synthétiques | construits | bord d'horizon (LIM-FLX-01), chevauchement (TF5) | oracle = **recomputation indépendante** (implémentation de contrôle / calcul manuel), pas un golden file |

> **Oracle synthétique = plus faible.** Les profils construits (bord, chevauchement) valident l'**implémentation des formules** de la spec (détecte les bugs de code), pas la justesse de la spec elle-même. À garder en tête pour LIM-FLX-01 et la couverture du chevauchement (nouvelle capacité v2.1 **sans** oracle de référence).

---

## 7. Environnement de test

- **Framework** : `pytest` `[HYPOTHÈSE]` (à confirmer en spec technique) ; version Python idem.
- **Réseau** : **aucun appel réel**. CoinGecko entièrement mocké par fixtures `market_chart`. Garantit le déterminisme et l'exécution hors-ligne.
- **Comparaison numérique** : helper de tolérance unique (`assert_usd_cent`, `assert_rel(1e-9)`), appliqué uniformément.
- **Indépendance des tests** : chaque test autonome ; seul prérequis = génération des fixtures (étape amont, hors campagne de recette).
- **Constantes d'intégrité Bear** : injectées comme configuration de test figée ; le balayage `MM_WINDOW_YEARS` (TF3) passe par cette config, jamais par une saisie utilisateur.

---

## 8. Questions ouvertes

- [OUVERT] **Décision de calibration `MM_WINDOW_YEARS`** (résultat de TF3) → Niko, sur lecture des mesures.
- [à valider] **LIM-FLX-01** — interprétation « bord d'horizon » (profils A/B autour de 2072).
- [ ] Framework de test exact (`pytest`) + version Python → spec technique.
- [ ] Convention d'arrondi au cent (half-up vs banker's) → spec technique (impact marginal vu la marge).
- [ ] Tactique d'extraction des fixtures (script versionné vs régénération à la demande) → spec technique.

---

## 9. Décisions tranchées (séance B5)

- ✅ **Séquencement** : plan de tests **avant** spec technique (critères d'acceptation = garde-fou).
- ✅ **Horizon** produit **2072** (config réélargissable à 2100 après tests) ; tests à 2072, couverture intégrale.
- ✅ **Tolérance** : prix au cent + garde `1e-9` relatif ; ARR/BTC `1e-9` relatif.
- ✅ **TF2** isolée par **injection de la colonne F** de Subsidy (sépare flux et prix).
- ✅ **TF3** descriptive, **non bloquante** ; décision de calibration séparée de la recette.
- ✅ **Pas d'oracle end-to-end** : validation **par composition** + tests synthétiques.
- ✅ **Flux `initial_stack ≥ 0`** → Spec Flux **v1.1** (débloque LIM-FLX-03 en cas nominal).

---

## 10. Glossaire (termes de test)

| Terme | Définition |
|---|---|
| **Oracle** | Valeur de référence attendue contre laquelle on compare la sortie Python |
| **Golden file** | Oracle figé extrait d'un fichier de référence (ici les `.ods`), gelé en fixture |
| **Point fixe** | Jeu d'entrées (`anchor_year=2025`, etc.) où la migration doit reproduire le pilote au cent près |
| **Non-régression structurelle** | Reproduction de REF en réinjectant ancre + MM aux valeurs du pilote, indépendamment de la taille de fenêtre MM |
| **Oracle synthétique** | Attendu recomputé indépendamment (pas de fichier de référence) ; valide l'implémentation, pas la spec |
| **Fixture** | Donnée de test gelée et versionnée (JSON/CSV), extraite une fois des sources |

---

*Plan de tests v1.0. Prêt pour validation. Une fois validé : spec(s) technique(s) — schéma base SQLite, stack web, version Python, packaging GitHub MIT, attribution CoinGecko.*
