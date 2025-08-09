# Fakturenn

Suite d'outils/scripts pour automatiser la facturation de la micro‑crèche Youn Ha Solena, récupérer des pièces (factures), interagir avec Gmail, et préparer l’export comptable (Paheko).

### Installation rapide
- Pré-requis: Python et Poetry installés
- Installer les dépendances:
```bash
poetry install
```

### Scripts disponibles
- **Télécharger les factures Free (FAI)**: enregistre les factures dans `factures_free/`
```bash
poetry run python scripts/download_free_invoices.py --help
poetry run python scripts/download_free_invoices.py
```
- **Initialiser l’auth Free Mobile**: assiste la configuration de l’authentification Free Mobile
```bash
poetry run python scripts/setup_free_mobile_auth.py --help
poetry run python scripts/setup_free_mobile_auth.py
```
- **Lister/traiter les mails Gmail non lus**: nécessite des identifiants OAuth Google valides
```bash
poetry run python scripts/gmail_unread.py --help
poetry run python scripts/gmail_unread.py
```
Astuce: commencer par `--help` pour voir les options et variables d’environnement attendues.

### Intégrations principales
- **Paheko (compta)**: client API dans `app/export/paheko.py` (création d’écritures: dépenses, recettes, virements, écritures avancées). Documentation Paheko: `https://paheko.cloud/api`.
- **Free / Free Mobile**: sources dans `app/sources/free.py`, `app/sources/free_mobile.py`, `app/sources/free_mobile_auth.py`.
- **Gmail**: gestion via `app/sources/gmail_manager.py`.

### Exécution
- Exécuter tous les scripts via Poetry: `poetry run python <script>`
- Pour la configuration (identifiants Free/Google/etc.), se référer aux messages interactifs des scripts et/ou à `--help`.


