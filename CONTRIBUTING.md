# Contributing

Thanks for considering a contribution! This is a small project, so the
process is intentionally lightweight.

## Getting set up

```bash
git clone https://github.com/silentprior/paperless-paddle-ocr.git
cd paperless-paddle-ocr
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Before opening a PR

```bash
ruff check .          # lint
ruff format --check . # formatting
mypy ocr_worker.py    # type check
pytest                # unit tests
```

All four run in CI on every pull request; please make sure they pass
locally first.

## Making changes

- Keep `ocr_worker.py` a single, readable file unless there's a strong
  reason to split it up — this project favors "read the whole worker in
  five minutes" over premature modularization.
- New behavior controlled by an environment variable should be documented
  in three places: the `Config` class docstring in `ocr_worker.py`,
  `docs/CONFIGURATION.md`, and the table in `README.md` if it's a
  commonly-used option.
- Add or update unit tests for any new logic in `tests/`. Heavy OCR/PDF
  dependencies are stubbed (see `tests/conftest.py`) — you shouldn't need
  to install `paddlepaddle` to run the test suite.
- If you're changing Docker build behavior, verify `docker build .` and
  `docker compose up` still work end-to-end.

## Commit messages / PRs

- Keep PRs focused — one logical change per PR is easier to review and
  revert if needed.
- Reference the issue you're fixing, if any (`Fixes #123`).
- Update `CHANGELOG.md` under an `## [Unreleased]` heading for anything
  user-facing (new env var, behavior change, bug fix).

## Releasing (maintainers)

Releases are tag-driven. Pushing a `vX.Y.Z` tag triggers
`.github/workflows/docker-publish.yml`, which builds and pushes a
multi-arch image to Docker Hub tagged `latest`, `X.Y.Z`, `X.Y`, and `X`,
and syncs `DOCKERHUB.md` to the Docker Hub repository description.

```bash
# after merging to main and updating CHANGELOG.md
git tag v1.1.0
git push origin v1.1.0
```

## Reporting bugs / requesting features

Please use the GitHub issue templates — they ask for the environment
variables you're using (redact your token!) and paperless-ngx version,
which is almost always needed to diagnose OCR worker issues.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Be
kind.
