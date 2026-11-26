# GitHub Actions workflows

This directory holds every workflow for the repository. There are no
subdirectories: GitHub only discovers workflows placed directly under
`workflows`, so reusable workflows live here too, alongside the
top-level ones that trigger on events.

## Naming convention

Every file is prefixed by what it does:

| Prefix      | Purpose                                                                                                                                                                               |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ci-`       | Quality/test checks, most of them reusable workflows called from `workflows/ci.yaml`.                                                                                                 |
| `lib-`      | Reusable workflows with no event trigger of their own; they only expose `workflow_call` outputs (e.g. reading the test matrix or `pyproject.toml`) and are `needs:`-ed by other jobs. |
| `bot-`      | Scheduled automation that pushes commits / opens PRs as the `ci-bot` GitHub App.                                                                                                      |
| `nightly-`  | Scheduled checks against the _published_ PyPI package (as opposed to `ci-*`, which checks the repo's source).                                                                         |
| `release-`  | Publishing: PyPI package, GitHub release assets, documentation.                                                                                                                       |
| `security-` | Supply-chain/security scanning (Scorecard, dependency review).                                                                                                                        |

`workflows/ci.yaml` is the entry point for pull requests/pushes to `main`; it fans out
to the `ci-*.yaml` reusable workflows so each check can also be run/dispatched
on its own. Its last job, `ci`, depends on all the others and fails unless each of them
succeeded. It is the one status check that the ruleset of `main` requires: add each new job of
`ci.yaml` to its `needs`, and do not rename it. The ruleset is a setting of the repository, which
a maintainer changes.

Three `ci-*` workflows are deliberately _not_ called from `ci.yaml`, each
standalone with its own trigger instead: `ci-benchmark.yaml` and
`ci-benchmark-import.yaml` run nightly on their own schedule rather than gating
every PR/push, since a benchmark regression isn't a merge blocker; `ci-verify-workflows.yaml` lints
`.github/workflows/*` itself and has its own trigger (every pull request and push to `main`, with no
path filter, so it can be a required check).

## Catalogue of the workflows

The trigger of a reusable workflow is `workflow_call`: it runs when another workflow calls it
(`ci.yaml` for the `ci-*` ones, `nightly-package.yaml` for `nightly-test-package.yaml`).

| Workflow                            | Trigger                                | Purpose                                                                                       |
| ----------------------------------- | -------------------------------------- | --------------------------------------------------------------------------------------------- |
| `ci.yaml`                           | pull request, push to `main`, nightly  | Entry point: calls the `ci-*` checks below. The job `ci` is the required check.               |
| `ci-benchmark-import.yaml`          | nightly, manual                        | Track the import time of the package (not a merge gate).                                      |
| `ci-build.yaml`                     | called by `ci.yaml`                    | Build the package and check that the built package installs.                                  |
| `ci-cyclic-imports.yaml`            | called by `ci.yaml`, manual            | Check that there is no circular import (`inv imports.check-cycles`).                          |
| `ci-doctest.yaml`                   | called by `ci.yaml`, manual            | Run the doctests (`inv test.doctest`) and check that the documentation builds.                |
| `ci-format.yaml`                    | called by `ci.yaml`, manual            | Check the formatting and the linting of the source, the Markdown, YAML, TOML and shell files. |
| `ci-pre-commit.yaml`                | called by `ci.yaml`, manual            | Run all the pre-commit hooks.                                                                 |
| `ci-test.yaml`                      | called by `ci.yaml`                    | Unit and integration tests on every Python version and OS.                                    |
| `ci-type-checking.yaml`             | called by `ci.yaml`, manual            | Type check the package with `ty`.                                                             |
| `ci-benchmark.yaml`                 | nightly, manual                        | Run the benchmarks (not a merge gate).                                                        |
| `ci-verify-workflows.yaml`          | pull request, push to `main`, manual   | Lint the files of `.github/workflows`.                                                        |
| `lib-get-test-matrix.yaml`          | called by other workflows, manual      | Load the Python versions and the operating systems to test.                                   |
| `lib-get-package-metadata.yaml`     | called by other workflows, manual      | Read the name and the version of the package from `pyproject.toml`.                           |
| `nightly-package.yaml`              | nightly (10:30 UTC), manual            | Test the package published on PyPI: calls `nightly-test-package.yaml`.                        |
| `nightly-test-package.yaml`         | called by `nightly-package.yaml`       | Run the tests against the installed PyPI package.                                             |
| `release-pypi.yaml`                 | version tag `v*.*.*`, manual           | Run `ci.yaml`, then build, sign, attest (SLSA, GitHub provenance) and publish to PyPI.        |
| `release-docs.yaml`                 | version tag `v*.*.*`, manual           | Deploy the documentation of the stable version (with `mike`).                                 |
| `release-docs-dev.yaml`             | push to `main`, manual                 | Deploy the documentation of the development version.                                          |
| `release-docs-publish.yaml`         | called by the two previous workflows   | Build and deploy the documentation (shared logic).                                            |
| `security-audit.yaml`               | scheduled, manual                      | Audit the dependencies for known vulnerabilities.                                             |
| `security-dependency-review.yaml`   | pull request                           | Review the dependencies added by the pull request.                                            |
| `security-scorecard.yaml`           | weekly, push, branch protection change | OSSF Scorecard supply-chain analysis.                                                         |
| `bot-cancel-stale-queued-runs.yaml` | hourly                                 | Cancel the runs that have been queued for too long.                                           |
| `bot-format-files.yaml`             | weekly (Friday)                        | Format the YAML, Makefile, shell and Markdown files and open a pull request.                  |
| `bot-pin-action.yaml`               | weekly (Wednesday)                     | Pin the actions to a commit SHA (`ratchet`) and open a pull request.                          |
| `bot-pre-commit-autoupdate.yaml`    | weekly (Tuesday)                       | Update the pre-commit hooks and open a pull request.                                          |
| `bot-sync-shared-makefile.yaml`     | weekly (Wednesday)                     | Sync the shared Makefile subtree and open a pull request.                                     |
| `bot-update-deps.yaml`              | weekly (Saturday)                      | Update the dependencies (`uv.lock`) and open a pull request.                                  |

All the workflows can also be triggered manually (`workflow_dispatch`), except the reusable ones
that need inputs and the pull request security review.

The two benchmark workflows compare the median of each benchmark with the one of the last run of
`main` that finished, successful or not, and fail if it is more than 50% slower. A regression
therefore fails one run: the next one compares with it.

`nightly-test-package.yaml` checks the published package with `tests/package_checks.py` of the tag
`v<installed version>`, not of `main`, so each version is checked with its own checks. A published
version without a tag fails the run.

`release-pypi.yaml` publishes with PyPI Trusted Publishing: it needs a GitHub environment named
`pypi`, configured as a trusted publisher with the workflow `release-pypi.yaml`. It refuses to
publish a version that is already on PyPI, a tag that does not match the version of
`pyproject.toml`, and a manual run of a version that is not a pre-release.

## Composite actions vs. reusable workflows

- **`.github/actions/*`** (composite actions): used when the shared unit is a
  handful of _steps_ inside a single job (e.g. checkout + `uv` setup,
  generating a bot token + checking out, or opening the resulting PR as
  ci-bot). Composite actions cannot produce a job-level output usable in a
  `strategy.matrix`.
- **`.github/workflows/lib-*.yaml`** (reusable workflows called with `uses:
./.github/workflows/lib-....yaml`): used when the output needs to feed a
  matrix, or when the shared logic is naturally a whole job (e.g. reading
  the supported Python versions and operating systems once and handing the JSON down to several
  jobs via `needs:`).

When adding new duplication, prefer extending an existing composite
action/reusable workflow over copy-pasting steps.

## Conventions applied to every workflow

- **Action pinning**: every third-party (and first-party `actions/*`) step is
  pinned to a full commit SHA with a trailing `# ratchet:owner/repo@vX.Y.Z`
  comment, added and refreshed automatically by
  [`ratchet`](https://github.com/sethvargo/ratchet) via `workflows/bot-pin-action.yaml`.
  Never hand-pin a SHA without that comment — the next `bot-pin-action` run
  would otherwise silently downgrade or drift it. Local composite actions
  (`uses: ./.github/actions/...`) are referenced by path, not pinned. The one
  exception is the SLSA generator of `release-pypi.yaml`: it verifies its own
  ref, so it is referenced by a tag, with a `# ratchet:exclude` comment. Any
  runtime tool invoked outside of a pinned action (e.g. `npx <pkg>`) should
  also pin an explicit version, so a bot-authored PR can't pick up an
  unreviewed upstream release.
- **Permissions**: top-level `permissions:` is always `{}` (it grants
  nothing), and each job declares the minimum permissions that it needs (e.g.
  `contents: read` to check out, `contents: write` to push, `id-token: write`
  for OIDC).
- **Timeouts**: every job sets `timeout-minutes`, sized to what the job
  actually does (2 for a config-read job, 5 for most checks, 10 or 15 for slower
  jobs like the tests, Scorecard or the benchmarks) so a hung step can't occupy a runner
  indefinitely.
- **Runners**: `ubuntu-slim` for lightweight jobs that only run a small
  action or a couple of shell commands (no Python/build tooling); otherwise
  `ubuntu-latest`, or the OS matrix under test for `workflows/ci-test.yaml` /
  `nightly-test-package.yaml`.
- **Windows**: the matrix of `ci-test.yaml` and `nightly-test-package.yaml` includes Windows,
  where the default shell is PowerShell. A `run` step of these workflows that uses shell syntax
  declares `shell: bash`. `ci-test.yaml` does not use `setup-venv-uv-action` or `invoke`, which do
  not support Windows.
- **`workflow_dispatch`**: added to every workflow (checks and automation
  alike) so it can be re-run manually without waiting for its normal trigger.

## Shared configuration

Values that would otherwise be duplicated across workflows are read once:

- The supported Python versions and the operating systems are in `../workflow-config.json`, read
  once per run by `lib-get-test-matrix.yaml` with `durandtibo/workflow-config-action`. The matrix
  has one runner per system, because the package is pure Python.

The package name and version are never duplicated in the workflows: they are read from
`../pyproject.toml` by the `durandtibo/extract-pyproject-metadata-action` composite action, wrapped
in `lib-get-package-metadata.yaml` so that a job can use them through `needs:`.

## Validating changes to this directory

`workflows/ci-verify-workflows.yaml` runs `durandtibo/verify-github-workflow-action` on
every pull request and push to `main`, checking pinning and
general workflow correctness. Locally, `actionlint` (run from this
directory) and a YAML syntax check are good pre-flight checks before pushing:

```bash
cd .github/workflows && actionlint
python3 -c "import yaml, glob; [yaml.safe_load(open(f)) for f in glob.glob('*.yaml')]"
```
