# Codebase review and suggestions

Scope: every tracked file (`src/`, `tests/`, `dev/`, `docs/`, `.github/`, `.make/`, packaging and
config). The library itself is small (about 800 lines including docstrings), so most of the value is
in API semantics, a few latent bugs, and repo hygiene. Breaking changes are allowed, since the
README states the API is unstable before 1.0.

Priority legend: **P0** bug or surprising behavior, **P1** API/design improvement,
**P2** quality/maintenance, **P3** nice to have.

---

## 1. Bugs and surprising behavior in `EventManager` (`src/minevent/manager.py`)

### 1.1 (P0) Read operations mutate the internal `defaultdict`

`_event_handlers` is a `defaultdict(list)`, so plain reads create keys:

- `trigger_event("x")` does `self._event_handlers[event]` (line ~121), which creates an empty entry
  for every event ever triggered, even when no handler exists.
- `has_event_handler(h, event="x")` does `self._event_handlers[evnt]` (line ~170), so a query
  creates an empty entry.

Consequences:

- `__repr__` lists phantom events with no handlers.
- `remove_event_handler("x", h)` after a `trigger_event("x")` raises
  _"handler is not found among registered..."_ instead of _"'x' event does not exist"_. The error
  depends on whether the event was previously triggered, and `remove_event_handler` itself relies on
  `event not in self._event_handlers`, which the other two methods corrupt.
- The dict grows without bound if event names are dynamic (for example `f"epoch_{i}"`).
- A query from another thread can raise `RuntimeError: dictionary changed size during iteration`
  while `has_event_handler` iterates over `self._event_handlers`.

Fix: use a plain `dict[str, list[BaseEventHandler]]` and read with `.get(event, ())`. Keep
`setdefault` only in `add_event_handler`. Add regression tests for `repr` after a trigger, and for
the `remove` error message after a trigger.

### 1.2 (P0) `has_event_handler(..., event="")` silently searches all events

`events = [event] if event else self._event_handlers` uses truthiness, so `event=""` means
"all events". Use `event is None`. This is a real, if unlikely, bug because an empty string is a
valid event name for `add_event_handler`.

### 1.3 (P0) Handlers added during a trigger run in the same trigger

`trigger_event` iterates the live list. If a handler calls `add_event_handler` for the same event,
the new handler is appended to the list being iterated and runs immediately. Meanwhile
`remove_event_handler` swaps the list, so the in-progress loop is unaffected and removed handlers
still run for the current dispatch. The two cases behave inconsistently. Iterate over a snapshot
(`tuple(self._event_handlers.get(event, ()))`) and document the semantic: "handlers registered or
removed during dispatch take effect on the next trigger".

### 1.4 (P1) Exception policy is undefined

If handler _k_ raises, handlers _k+1..n_ never run and `last_triggered_event` is already set. The
docs (`best_practices.md`, `troubleshooting.md`) tell users to wrap each handler in `try/except`,
which shows the library should offer a policy. Options:

- Keep fail-fast, and document it in the `trigger_event` docstring.
- Add `trigger_event(event, *, on_error="raise" | "log" | "collect")`. With `"collect"`, raise an
  `ExceptionGroup` (Python >= 3.11 is already the minimum) after all handlers have run.

### 1.5 (P1) `last_triggered_event` is set before the handlers run

If a handler raises, or a handler reads `manager.last_triggered_event`, the semantics are unclear.
Decide whether it means "last event whose dispatch started" or "last event that completed", and
document it. Also check that the feature earns its place: nothing in the repo uses it besides
tests and docs. Consider removing it or replacing it with an opt-in hook.

### 1.6 (P1) `event` is coerced with `str()` in `add_event_handler` only

`add_event_handler(1, h)` stores the key `"1"`, but `trigger_event(1)` looks up the key `1` and
finds nothing. Either coerce everywhere or, better, reject non-`str` events with a `TypeError`.
Also consider accepting any hashable, or an `enum.StrEnum`, to avoid typos in magic strings (see
2.3).

### 1.7 (P2) `remove_event_handler` raises `RuntimeError`

