# Bitcoin Retirement Forecast

## Projet
Application Python **web-locale** : maintient une base SQLite de clôtures mensuelles BTC/USD (depuis 2010), se synchronise au lancement via CoinGecko **keyless**, et projette la viabilité d'une retraite en BTC (scénario **Bear**, drawdown + DCA optionnel) jusqu'à 2072. Reprise d'un modèle tableur existant. Dépôt GitHub, licence **MIT**.

## Stack
- **Python 3.x**
- **Flask** (routes) + **waitress** (serveur WSGI — JAMAIS le serveur de dev Flask, même en local)
- **SQLite** (clôtures mensuelles persistées)
- **requests** (CoinGecko ; `timeout=(5, 10)` **obligatoire**)
- **Pydantic** (validation des paramètres utilisateur de flux)
- **webbrowser** (stdlib ; ouvre l'onglet au démarrage, **après** que waitress écoute)
- **python-dotenv** (lecture *optionnelle* d'une clé CoinGecko ; jamais requise)
- Frontend : `btc_dashboard.html` (Chart.js) — à recâbler sur `/api/forecast`

## Commandes
- Lancer : `python run.py` → waitress sur `127.0.0.1:8000` (**fallback bind incrémental** 8001, 8002… si occupé) → ouvre un onglet navigateur
- Tests : `pytest tests/ -v`
- Liaison réseau : `127.0.0.1` **uniquement**, jamais `0.0.0.0` (mono-utilisateur, pas d'auth)
- **Seed historique** : `data/seed_monthly_closes.csv` (Coin Metrics Community Data,
  CC license, 191 mois 2010-07→2026-05). Chargé au démarrage par
  `storage.db.seed_from_csv()` (INSERT OR IGNORE — real figé). Régénérable :
  `python scripts/generate_seed.py`. Attribution requise (déjà dans README).

## Architecture — couches et dépendances autorisées
- `domain/` — **métier pur, aucune I/O ni état** : `aggregation` → `price_engine` → `flow_engine` → `pipeline` → `assemble_dto`. Testable par **composition** (moteur sur REF, flux sur Subsidy). Tous les sous-modules sont des **packages** (`__init__.py`) : `price_engine/`, `aggregation/`, `flow_engine/`, `pipeline/`.
- `domain/aggregation/` est un **package** (comme `price_engine/`), pas un module fichier-plat.
- `domain/errors.py` : DomainError (base) + InsufficientHistoryError (code=INSUFFICIENT_HISTORY).
- `sync/errors.py` : SyncError, SyncApiError, SyncStructError, SyncGranularityError.
- `sync/` — client CoinGecko keyless, dérivation des clôtures, réconciliation + interpolation, états `DEGRADED_*`.
- Couche HTTP (Flask) — `GET`/`POST /api/params`, `GET /api/forecast` (sérialise `ForecastExportDTO`).
- Couche données — SQLite (lecture/écriture clôtures mensuelles).
- **Règle de dépendance :** `domain/` ne dépend de **rien** (ni Flask, ni SQLite, ni requests). Les couches externes dépendent de `domain/`, jamais l'inverse.
  **Exception documentée (ST8 §3.4) :** `domain/flow_engine/__init__.py` importe `FlowParams` depuis `config/params.py` — `FlowEngineInput` est défini dans ce package (≠ `domain/models.py`) pour éviter la circularité `domain → config`. Seul point de contact `domain → config` autorisé.
- **Langue :** code / champs / routes / logs / libellés UI en **anglais** ; prose des specs et échanges en **français**.
- **Sens des dépendances** : `domain/` est pur (aucun import de `storage/`, `sync/`, `web/`,
  `requests`, `flask`, `sqlite3`). `storage/` PEUT importer `domain.models` (types de frontière
  uniquement). `sync/` importe `storage/` et `domain.models`. Jamais l'inverse.
  (Formulation incorrecte à éviter dans les briefs : « storage/ n'importe pas domain/ » —
  la contrainte est dans l'autre sens.)

## Invariants critiques — NE JAMAIS CASSER
- **Non-régression moteur (gate de tout merge touchant `price_engine`)** : `anchor_year=2025, anchor_price=101700, mm_anchor=0.361334851227728` → `nominal_price(2026..2072)` = `L37..L83` du pilote **au cent** (garde relative `1e-9`). ⚠️ `mm_anchor` DOIT être la valeur pleine précision du pilote (`Forecast Bear!C12`) ; `0.3613` est un arrondi d'affichage 4 décimales (écart ~3,5e-5 ≫ 1e-9) qui fait échouer les 5 années de blend. Contrôles : `arr_theo(2026)=0.210231258`, `nominal(2026)=123080.52`, `nominal(2072)≈2373743`.
- **Prix et taux en `float` (double IEEE-754).**
- **Jointure UNIQUE inter-référentiels** : `nominal_price` (moteur → flux). Rien d'autre ne traverse.
- **Compteur `C = année − anchor_year`** : `C=0` à l'ancre, `C=1` à la 1ʳᵉ projection. **Côté flux uniquement** (anti-bug V4). Le moteur indexe par année calendaire absolue, jamais de compteur.
- **`anchor_price` (moyenne glissante, germe de capitalisation) ≠ `reference_price` (KPI `current_portfolio`)** — ne jamais fusionner.
- **Constantes d'intégrité Bear** (jamais réglage utilisateur ; ajustables par release) : `POWER_LAW_EXPONENT=5.7675`, `POWER_LAW_TIME_ORIGIN=2008`, `BEAR_DISCOUNT=0.60`, `BLEND_WINDOW_YEARS=6`, `PLATEAU_ARR=0.03`, `PLATEAU_YEAR=2055`, `SIGMOID_CALENDAR_ORIGIN=2026` (fixe), `HORIZON=2072`. **`MM_WINDOW_YEARS=6` centralisé `Aggregator`** (≠ `BLEND_WINDOW_YEARS`, deux constantes distinctes).
- **`SIGMOID_CALENDAR_ORIGIN=2026` est un rail calendaire de _convergence_, PAS l'origine de la projection.** L'origine de la projection est l'**ancre** (`anchor_year`/`anchor_price`), elle déjà dynamique (dernier point réel observé ; projection à `anchor_year + 1`). Cette constante ne sert qu'à caler le **calendrier de maturation** de l'ARR vers le plateau. Elle reste **fixe par conception** (DEC-MOTEUR-01) : un lancement tardif doit produire un ARR de départ _plus bas_ (le BTC a mûri sur le calendrier réel), et non réinitialiser sa maturité. La rendre dynamique (`= anchor_year`) comprimerait la sigmoïde (effet « falaise » sur lancement tardif) et provoquerait une **division par zéro post-2054**. Le **midpoint `= (SIGMOID_CALENDAR_ORIGIN + PLATEAU_YEAR)/2 = 2040,5` est TOUJOURS dérivé, jamais codé en dur** (cf. Moteur de prix v1.0 §4.5).
- **`cdv_train` compose inflation ET train de vie** (DEC-DCA-03) : `cdv_train = cdv_inflation × (1+spending_growth)^C`.
- **`mm_anchor`** : MM6 en production ; MM4 (`0.361334851227728`, pleine précision pilote — pas l'arrondi `0.3613`) **uniquement** dans le vecteur de non-régression.
- **`keyless` = mode standard nominal ≠ états `DEGRADED_*`** (échec de synchro). Ne pas câbler keyless → DEGRADED.
- **Sérialisation `runway = ∞` → `"Infinity"`** (string JSON portable).
- **Pydantic ValidationError → JSON 422** : toujours `exc.errors(include_context=False)`
  — `include_context=True` (défaut) expose des `ValueError` Python non JSON-sérialisables.
- **Champs % dans FlowParams** (`inflation_rate`, `spending_growth_rate`, `dca_growth_rate`) :
  stockés en décimal (0.06 = 6%), convertis ×100 à l'affichage UI et ÷100 à la saisie.
  Ne jamais stocker ni envoyer en pourcentage entier.
- **Frontière `config/` vs `domain/` :** les **constantes d'intégrité Bear** vivent dans `domain/constants.py` (métier, module pur). `config/` porte la **config applicative** (host loopback, port, chemin db) et la **validation Pydantic des paramètres UTILISATEUR de flux** uniquement. Ne JAMAIS placer les constantes d'intégrité dans `config/` (préserve la pureté de `domain/` et l'isolation du test de non-régression). Port waitress **figé à 8000** (fallback bind incrémental conservé).

## Spécifications — source de vérité (lire à la demande dans `docs/specs/`)
Cadrage v2.1 · Synchronisation v1.3 · Agrégation **v1.3** · Flux v1.1 · Moteur de prix v1.0 · Plan de tests v1.0 · Spec technique 7 (Infra) v1.1 · Spec technique 8 (Moteur de calcul) v1.0.
> En cas de doute sur une formule ou une règle : **la spec fait foi, pas la mémoire**. La Spec technique 8 porte le pipeline `domain/` et le schéma du DTO ; la Spec technique 7 porte l'infra, le transport HTTP et la synchro.

## Glossaire
- **ancre / anchor** : dernier point réel d'où démarre la projection (`anchor_year`, `anchor_price`).
- **mm_anchor** : moyenne des `MM_WINDOW_YEARS` derniers ARR annuels (MM6 en prod) ; ancrage du blend.
- **runway** : nombre d'années avant épuisement du stack (`∞` si jamais épuisé).
- **DTO** : `ForecastExportDTO`, miroir JSON sémantique de la feuille `_Export` du pilote.

## Conventions de commit (MODE_GIT)
`feat:` · `fix:` · `refactor:` · `test:` · `docs:` · `chore:`
