# ICS repair proxy

Petit proxy sans dépendance Python externe. À chaque requête, il récupère le
calendrier source, répare les retours à la ligne et échappements `TEXT`, replie
les lignes à 75 octets, préfixe les `SUMMARY`, puis renvoie un ICS UTF-8/CRLF.

## Démarrage

```sh
cp .env.example .env
# Modifier .env, notamment ICS_INPUT_URL et SERVER_PATH
docker compose up -d --build
```

Le calendrier est ensuite disponible à l'adresse :

```text
http://votre-hôte:8080/<votre-chemin>
```

Toutes les autres routes répondent `404`. Le chemin secret et l'URL source ne
sont pas écrits dans les logs. `GET` et `HEAD` sont acceptés.

## Variables

| Variable | Défaut | Description |
|---|---|---|
| `ICS_INPUT_URL` | obligatoire | URL HTTP(S) du calendrier source |
| `SERVER_PATH` | `/calendar.ics` | Route exacte exposée, avec ou sans `/` initial |
| `SERVER_HOST` | `0.0.0.0` | Interface d'écoute dans le conteneur |
| `SERVER_PORT` | `8080` | Port d'écoute dans le conteneur |
| `EVENT_PREFIX` | `` | Préfixe ajouté à chaque `SUMMARY` de `VEVENT` |
| `FETCH_TIMEOUT` | `15` | Timeout amont en secondes |
| `PUBLIC_PORT` | `8080` | Port publié par Docker Compose |

Choisissez un `SERVER_PATH` long et aléatoire. Ce chemin agit comme un secret
non devinable, mais ne remplace pas HTTPS : placez le service derrière votre
reverse proxy TLS si le calendrier transite sur Internet.

## Tests

```sh
python -m unittest -v
```
