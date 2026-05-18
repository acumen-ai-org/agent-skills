# Reading the attack-surface fragment

This part answers one question: what is the attack surface — taint, network
egress/ingress, and committed secrets? The network inventory, Semgrep taint
paths, and secret findings fold into one fragment.

## Network

The network cards count outbound calls and inbound listeners; the two tables
list every egress and ingress site by signature, file, line, and call/bind
site.

What to look for: egress is a capability, not a defect — a documented outbound
call is inventory, not a vulnerability. It only becomes risk when a secret or
a taint path meets it. Any egress or ingress sets `status: warn` (track,
non-blocking) on its own.

## Secrets

The secrets card counts verified secrets; the table lists each by rule, file,
line, and scanner (gitleaks / trufflehog). The secret value is never shown.

What to look for: any row. A verified secret is the highest-exposure fact —
the fragment goes `status: error` and ships are blocked until the credential
is rotated and removed. `secrets` above zero is ship-blocking.

## Taint — Semgrep

The Semgrep cards count taint/security findings by severity; the table lists
each check, file, line, severity, and message.

What to look for: `Error`-severity findings that connect an untrusted source
to a dangerous sink. With no secrets present, these are the "address before
release" items; `semgrep_error` is the count to watch.

## Assessment (role-written)

The `threat-synthesis` role adds three narrative sections — attack surface,
secrets, data-flow & taint — tying entry points, exit points, and the single
highest-risk path together. A secret, when present, always leads the verdict.
