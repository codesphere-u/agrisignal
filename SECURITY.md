# Security Policy

## Supported Versions

| Version | Supported |
| :--- | :--- |
| `1.0.x` | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security issue in AgriSignal (such as payload hash collision bypasses in the offline sync engine or injection vectors in the web workbench), please report it privately to `codesphereinnovationz@gmail.com` with the subject `[SECURITY] AgriSignal`.

We acknowledge reports within 48 hours and aim to release verified patches within 7 days.

## Field Data Integrity Principles

1. **Cryptographic Payload Verification**: Every `FieldObservationEnvelope` carries a canonical SHA-256 `content_hash`. Tampered or corrupted 2G/3G payloads are rejected prior to CRDT state mutation.
2. **Idempotent Replay Safety**: Envelopes include deterministic `idempotency_key` identifiers so repeated retries over high-latency rural links cannot corrupt or duplicate state.
3. **Biosafety Guardrails**: Pest and disease early warnings strictly output cultural, mechanical, and biological IPM recommendations and require certified extension-officer escalation before any chemical intervention.
