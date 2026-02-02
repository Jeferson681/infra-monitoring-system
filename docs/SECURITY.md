
# Security

If you find a vulnerability or a possible credential leak in this repository, follow the guidelines below:

1. Do not disclose details publicly.
2. Open a private report (if available) or email jefersonoliveiradesousa681@gmail.com with as much detail as possible (repro steps, impact, suggested fixes).

Important notes:

- Never commit/version secrets (tokens, private keys, passwords). If you find a secret, remove it from history and rotate credentials immediately.
- Before pushing, run TruffleHog locally to detect secrets:
  ```powershell
  docker run --rm -v ${PWD}:/repo -w /repo trufflesecurity/trufflehog:latest filesystem /repo
  ```

This policy covers the source code in this repository. For issues in third-party dependencies, use the official channels of the affected projects.