`KeyError` or `ValueError` would be more idiomatic and match `list.remove`. Add an opt-out
`missing_ok: bool = False` parameter. Currently users must wrap it in `try/except RuntimeError`,
which is a very broad exception type.

### 1.8 (P2) `__init__` calls `self.reset()` after initialising the same fields

`self._event_handlers = defaultdict(list)`, `self._last_triggered_event = None`, then `reset()`
clears them again. Pick one. Also annotate the attributes (`self._event_handlers: dict[str,
list[BaseEventHandler]] = {}`). The bare `defaultdict(list)` is untyped, so `ty` infers `Unknown`.

### 1.9 (P2) `__repr__` is hard to read

The nested `"\n" + str_sequence(...)` plus conditional strings is hard to follow and produces odd
output for empty managers. Build the representation in a helper and cover it with a snapshot test
(the current tests only assert `startswith("EventManager(")`).

### 1.10 (P3) Missing small conveniences

- `__len__` / `__contains__`, and an `events` property (list of events with handlers).
- A `clear_event(event)` method. `reset()` is the only way to clear.
- `add_event_handler` could return the handler, and `trigger_event` could return nothing or a count.
  This makes decorator-style registration possible:

  ```python
  @manager.on("after_epoch")
  def log(): ...
  ```

- A `trigger_event(event, *args, **kwargs)` form so handlers can receive context (see 2.1).

---

## 2. API and design

### 2.1 (P1) Handlers cannot receive event data

`BaseEventHandler.handle()` takes no arguments, and `trigger_event` takes no payload. Everything the
handler needs must be bound at registration time (`handler_args`, `handler_kwargs`, closures). For
the stated target (ML training loops) this is the main practical limitation. Users want the epoch,
the loss, or the model at trigger time. The docs (`architecture.md`) even sketch an
`Event(name=..., priority=...)` object that does not exist.

Proposal (breaking): `trigger_event(event, **payload)` calls `handler.handle(**payload)`, or passes
a small immutable `EventContext`. Keep the zero-argument form as the default so existing code still
works.

### 2.2 (P1) `EventHandler` vs `ConditionalEventHandler` vs `BaseEventHandlerWithArguments`

Three classes plus a base class for what is functionally "callable + args + optional condition".
Issues:

- `BaseEventHandlerWithArguments` and `EventHandler` have identical bodies except for `equal`.
- `equal` is copy-pasted in both subclasses, and `__repr__` is copy-pasted too.
- `isinstance(other, EventHandler)` in `EventHandler.equal` means a user subclass of `EventHandler`
  compares equal to a plain `EventHandler`, while `ConditionalEventHandler` is not a subclass, which
  is inconsistent.

Proposal: collapse into one `EventHandler(handler, *args, condition=None, **kwargs)` or
`EventHandler(handler, args=(), kwargs=None, condition=None)`. Keep `ConditionalEventHandler` only
as a deprecated alias for one release. Implement `equal` once in the base class by comparing
`type(self) is type(other)` and a `_key()` tuple.

### 2.3 (P1) Equality semantics: `objects_are_equal` is heavy, and surprising for callables

`equal` relies on `coola.objects_are_equal`, which, for functions, falls back to `==`:

- Lambdas and bound methods compare unequal across instances (`obj.method != other.method`), so
  `has_event_handler` and `remove_event_handler` often silently fail for them. The docs only
  partially warn about this.
- For tensors or arrays in `handler_args`, `objects_are_equal` is exactly right, but it is the only
  reason `coola` is a runtime dependency. That is a heavy dependency for a "minimal" library,
  and `coola` has changed major versions three times (see the README table).

Options:

1. Drop `coola` and compare with `==` and `is` (zero dependencies), documenting that handlers
   with array arguments should use identity.
2. Keep `coola` but make it an optional extra and fall back to `==`.
3. Return a registration token from `add_event_handler` (see 2.4) so removal never needs equality.

I recommend (3) combined with (1). The whole `equal` abstraction then becomes optional.

### 2.4 (P1) Add a way to unsubscribe without re-creating an equal handler

