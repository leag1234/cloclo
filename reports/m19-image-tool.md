# M19 image-tool implementation status

M19 D1/D3, REQ-ENG-004/009 and REQ-FIN-002. Chat and scoped project conversations
expose `generate_image(prompt)`; regex matching no longer gates generation.
The selected tool ends the model loop and generation receives only the remaining
request budget/deadline. Rewrite carries source and output language explicitly.

The public API regression failed before implementation (504 for a model-selected
natural drawing request). Unit tests now cover image delivery, invalid/disabled
arguments, combined decision/image cost, exhausted budgets and rewrite reservation.
M7 was recorded against the real provider (EUR 0.0127899). Real GPU journey
recordings remain blocked: the affordable GPU was created but poweron returned
`resource out of stock`; cleanup removed it. No completion is claimed.
