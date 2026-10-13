# Daily live acceptance probe (M26)

Run `scripts/daily-probe.sh` with the local stack available on ports 8020 and
8000. It loads the same external credentials as `make serve`. Each request uses
the first public profile, the ordinary or attachment budget, and real providers.
The six cases check downloaded presentation, corrected document and spreadsheet
content, the owner's structured PDF summary, a changing web fact and plain text.
The owner fixture is read only from `/opt/atlas-src/private/fixtures/owner-174p.pdf`.
It and all captures remain outside tracked files. No private evaluation is read.

Install on this host with a weekday morning cron entry (UTC):

```cron
0 7 * * 1-5 cd /opt/atlas-src/repo && scripts/daily-probe.sh >> BRAIN/daily-probe.log 2>&1
```

`BRAIN/probe/YYYY-MM-DD.json` records status, elapsed seconds, cost, HTTP status
and error code/message for each case. A provider quota refusal records
`quota_exceeded` and its provider HTTP status (for example432) in the message. Any failure writes `BRAIN/PROBE_FAILED.txt` with
the failed case and measured values; a fully successful run removes that marker.
An unavailable stack is a failed probe, never a passing replay. The lock prevents
overlapping scheduled executions. Local milestone acceptance uses `make verify-m26`;
CI regression replays never certify live acceptance.

Current owner ruling (2026-09-23): J59 and the web probe are NOT RUN until the
owner restores search credits. Do not schedule or launch the full probe while
that suspension applies; NOT RUN never counts as successful acceptance.