Removal requires constructing an equal handler again. Return a `Subscription`/token (or the
handler) from `add_event_handler`, with `.remove()` support. This also avoids the "remove deletes
all duplicates" surprise (documented, but rarely wanted). Also consider a `once=True` option, which
the quickstart currently emulates by hand with `has_event_handler` (`quickstart.md` ~line 343).

### 2.5 (P1) `PeriodicCondition` has shared mutable state and a fragile contract

- `freq=0` constructs successfully and fails later with `ZeroDivisionError` inside `evaluate()`.
  Negative values are accepted silently (`step % -3` works, but is meaningless). The docstring
  admits this. Validate in `__init__` (`ValueError` for `freq < 1`) and update the tests.
- `int(freq)` silently truncates `2.9` to `2`. Reject non-integers.
- `equal` ignores `_step`, so two conditions with different progress compare equal. That is probably
  intended for duplicate detection but must be documented. The state is also shared if the same
  condition instance is passed to two handlers.
- `evaluate()` has a side effect (increments a counter), so it is not idempotent, which is not
  obvious from the name. Consider `__call__`/`should_run()` or a `reset()` method.
- No way to express "every N calls but skip the first" (the docstring says it fires on the first
  call, which matches 0-based epoch semantics but not "every 10th epoch" in the usual meaning).
  Add `offset`/`skip_first`.
- Use `itertools.count()` for the counter, and annotate `freq: int` as positive.

### 2.6 (P2) Conditions only exist as a class hierarchy

`ConditionalEventHandler` accepts any `BaseCondition`, yet the test `callable_condition` and docs
suggest plain callables might be accepted. Allow `Callable[[], bool]` as a condition (via a
`Protocol`) so users do not need to subclass an ABC with two abstract methods (`equal` +
`evaluate`) for a one-liner. Provide a couple more built-ins (`AlwaysCondition`, `OnceCondition`,
`AfterNCondition`, combinators `AndCondition`/`OrCondition`/`NotCondition`) if the "conditions" idea
is meant to be a selling point. At present there is exactly one concrete condition.

### 2.7 (P2) `__eq__` without `__hash__`

Both ABCs define `__eq__` and silence `PLW1641` with `# noqa`, which leaves instances
unhashable (`Python` sets `__hash__ = None`). That prevents putting handlers in sets or as dict
keys. Either define a consistent `__hash__` (impossible with `objects_are_equal` semantics), or
document it as an intentional property. Having `__eq__` delegate to an `equal` method that other
code calls directly is also an API duplication. One of them should be the primary API.

### 2.8 (P2) Defensive copying

`handler_kwargs` is stored by reference (`handler_kwargs or {}`), and the property returns the live
dict. Mutating the caller's dict later changes the registered handler, which also invalidates
`equal`. Copy on construction (`dict(handler_kwargs or {})`) or expose a read-only
`MappingProxyType`.

### 2.9 (P3) Async support

`architecture.md` says async is a non-goal and recommends threads. If the target audience includes
async training or serving code, `atrigger_event` (awaiting coroutine handlers) is a small addition
that would remove the need for the thread-pool workaround documented in `troubleshooting.md`.

### 2.10 (P3) Thread safety

Documented as unsupported. A lock around mutations and a snapshot on trigger (1.3) would make the
manager safe for the common "register in main thread, trigger from worker threads" pattern, and the
CI already tests free-threaded builds (3.14t), where races are likelier. At least test and document
the guarantee that does hold.

---

## 3. Typing and docstrings

- (P1) `Callable` is unparameterised everywhere (`handler: Callable`). Use `Callable[..., Any]`, or
  better, `Callable[..., object]`. With a `ParamSpec`-based generic handler the arguments could even
  be type-checked against `handler_args`.
- (P2) `handler_kwargs: dict[str, Any]` should be `Mapping[str, Any]`, `handler_args:
Sequence[Any]` should reject `str` (a `str` is a `Sequence`, so `handler_args="abc"` silently
  becomes `("a", "b", "c")`).
- (P2) `BaseCondition.__eq__` returns `self.equal(other)` and `equal` takes `Any`. Use
  `object` instead of `Any` for `other`.
