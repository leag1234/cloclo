# MISSION — ATLAS-0

Build docs/13-poc-spec.md; first read AGENTS.md, docs/11 and docs/14.
M0–M23 delivered; M24 current and last. History: docs/decisions-log.md.

Done = make verify-mN + green GitHub ci. Protect workflows/CODEOWNERS/verify-*;
never weaken assertions. Branch/PR only, no main push. Current human mandate
controls merge and subsequent milestones.

## Permanent constraints

Contracts precede code; prove useful answers through public HTTP. No secrets in
repo/logs/prompts; dedicated project only. GPU2 EUR/h,30 EUR/milestone; owner accepts
bounded risk with alerts. Record costs before provisioning; destroy experiments
and run infra/gpu-down.sh at session end.

Requests: <=10 tools; authorized profile budgets/deadlines below.
Image model loading is measured separately under contracts/m13 and M20's bounded
startup wait. Declare live/replay honestly; replay uses real recordings. Do not re-verify completed milestones without explicit request or visible regression;
use BRAIN outcomes and report skips. CI regression gates remain mandatory.

Update BRAIN STATUS/TASK/JOURNAL before risk and session end, BLOCKERS when blocked.
MISSION <=8000 bytes; archive settled history unchanged in decisions-log.

### Journey rules (permanent)

R1: Before implementation, write user intent and six natural phrasings, independent
of regexes/templates.

R2: For each capability include six phrasings, three without the obvious keyword,
a message of at most four words, unaccented and uppercase input, English and another
language, and a negative case. For attachments include at least two in one request.

R3: Assert useful user content, never just internal calls/routing. No useful answer
means failure.

R4: Preserve every owner-reported defect as a permanent, verbatim, dated journey;
never rephrase it to make it easier.

R5: A service module called only from tests is not delivered. Unreachable modules
must fail the gate, not merely produce a warning.

R6: Every rejection identifies measured values and thresholds, in plain user-facing
language and the server journal. Never conflate image byte limits with model token
limits. Preserve the user's question when it can be safely parsed.

## Standing facts — never archive

- Token incidents2026-09-13/15 are CLOSED. Owner replaced and reinjected credentials,
  verified API write/delete and push. Never stop or reconfirm for pre-17th incidents.
- Owner attests GPU2 EUR/h,30 EUR/milestone,800 EUR monthly, alerts active.
  Hypothetical shutdown defects are notes, not blockers.
- External failure counters reset each session; historical errors do not block a
  first attempt. Preserve permanent rules; archive only history.

## Permanent credential ruling — owner, 2026-09-18

The06:30 remote-URL incident is a CLOSED FALSE POSITIVE; no revocation is required.
Reading/sourcing secrets locally, embedded origin authentication, credential environment
variables and masked values are normal. Never re-raise this incident. Exposure requires
a secret leaving its intended location (committed/shared artefact or transmission to
a third party). Report what left, where and when for a genuine incident. Full ruling
is preserved in docs/decisions-log.md. Do not print secrets into shared tool output.

## M24 — Documents and files: read, produce, transform

Binding requirements/J42–J49: contracts/m24-owner.md and contracts/m24.md.
No criteria relaxed. REQ-ENG-004/005/009/011, REQ-FIN-002, POC-F1/F3/F5.

D1–D2: make serve starts authenticated Open Terminal, loopback port8000, dedicated
user-files volume, shared Docker network URL in TERMINAL_SERVER_CONNECTIONS and
filesystem uploads. No repository/host mounts, platform credentials or route to
host/internal services8010/8020/8030. runbooks/files.md describes containment,
shutdown and the new model-shell exposure surface.

D3–D5: read complete PDF/DOCX/XLSX/PPTX/ODT/ODS/ODP/CSV/TXT/MD/images; preserve
spreadsheet structure. Explicit scanned/password/extraction failures. Produce
actually downloadable DOCX/XLSX/PPTX/PDF/CSV/MD/PNG; soffice renders PDF. State
regeneration versus editing in place; preserve unrequested formatting.

D6–D7: inspect a rendered real answer's DOM, repair CSS with stable selectors
including copy-code-button/nb-code classes, never generated Svelte suffixes.
Browser before/after screenshots in reports/M24.md must prove serif body and
code without line numbers/default toolbar. Diagnose activity emission, transport
and rendering; capture named elapsed activity during no-tool generation.

D8: attachments allow0.30 EUR/request; other requests retain0.10 EUR. Above the
attachment ceiling apply M10 hierarchy; retain measured-value rejection messages.
Use Tavily search with TAVILY_API_KEY from secrets.env and page content directly;
no separate fetch for these results. Keep explicit SerpApi fallback selection.
Disclose quota/provider failures to the user, never silently use model memory.

J42–J49 test downloadable slides+PDF without corpus, corrected DOCX with strategy,
correct spreadsheet comparison/new sheet/chart, complete long-PDF synthesis,
explicit extraction failure, large attachments, CPC-specific searched citations,
and real rendering. Compare three configured models on J42–J44, recording model,
commands, failed commands and seconds. Preserve original wording in journeys.

Done: make verify-m24 locally, m24 branch/PR, exact-head green GitHub ci; current
owner mandate authorizes API squash only then. Poll up to180 times at15 seconds.
Update BRAIN and write the completion marker after confirmed merge. Continue only
if another milestone is listed. Protected files remain untouched.

### M24 supersedes the read-only tool restriction (owner ruling, 2026-09-18)
`docs/13` POC-W3 restricted model tools to read-only. M24 requires a shell with write
access, so the two conflict. AUTHORIZED: for the Open Terminal path only, the read-only
restriction is SUPERSEDED by the containment described in M24/D2.

What is granted: executing Python and shell commands inside the Open Terminal Docker
container, and creating or modifying files in its dedicated volume.
What still holds, and is the condition of this authorisation:
- the container has no route to the VM's internal services (8010/8020/8030), no Scaleway
  credentials, and no mount of the ATLAS repository;
- its volume carries user files only, nothing of the platform;
- the port is bound to 127.0.0.1;
- `runbooks/files.md` states plainly what the terminal can and cannot reach, and how to
  stop it.
Read-only remains the rule for every OTHER tool path (web fetch, retrieval, MCP).
This is an explicit owner exception: apply it, do not stop on it again.

### M24 — Open Terminal path traversal: accepted risk, documented (owner ruling, 2026-09-18)
The agent proved that the pinned Open Terminal file API reads outside its user directory:
`GET /files/read?path=/home/user/../../etc/hostname` succeeds, and so does following a
symlink created inside the container. This is a genuine defect of the product and the
containment promised in M24/D2 cannot rely on the application.

Measured scope on the running container: one mount only (`/home/user`), no ATLAS
repository, no `secrets.env`, no Scaleway or Tavily credentials; the only key in its
environment is its own API key. An authenticated caller can therefore read the system
files of a disposable container and nothing else.

ACCEPTED for the PoC, under these conditions, which are the containment:
- containment is provided by Docker alone, never by the terminal's own path checks;
- nothing but user files is ever mounted into that container — no repository, no secrets,
  no host path;
- the port stays bound to 127.0.0.1 and the container is never publicly exposed;
- `runbooks/files.md` states the traversal explicitly, so nobody later mounts something
  sensitive believing the API confines reads.
Do not stop on this again. Report the defect upstream to Open WebUI with the two probes.
