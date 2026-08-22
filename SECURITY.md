# Security Policy

## Supported versions

Only the latest tagged release (`latest` / most recent `vX.Y.Z` image on
Docker Hub) receives security fixes. There is no long-term support branch
for older versions — please stay on `latest` or a recent tag where possible.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, use GitHub's private vulnerability reporting:
**Security tab → "Report a vulnerability"** on this repository. If that's
unavailable, email the maintainer listed on the GitHub profile with a
description of the issue, reproduction steps, and impact.

Please include:

- The image tag/version affected
- Whether the issue is in this worker's own code, or in an upstream
  dependency (PaddleOCR, PyMuPDF, the base image, etc.)
- Any relevant logs (with `PAPERLESS_API_TOKEN` and other secrets redacted)

## Scope notes

- This project talks to your paperless-ngx instance over HTTP(S) using the
  token you provide. It never sends data anywhere else.
- `PAPERLESS_API_TOKEN` should be treated as a secret — pass it via
  `.env`/Docker secrets, not committed into `docker-compose.yml` or version
  control.
- The container runs as a non-root user (`appuser`, uid 1000) by design;
  please report any behavior that requires or silently falls back to root.
- Base image and dependency vulnerabilities are tracked via Dependabot, the
  CI's `pip-audit` step (`.github/workflows/ci.yml`), and a Trivy image
  scan on release (`.github/workflows/docker-publish.yml`) — if you spot a
  CVE that isn't yet flagged, a report is still welcome.