- (P2) `ty` only checks `src` (`[tool.ty.src] include = ["src"]`). Include `tests`, since the
  test helper `trace` assigns attributes on functions (`wrapper.called = ...`), which a checker
  would flag. Replace it with `unittest.mock.Mock`/`MagicMock` or a small callable class.
- (P2) The module `__init__` has `__all__` containing `__version__`; fine, but also export
  `__version__` consistently, and avoid the `"0.0.0"` fallback masking a broken install.
- (P3) Docstrings: `r"""` prefixes are used on all docstrings with no backslashes. Harmless but
  noisy. Several "Returns:" blocks have inconsistent indentation, and `BaseEventHandlerWithArguments`
  docs show `EventHandler` examples. Docstring style is otherwise good.

---

## 4. Tests (`tests/`)

- (P1) Tests access private state (`event_manager._event_handlers[...]`) in about ten places.
  Assert behavior through the public API (`has_event_handler`, `trigger_event`) so that the
  refactors in section 1 do not need test rewrites.
- (P1) Missing coverage for real-world cases:
  - handler raising an exception during `trigger_event` (and the order of later handlers),
  - handler adding/removing handlers during dispatch,
  - `trigger_event` followed by `remove_event_handler` (bug 1.1),
  - `has_event_handler(event="")` (bug 1.2),
  - `PeriodicCondition(0)` / negative / float,
  - `ConditionalEventHandler` inside a manager, and `has_event_handler` with a conditional handler,
  - `__repr__` content (not just `startswith`),
  - a custom `BaseCondition`/`BaseEventHandler` subclass, to prove the extension story in the docs,
  - `handler_args` as a `str` (pitfall above) and mutation of `handler_kwargs` after construction.
- (P2) `trace` in `tests/unit/utils.py` plus the identical `_reset_tracer` fixture duplicated in
  `test_manager.py` and `test_handlers.py` is reinventing `Mock`. Replace with `Mock(spec=...)`, or
  move the fixture to `tests/conftest.py`. Module-level state shared between tests is also a
  `pytest-xdist` hazard.
- (P2) `PeriodicCondition` tests spell out ten-element boolean lists. Use `parametrize` with a
  generated expected list (`[i % freq == 0 for i in range(10)]`) or a compact string
  (`"TFFTFFTFFT"`).
- (P2) Tests are duplicated: `test_last_triggered_event_name_after_fire` and
  `test_event_manager_last_triggered_event` check the same thing, and
  `test_event_handler_handle_1`/`_10` appear to differ only by parameter, so parametrise them.
  Naming also drifts (`test_event_handler_handle_*` is used for `ConditionalEventHandler` tests).
- (P3) Add property-based tests (Hypothesis) for `PeriodicCondition` (`evaluate` is True exactly
  at multiples of `freq`) and a few invariants for the manager (add then remove is a no-op).
- (P3) `tests/package_checks.py` is not named `test_*`, which is intended (it is run by the
  package workflow), but it only asserts a happy path. Extend it to import every symbol in
  `__all__` and check `__version__`.

---

## 5. Packaging and configuration (`pyproject.toml`, `uv.lock`, root files)

- (P1) Build artifacts `coverage.xml`, `htmlcov/`, and `dist/` exist in the working directory. They
  are ignored by git (good), but `dist/` and the others should be removed regularly. `make clean`
  does not remove `dist/`. Add it.
- (P2) `[tool.uv.pip] torch-backend = "auto"` is irrelevant to this project (no torch dependency).
  It looks copy-pasted from another repo. Remove it.
- (P2) `[project.optional-dependencies]` is an empty table that is still consumed by the
  `autoextras` build hook and by `dev/generate_versions.py`
  (`read_pyproject_optional_dependencies`). Either delete both, or document why they remain.
  README line "no optional dependencies or extras are required" matches reality.
- (P2) Classifier `Programming Language :: Python :: 3.15` is listed, but the 3.15 interpreter is
  pre-release for much of its life. Make sure CI actually tests it (`lib-get-test-matrix.yaml`) or
  drop the classifier. "Development Status :: 4 - Beta" is also at odds with the README's "no API is
  guaranteed" notice.
