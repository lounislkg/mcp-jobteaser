# mcp-jobteaser

Serveur MCP qui recherche des offres publiées sur [JobTeaser](https://www.jobteaser.com) et les
retourne en JSON (titre, entreprise, lieu, contrat, url...), sans le détail complet de chaque offre.
Un second outil récupère ce détail (description complète, profil recherché...) pour les offres
choisies par l'agent, à partir de leur `id`.

## Comment ça marche

JobTeaser bloque les requêtes HTTP classiques (challenge anti-bot "Security checkup"). Le serveur
pilote donc un vrai navigateur Chromium headless via [Playwright](https://playwright.dev/python/)
pour charger les pages de résultats, page par page, jusqu'à atteindre `max_offers` ou tomber sur une
page de résultats vide.

**Point important** : chaque page de résultats est chargée dans un **contexte de navigateur neuf**
(cookies non partagés entre les requêtes). Réutiliser un même contexte pour plusieurs navigations
successives déclenche de façon quasi systématique le challenge JS de JobTeaser ("Un instant…"), qui
ne se résout jamais tout seul. Ne pas "optimiser" ça en réutilisant une page/context pour plusieurs
pages sans retester — voir `src/mcp_jobteaser/search_service.py`.

```
src/mcp_jobteaser/
├── server.py                        # serveur MCP (streamable-http) + outils exposés
├── search_service.py                # boucle de pagination de la recherche
├── details_service.py               # récupération du détail d'une liste d'offres par id
├── browser.py                       # lancement de Chromium + contexte neuf (partagé)
├── pages/job_offers_search_page.py  # Page Object : sélecteurs + parsing d'une page de résultats
├── pages/job_offer_page.py          # Page Object : sélecteurs + parsing d'une page d'offre
├── models.py                        # JobOffer / SearchResult / JobOfferDetails... (pydantic)
└── config.py                        # constantes / variables d'environnement
```

## Prérequis

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker (pour le déploiement)

## Développement local

```bash
uv sync
uv run playwright install chromium
```

Lancer les tests (parsing testé hors-ligne contre des fixtures HTML dans `tests/fixtures/`, pas
besoin de réseau) :

```bash
uv run pytest
```

Tester une recherche en réel, sans passer par le serveur MCP :

```bash
uv run python -c "
from mcp_jobteaser.search_service import search_job_offers
result = search_job_offers('stage DevOps', max_offers=10)
print(result.model_dump_json(indent=2))
"
```

Lancer le serveur MCP en local :

```bash
MCP_AUTH_TOKEN=dev-token uv run python -m mcp_jobteaser.server
```

Le serveur écoute par défaut sur `http://0.0.0.0:8000/mcp`.

## Variables d'environnement

| Variable | Défaut | Description |
|---|---|---|
| `MCP_AUTH_TOKEN` | *(vide)* | Token requis en `Authorization: Bearer <token>` sur chaque requête. **À définir en prod** : sans lui, le serveur log un warning et accepte les requêtes non authentifiées. |
| `MCP_HTTP_HOST` | `0.0.0.0` | Adresse d'écoute du serveur HTTP. |
| `MCP_HTTP_PORT` | `8000` | Port d'écoute. |
| `CHROMIUM_EXECUTABLE_PATH` | *(bundled Playwright)* | Chemin d'un binaire Chromium système à utiliser à la place de celui de Playwright (utile sur ARM, voir Docker). |
| `CHROMIUM_EXTRA_ARGS` | *(vide)* | Flags Chromium supplémentaires, séparés par des virgules (ex: `--no-sandbox,--disable-dev-shm-usage`, nécessaire en conteneur). |
| `JOBTEASER_PAGE_DELAY_SECONDS` | `1.5` | Délai entre deux pages consécutives lors de la pagination. |
| `JOBTEASER_NAV_TIMEOUT_MS` | `30000` | Timeout de navigation Playwright. |
| `JOBTEASER_POST_LOAD_WAIT_MS` | `1500` | Attente supplémentaire après chargement, avant de lire le DOM (hydratation React). |

Voir aussi `.env.example`.

## Déploiement Docker (ex: Raspberry Pi)

Le `Dockerfile` installe Chromium via `apt` (plus fiable que le binaire téléchargé par Playwright sur
ARM) et configure les flags nécessaires pour tourner en conteneur (`--no-sandbox`).

```bash
docker build -t mcp-jobteaser .

docker run -d \
  --name mcp-jobteaser \
  --restart unless-stopped \
  -p 8000:8000 \
  -e MCP_AUTH_TOKEN="<un-token-long-et-aleatoire>" \
  mcp-jobteaser
```

Générer un token correct (exemple) :

```bash
openssl rand -hex 32
```

Le conteneur expose `/mcp` sur le port 8000. Comme tu gères déjà l'exposition réseau (tunnel /
reverse proxy vers l'extérieur), il suffit de pointer ça vers `http://<pi>:8000/mcp` en HTTPS côté
public — **le bearer token ne remplace pas le TLS**, assure-toi que le tunnel/reverse proxy termine
bien en HTTPS avant que la requête n'arrive en clair sur le Pi.

Vérifier que le conteneur tourne correctement :

```bash
docker logs -f mcp-jobteaser
```

### Tester le serveur déployé avec curl

```bash
# Doit renvoyer 401
curl -o /dev/null -s -w "%{http_code}\n" https://ton-domaine/mcp

# Doit renvoyer un handshake MCP (200)
curl -s -X POST https://ton-domaine/mcp \
  -H "Authorization: Bearer <ton-token>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}'
```

## Configurer Claude pour utiliser ce MCP

Le serveur utilise le transport **streamable-http**, avec authentification par bearer token. Il faut
donc que le client Claude envoie l'en-tête `Authorization: Bearer <token>` sur chaque requête.

### Claude Code (CLI)

```bash
claude mcp add --transport http jobteaser https://ton-domaine/mcp \
  --header "Authorization: Bearer <ton-token>"
```

(vérifie `claude mcp add --help` si la syntaxe a évolué depuis l'écriture de ce README).

### Claude Desktop

Dans la config MCP (`claude_desktop_config.json`), ajouter une entrée de type serveur distant :

```json
{
  "mcpServers": {
    "jobteaser": {
      "type": "http",
      "url": "https://ton-domaine/mcp",
      "headers": {
        "Authorization": "Bearer <ton-token>"
      }
    }
  }
}
```

### Claude.ai (web) — pour les tâches programmées dans le cloud

C'est le cas d'usage visé (tâches nocturnes qui tournent dans le cloud, PC perso éteint) :

1. **Réglages → Connecteurs → Ajouter un connecteur personnalisé**
2. URL : `https://ton-domaine/mcp`
3. Renseigner l'authentification par en-tête personnalisé : `Authorization: Bearer <ton-token>`

Une fois le connecteur ajouté, les outils `search_job_offers_tool` et `get_job_offers_details_tool`
sont disponibles dans les conversations et les tâches programmées qui l'activent.

## Outil exposé

`search_job_offers_tool(query: str, max_offers: int = 50)`

- `query` : termes de recherche, équivalent au champ de recherche JobTeaser (ex: `"stage DevOps"`).
- `max_offers` : nombre maximal d'offres à retourner (plafond dur à 100, voir
  `HARD_CAP_MAX_OFFERS` dans `config.py`).

Retourne un objet avec `query`, `total_offers_found`, `pages_scanned`, `reached_end_of_results`
(`true` si JobTeaser n'a plus d'offres correspondantes, `false` si on s'est arrêté à cause de
`max_offers`), et la liste `offers`.

`get_job_offers_details_tool(ids: list[str], max_chars: int = 6000)`

À appeler sur les offres jugées pertinentes après la recherche, pas sur toute la liste : chaque offre
coûte un chargement de page.

- `ids` : champs `id` des offres (UUID) tels que retournés par `search_job_offers_tool`. 10 maximum
  par appel (`MAX_IDS_PER_DETAILS_CALL` dans `config.py`) ; au-delà l'appel est refusé.
- `max_chars` : longueur maximale de la description par offre (plafond dur à 20000).

Le serveur reste sans état : l'agent renvoie les `id`, le serveur reconstruit l'URL. JobTeaser
redirige `/fr/job-offers/<id>` vers l'URL canonique (avec le « slug » décoratif), donc l'`id` seul
suffit.

Retourne `offers` (par offre : `id`, `url`, `title`, `company`, `location`, `contract_type`,
`start_date`, `salary`, `remote_policy`, `study_level`, `function`, `application_deadline`,
`posted_at`, `description`, `description_truncated`) et `errors`. Les champs que le recruteur n'a pas
renseignés valent `null`. Un échec sur un id n'empêche pas les autres d'être retournés ; chaque
entrée de `errors` porte un code :

| Code | Signification |
|---|---|
| `invalid_id` | l'id n'est pas un UUID |
| `not_found` | offre expirée ou supprimée (HTTP 404) |
| `blocked` | le challenge anti-bot de JobTeaser a intercepté la page (transitoire) |
| `timeout` | la page ne s'est pas chargée à temps (transitoire) |

Les deux outils pilotent un Chromium : un verrou (`_browser_lock` dans `server.py`) garantit qu'un seul
navigateur tourne à la fois, même si l'agent envoie plusieurs appels en parallèle.
