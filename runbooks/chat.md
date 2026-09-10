# Chat M7

Lancer `make serve` avec les variables Scaleway/SerpApi injectées (`.env` facultatif).
Python : requirements-dev.txt ; Docker Linux. Aucun identifiant cloud transmis à l'UI.
Depuis votre poste : `ssh -L 3000:127.0.0.1:3000 -L 8020:127.0.0.1:8020 utilisateur@vm`,
puis http://localhost:3000 ; choisir atlas. Le tunnel 8020 sert les citations.
Ctrl-C arrête les services ; volumes atlas-chat-ui/index conservés. Journaux privés :
BRAIN/interactions/YYYY-MM-DD.jsonl. Budget/arrêt : 120 s et 0,05 EUR par requête.
UI single-user locale ; ni HTTPS ni exposition publique. Aucun GPU créé par serve.
Open WebUI v0.11.3, digest épinglé, image ~7,14 Go ; interface/marque conservées.
Dépendance imposée par MISSION ; alternative LibreChat écartée pour une seule intégration.
Source configuration/licence : https://docs.openwebui.com/reference/env-configuration/
et https://github.com/open-webui/open-webui/blob/v0.11.3/LICENSE .

Arrêter serve avant `make verify-m7` : les tests utilisent les mêmes ports locaux.
Pour le lancement en arrière-plan de l'agent, le PID de groupe est dans BRAIN/m7-serve.pid.
Le champ execution distingue live, record (appel réel de test) et replay (sans dépense).
Les anciennes lignes sans ce champ ont une provenance indéterminée : ne pas sommer leurs coûts.
