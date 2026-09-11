# ADR-0001 — Frontière de l'API développeurs M15

Statut : proposé ; adoption par merge du contrat sous CI verte, selon le mandat
humain d'autonomie et de squash conditionnel. Exigences REQ-DEV-001 à005.

Contexte : le chat M7 utilise un historique/RAG/MCP privé partagé, tandis que M15
introduit des clés et quotas individuels et des outils exécutés dans les clients.
Codex courant utilise Responses ; Claude Code utilise Messages. Les deux doivent
atteindre le même gateway code sans accéder aux données privées du chat.

Options : ajouter des identités au pipeline de chat complet ; publier directement
le fournisseur ; créer une entrée développeur isolée partageant le gateway.
La première impose une migration multi-utilisateur de l'UI hors périmètre ; la
seconde expose les credentials/coûts et ne fournit pas le protocole Messages.

Décision : entrée locale8030 sans état conversationnel, clés/quotas SQLite locaux,
et traduction des trois formats vers le gateway. Les outils restent côté client.
Le chat8020 conserve son périmètre privé. Aucun credential cloud dans les clients.
Une seule tentative fournisseur code sous0,05EUR pour préserver le budget du grand
contexte ; le fallback M8 du chat reste inchangé. Les refus de budget sont visibles.

Conséquences : deux points d'entrée locaux documentés ; aucun hébergement public
ni promesse de durcissement production. Traduction Messages expérimentale pour un
modèle non-Claude, sans support fournisseur Anthropic. Les limites protocolaires
sont explicites et testées ; les formats inconnus sont refusés. SQLite conserve
les réservations inconnues après crash, au prix d'un débit conservateur. Les
évolutions de cette décision nécessitent un nouvel ADR, pas l'édition de celui-ci.