- (P2) `coola>=1.0,<2.0` is the only runtime dependency, and it is used only for equality and
  formatting helpers (`str_indent`, `str_mapping`, `str_sequence`). See 2.3. Dropping it makes
  `minevent` a true zero-dependency package, which fits the "minimal" pitch and removes the
  yearly cross-major compatibility burden visible in the README table.
- (P2) `[tool.ruff.lint]` selects `NPY` and `PD` (NumPy, pandas), and contains `ANN401` ignored,
  `PLR0913` ignored. Those are copy-paste from a data library. Prune what is not relevant.
  Conversely, consider enabling `DOC` (pydoclint, preview) and `ERA` (commented-out code).
- (P2) `pytest` `filterwarnings = ["error"]` is great. `log_level = "DEBUG"` globally, together
  with `--durations 10`, is noisy. Set it per test with `caplog` where needed.
- (P3) `[tool.codespell] skip` mentions `./docs/site`; verify the path (`docs/site` is the mkdocs
  default output, but not present).
- (P3) `CODEOWNERS` has two lines and a single owner. Fine, but add `/.github/` ownership rules or
  remove the file if unused.
- (P3) Both `CONTRIBUTING.md`/`CODE_OF_CONDUCT.md` and `.make/CONTRIBUTING.md`/
  `.make/CODE_OF_CONDUCT.md` exist, along with `.make/LICENSE`, `.make/SECURITY.md`, and
  `.make/README.md` (synced by `bot-sync-shared-makefile.yaml`). It is confusing to have two copies
  of governance files. Exclude `.make/*.md` from the sync, or from the repo root searches, so
  contributors do not edit the wrong one.

---

## 6. Documentation (`README.md`, `docs/`)

- (P0) The README badges point to workflows that do not exist:
  `nightly-tests.yaml`, `docs.yaml`, `docs-dev.yaml`. The existing files are
  `nightly-test-package.yaml`, `nightly-test-package-dep.yaml`, `release-docs.yaml`, and
  `release-docs-dev.yaml`. `docs/docs/index.md` uses yet another form (`workflows/Nightly%20Tests/
badge.svg` by workflow _name_). Badges render as "no status" or broken.
- (P1) `README.md` and `docs/docs/index.md` are two diverging copies of the same content (badges,
  overview, install). Use `mkdocs-include-markdown-plugin` (already a dependency in the `docs`
  group) to include the README, or trim `index.md` to the essentials. Note the README version table
  lists `0.5.0` as `>=3.10`, while `main` is `>=3.11`.
