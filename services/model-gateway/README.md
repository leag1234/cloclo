# model-gateway

M1 : configuration de routage local + fallback (POC-A3, REQ-INF-012/013).
Le modèle local est exposé sous l'alias `local`. Après `infra/gpu-up.sh`, charger
`BRAIN/gateway.env` pour obtenir `LOCAL_API_BASE`. Les identifiants du fallback
et sa clé restent injectés via l'environnement ; son activation relève de M4.

Le modèle FP8 et sa révision sont chargés depuis `local.env` dans ce service ;
un éventuel `.env` racine peut les remplacer. `GPU_SSH_PUBLIC_KEY` permet
d'autoriser une clé publique dédiée pour les diagnostics sans installation SSH.
Le provisionnement nécessite Scaleway CLI 2.62, Python 3 et les variables
`SCW_DEFAULT_PROJECT_ID`, `SCW_DEFAULT_ZONE` (fr-par-2), `LOCAL_MODEL`,
`GPU_CLIENT_IP` (IPv4 de la VM app), `GPU_MAX_EUR_H` (plafond GPU hors stockage/IP).
Le groupe réseau restreint SSH et l'inférence à cette IPv4. Aucun secret n'est
transmis dans cloud-init. L'installation est entièrement déclarée par script.

Runbook : `make verify-m1` effectue un cycle réel avec credentials ; sans credentials,
le script protégé ne fait qu'un contrôle statique. En cas d'échec, `infra/gpu-down.sh`
réconcilie les ressources taguées atlas-m1 du projet/zone, conserve les poids,
supprime GPU, IP et disque système. Une erreur fournisseur reste une erreur.
Ne pas lancer de cycles concurrents ; verrou local, une seule VM de contrôle.
`infra/inventory.sh` permet de contrôler les serveurs/IP du projet après nettoyage.
Les mesures minimales sont archivées dans `BRAIN/bench/`, sans promesse TTFT/SLO.

Coût estimé L40S : 1,511316 EUR/h HT avec stockage 280 Go et IPv4 ;
poids persistants 200 Go : 0,026 EUR/h. Revoir au checkpoint humain après M1.
Source: https://www.scaleway.com/en/blog/a-transparent-update-on-scaleway-pricing/
Source: https://www.scaleway.com/en/docs/instances/reference-content/identify-devices/
Source: https://docs.vllm.ai/en/v0.10.2/getting_started/installation/gpu.html