- (P1) Documentation volume (about 2,450 lines in `docs/docs`) is large compared with about 800
  lines of source, and much of it is speculative:
  - `architecture.md` describes hypothetical features ("Thread-Safe Event Managers", "Async
    Support", an `Event(name=..., priority=...)` object) and comparison tables against other
    libraries. These are easy to go stale and make the library look more featureful than it is.
    Move them to a short "Roadmap/Non-goals" section or delete them.
  - `best_practices.md`, `troubleshooting.md`, and `faq.md` repeat the same advice (exception
    handling, duplicates, testing with mocks). Merge them and de-duplicate.
- (P1) All Markdown code snippets should be executed in CI. `ci-doctest.yaml` covers docstrings
  via `xdoctest`, but the many ` ```python ` blocks in `docs/` are not tested. Use
  `pytest --doctest-glob`, `mktestdocs`, or `pytest-markdown-docs` to prevent drift.
- (P2) `mkdocs.yml` has the `pymdownx.emoji` configuration with `!!python/name:` tags, which makes the
  YAML unsafe to load (which is why `check-yaml --unsafe` is needed). Consider `material.extensions`
  string references (supported by recent versions) or remove emoji.
- (P2) Missing: a `CHANGELOG.md` (the `Changelog` URL points at GitHub Releases only), and a
  migration note for the `0.5.0 -> main` break (Python 3.10 dropped, `coola` 1.x).
- (P3) Grammar fixes in the overview: "allows to customize" -> "allows you to customize", "piece of
  code that are executed" -> "pieces of code that are executed". The same sentence is repeated in
  `CITATION.cff`.
- (P3) `README` still shows the Black badge although the project uses `ruff format`.
- (P3) `CITATION.cff` has no `version` or `date-released`. Add them and automate them in
  `release-pypi.yaml`.

---

## 7. CI/CD (`.github/`)

This is the most elaborate part of the repository (35 workflow files for a library with 3 modules).

- (P1) Maintenance cost vs benefit: there are seven `bot-*`, three `lib-*`, three `nightly-*`, and
  three `release-docs*` workflows. Consider whether `bot-pin-action` + `bot-pre-commit-autoupdate`
  - `bot-update-deps` + `bot-generate-package-versions` + `dependabot.yml` overlap (Dependabot is
    also configured). Pick one mechanism per concern.
- (P1) `ci-test-code-dep.yaml`, `ci-test-deps.yaml`, `nightly-test-package-dep.yaml`, and
  `lib-get-package-versions.yaml` test version matrices of `coola`. If `coola` is removed
  (5), roughly a quarter of the CI disappears, along with `dev/generate_versions.py` and
  `dev/config/package_versions.json`.
- (P2) `ci-test.yaml` runs the same test job for `all` and `min` (`--no-optional-deps`), but the
  project has no optional dependencies, so the `min` job is an exact duplicate on every OS and
  Python cell. Drop it, or replace it with a "lowest direct dependency versions"
  job (`uv sync --resolution lowest-direct`), which tests the `coola>=1.0` bound for real.
- (P2) Pass `permissions: contents: read` at the workflow level for every workflow, and verify each
  job pins the minimum. `ci-test.yaml` does. Run the same audit on the others (a check can be
  automated with `zizmor`).
- (P2) Add a `concurrency:` group to cancel superseded PR runs, which would make
  `bot-cancel-stale-queued-runs.yaml` unnecessary.
- (P2) Add `pip-audit`/`uv audit` and `zizmor` into `security-audit.yaml` if they are not there.
- (P3) The CI matrix includes macOS and free-threaded builds with a 10 minute timeout "because they
  are slow". For a pure-Python library with a sub-second test suite, test only
  `{ubuntu: all versions, macos + windows: oldest + newest}`. Windows is not in the classifiers
  (`Operating System :: POSIX :: Linux`, `MacOS`); either add Windows to CI and the classifier, or
  state that it is unsupported.

---

## 8. Developer tooling

- (P2) `tasks.py` is just `from invoke_tasklib import ns`. All task logic lives in an external
  `invoke-tasklib`, and `Makefile` provides a second, different set of targets (`format`, `lint`,
  `clean`) for non-Python files. Newcomers need to learn `make`, `inv`, and `pre-commit`. Document
  all three entry points in one place (`CONTRIBUTING.md` currently does not list the `inv` tasks).
- (P2) `dev/generate_versions.py` has `# noqa: INP001` and is invoked by a bot workflow. Add a
  smoke test, or run it in CI with a mocked network, since an upstream API change in `feu` breaks
  the bot silently.
- (P3) `.pre-commit-config.yaml` runs `ty` through `language: system` + `uv run`, which bypasses
  pre-commit's environment isolation. This is acceptable, but worth a comment. Also pin the hook
  revisions through a single mechanism (the `bot-pre-commit-autoupdate` workflow).
- (P3) Consider adding `mypy` or `pyright` strict runs alongside `ty` until `ty` is stable (it is
  still `0.0.x`).

---

## 9. Suggested roadmap

1. **Quick fixes (one PR):** items 1.1, 1.2, 1.3, 2.5 validation, 2.8, README badges (6), remove
   `torch-backend`, add tests for each.
2. **Semantics PR (breaking):** payload on `trigger_event` (2.1), exception policy (1.4), event key
   validation (1.6), `remove_event_handler` error type (1.7), subscription tokens (2.4).
3. **Simplification PR (breaking):** merge handler classes (2.2), accept plain callables as
   conditions (2.6), drop `coola` (2.3/5), delete the now-unneeded CI matrices (7).
4. **Docs PR:** consolidate and test the docs (6), add a CHANGELOG and a migration guide.
5. **Optional features:** async triggering (2.9), thread safety (2.10), more built-in conditions
   (2.6).
