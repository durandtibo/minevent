# Codebase review and suggestions

Reviewed at `976989a` (`main`): every tracked file (`src/`, `tests/`, `dev/`, `docs/`, `.github/`,
`.make/`, packaging and config). The previous version of this file described the code before
payloads, `once`, `Subscription`, async, locking, the extra conditions and the `ValueError`/`TypeError`
changes. Nearly all of its items have been fixed, so this version is rewritten from scratch against
the current code.

Baseline: `ruff check`, `ruff format --check`, `ty check`, the 288 tests (100% line and branch
coverage) and the 31 source doctests all pass. The items below are things that baseline does not catch.

Items marked **[verified]** were reproduced with a script against the current code, not just read.
Priority: **P0** bug, **P1** design flaw or likely user pain, **P2** quality, **P3** nice to have.
Breaking changes are acceptable (the README says the API is unstable before 1.0).

---

## 1. Bugs

### 1.1 (P0) [verified] A `once` handler can run more than once under concurrency

`_OnceEventHandler.handle` (`manager.py:53`) calls `self.subscription.remove()` and ignores its
return value. Two threads that both took their snapshot before either removed the registration both
run the handler. With two threads synchronised right after `_start_trigger`, the wrapped handler ran
**2** times.

The "once from threads" integration test (`test_manager_threads.py`) only passes because the window
is tiny: it is a probabilistic test of a guarantee the code does not provide.

Fix: make the claim atomic, so only the caller whose `remove()` returns `True` runs the handler:

```python
def handle(self, **payload):
    if self.subscription is None or self.subscription.remove():
        self.event_handler.handle(**payload)
```

(Same in `ahandle`.) Then replace the integration test with a deterministic one using a
`threading.Barrier` between snapshot and dispatch, as in the reproduction.

### 1.2 (P0) `subscription` is attached to the `once` wrapper after it is visible

`add_event_handler` (`manager.py:257-261`) appends the wrapper under the lock, releases the lock,
builds the `Subscription`, and only then sets `registered.subscription`. A trigger from another
thread in that window runs the wrapper with `subscription is None`: it skips the removal and the
handler will run again at every later trigger. Build the `Subscription` first (it only needs
`registered`), assign it, then append under the lock.

### 1.3 (P1) [verified] Payload keys `event` and `self` collide with parameter names

`trigger_event(self, event, **payload)` means `manager.trigger_event("batch_end", event=e)` raises
`TypeError: got multiple values for argument 'event'`, and `self=...` does too. The same applies to
`handle(self, **payload)` and `ahandle`. Make the positional parameters positional-only:
`trigger_event(self, event, /, **payload)`, `atrigger_event`, `handle(self, /, **payload)`,
`ahandle`. This is source compatible for every normal call.

### 1.4 (P1) [verified] A coroutine handler passed to `trigger_event` is silently dropped

`EventHandler.handle` calls the function and discards the result. For `async def` handlers this
creates a coroutine that is never awaited: the only trace is a `RuntimeWarning` at garbage
collection (which is invisible in most apps, and an error only under pytest's `filterwarnings =
error`). The docstring of `ahandle` mentions it, but the failure mode is silent loss of work.

Suggestion: in `EventHandler.handle`, if `inspect.isawaitable(result)`, close it and raise
`TypeError("... returned an awaitable; use atrigger_event")`. Or at least `warnings.warn` right
there with the handler name. Add a test for the chosen behaviour.

### 1.5 (P1) [verified] `handler_args or ()` fails for array-like arguments

`EventHandler.__init__` (`handlers.py:248`) does `tuple(handler_args or ())`. For an object whose
truth value is ambiguous (a NumPy array or torch tensor passed as the sequence itself) this raises
`ValueError: truth value ... is ambiguous`. The library targets ML code, so write
`() if handler_args is None else tuple(handler_args)`. Same pattern for `handler_kwargs or {}`
(harmless for `Mapping`, but be consistent). Add a regression test.

### 1.6 (P1) `once` is consumed even when the condition is false

[verified] `EventHandler(f, condition=lambda: False)` registered with `once=True` is removed on the
first trigger without ever running `f`. That is surprising: "once" reads as "run once", not "give it
one chance". Either document it explicitly in `add_event_handler`, or (better) remove the
registration only after the wrapped handler actually ran. The latter needs `handle` to report
whether the condition fired, for example by having `EventHandler.handle` return `bool`.

### 1.7 (P2) User code runs while the manager lock is held

`remove_event_handler` calls `event_handler.equal(...)` inside `with self._lock`
(`manager.py:497-517`), and `__repr__` formats user handlers under the lock. `equal` goes through
`coola.objects_are_equal`, which can be slow for large tensors, and a custom `equal`/`__repr__` may
block or call back into the manager from another thread, which can deadlock. Take a snapshot under
the lock, compare outside it, then re-acquire the lock and remove by identity (the same
`_remove_registration` path `Subscription` uses). This also gives the two removal paths one
implementation (today one rebuilds the list and the other does `del handlers[i]`).

### 1.8 (P2) [verified] Unbounded recursion if a handler re-triggers its own event

A handler that triggers the event it handles raises `RecursionError`. The snapshot semantic is
fine, but this is an easy mistake in training code (`after_epoch` handler that triggers
`after_epoch`). Consider a re-entrancy guard (opt-in or raising a clear `RuntimeError`), or at least
a sentence in the `trigger_event` docstring.

### 1.9 (P2) [verified] Empty `EventManager.__repr__` has trailing whitespace

`repr(EventManager())` yields ` (event_handlers):` followed by a newline (a trailing space).
`_format_event_handlers` returns `""` and the format adds the separator regardless. Trailing
whitespace is stripped by the `trailing-whitespace` pre-commit hook, so the docs show a different
output than the code produces: running the docs as doctests (see 5.1) fails on this exact line in
`quickstart.md:227`. Return `"{}"` or `"()"` for the empty case, and cover `repr` with an exact
string test.

---

## 2. API and design

### 2.1 (P1) `last_triggered_event` has unclear value

It is set when dispatch starts, so it is only meaningful in single-threaded code and a handler that
reads it sees its own event. Under threads it is a last-writer-wins race. Nothing in the library
uses it. Options: remove it (breaking, but it pollutes `__repr__`, `reset()` and the lock scope), or
keep it and say in the class docstring that it is informational and not thread-meaningful.

### 2.2 (P1) No way to see what is registered, only whether something is

There is `events`, `__contains__` and `has_event_handler(handler)` (which needs a handler built to
match). Add `get_event_handlers(event) -> tuple[BaseEventHandler, ...]` (a snapshot) and `__len__`
(number of registrations). It makes debugging and tests simpler, and lets tests stop reaching for
`repr`.

### 2.3 (P1) Equality-based lookup is the weakest part of the API

`has_event_handler`/`remove_event_handler` depend on `coola.objects_are_equal`, which falls back to
`==`: lambdas, closures and bound methods of different instances never match [verified:
`has_event_handler(EventHandler(lambda: 1))` is `False` after registering an identical lambda].
`Subscription` already solves removal. Options, in order of preference:

1. Keep equality but document the limits prominently (partly done), and steer all docs toward
   `Subscription` (see 5.2: the docs still teach the equality workflow).
2. Make `remove_event_handler` / `has_event_handler` accept a `Subscription` as well.
3. Drop `coola` (see 4.1) and compare with `==`/`is`.

### 2.4 (P2) `Subscription` conveniences

- Context manager (`with manager.add_event_handler(...) as sub:` removes on exit) for scoped
  instrumentation such as a profiler active during one phase.
- `__bool__`/`active` property to tell if it is still registered.
- Allow `manager.add_event_handler` to be used as a decorator factory, e.g. `@manager.on("e")`,
  which returns the function unchanged. Tiny, and popular in event libraries.

### 2.6 (P2) Payload is all-or-nothing

Every handler receives the whole payload and raises `TypeError` if it does not accept a key
[verified]. In training loops, handlers with different needs (`loss` vs `epoch`) cannot share an
event unless each takes `**kwargs`. Options: an opt-in `EventHandler(..., filter_payload=True)` that
passes only the keys the signature accepts (via `inspect.signature`, computed once at construction),
or document the `**_` idiom in the quickstart.

### 2.7 (P2) Combinators evaluate every operand (no short-circuit)

This is deliberate and documented (stateful operands advance together), but it makes
`AndCondition(cheap, expensive)` always pay for `expensive`. Offer `short_circuit: bool = False` or
document the trade-off in the "conditions" page, not only in the docstring.

### 2.8 (P2) Stateful conditions are shared by reference

One `PeriodicCondition` instance passed to two handlers shares a counter, and this is only a
docstring warning. Consider `condition.copy()`/`__copy__` or documenting `functools.partial`-style
factories. For `once=True`, nothing else is needed, but for `OnceCondition` combined with
`once=True` there are now two mechanisms for "run once"; mention which to prefer.

### 2.9 (P2) Weak references to bound methods

`EventHandler(self.method)` keeps `self` alive for the lifetime of the manager. The troubleshooting
page's "Memory Leaks" answer is a hand-rolled `weakref` handler that is not even a valid
`BaseEventHandler` (no `equal`, wrong `handle` signature). A `weak=True` option using
`weakref.WeakMethod` (auto-unsubscribing when the owner dies) would replace that recipe. The
architecture page lists weak references as a non-goal, so decide and align the docs either way.

### 2.10 (P3) Exception policy

Fail-fast is documented, and the docs tell users to wrap handlers in `try/except`. An opt-in
`trigger_event(..., on_error="raise" | "collect")` that raises an `ExceptionGroup` after all handlers
ran (Python >= 3.11 is the minimum) would remove that boilerplate. Not needed for a minimal library;
mention as a conscious non-goal if you decline.

### 2.11 (P3) `Any` for payload and `Callable` plumbing

`**payload: Any` could be `**payload: object`. `ANN401` is globally ignored in `pyproject.toml`;
enable it and fix the few places that really mean `object`.

---

## 3. Tests (`tests/`)

All checks below were computed by script over `tests/`, against the rules in `CLAUDE.md`.

- (P1) **One-assert rule is broken in about 35 tests.** Examples:
  `test_handlers.py` (`test_event_handler_without_args_and_kwargs`: 3 asserts; the four
  `test_event_handler_handle_*`: 4 asserts; `test_event_handler_condition_*`: 4 asserts),
  `test_manager.py` (`test_event_manager_contains`: 3 asserts;
  `test_event_manager_last_triggered_event_after_trigger`: 3). Split them, or assert one tuple/dict
  of the observable state. Tests with a `for`/`if`: `test_event_handler_condition_handle_10`,
  `test_event_handler_condition_combinator`, `test_event_manager_no_duplicate`,
  `test_event_manager_atrigger_event_mixes_sync_and_async_in_order`; parametrize them.
- (P1) **No deterministic concurrency test.** The race in 1.1 passes the current thread test. Add a
  barrier-based test (see 1.1) and a test for 1.2. Keep randomised stress tests, but do not count
  them as proof.
- (P1) **Missing regression tests** for the items in sections 1 and 2: payload keys `event`/`self`,
  coroutine handler through `trigger_event`, array-like `handler_args`, `once` + false condition,
  `repr` of an empty manager (exact string), re-entrant trigger.
- (P2) **Malformed section headers** (rule: three lines, 5 spaces each side of the name):
  `test_manager.py:602` (`#     Tests for _unwrap #`), `test_utils.py:11` and `:64`.
- (P2) **Misplaced and duplicated tests** in `test_manager.py`:
  `test_event_manager_subscription_remove_second_registration` (line 616) sits under the `_unwrap`
  header; `test_event_manager_remove_event_handler_after_trigger` (224) and
  `..._after_trigger_event` (774), and `test_event_manager_trigger_event_does_not_register_event`
  (212) and `..._unknown_event_does_not_register_it` (782), test the same thing. Delete one of each
  pair. The file is 849 lines; split it into `test_manager.py`, `test_manager_once.py`,
  `test_manager_async.py`.
- (P2) `tests/unit/utils.py::Tracer` re-implements `unittest.mock.Mock(wraps=f)` and carries its own
  test file. Module-level `@trace` handlers share state across tests via `_reset_tracer` fixtures
  (a `pytest-xdist` hazard). Replace it with `Mock`, or with per-test local functions.
- (P2) `test_init.py` patches `importlib.metadata.version` for the fallback and `package_checks.py`
  only verifies `__version__ != "0.0.0"`, so the "patched stand-in vs real thing" rule is only met
  half way. This goes away if the lazy `__version__` is removed (4.2).
- (P3) Property-based tests (Hypothesis) for `PeriodicCondition`/`AfterNCondition` against a
  closed-form oracle, and for "add then `Subscription.remove` leaves the manager unchanged".
- (P3) `tests/package_checks.py` (run by `ci-build`) only covers a bare trigger. Extend it to
  exercise `once`, a payload and `atrigger_event` against the built wheel.

---

## 4. Source, packaging and configuration

### 4.1 (P1) `coola` is the only dependency and costs 90% of the import time

[verified] `import minevent` takes about 43 ms, of which `coola` is about 39 ms (it imports its whole
equality interface eagerly). It is used for `objects_are_equal` (equality) and three `str_*`
formatters. Because `Subscription` makes equality optional for removal, a zero-dependency
`minevent` is realistic: compare with `==`, write a 10-line indenter for `__repr__`. That also
deletes `ci-test-deps`, `ci-test-code-dep`, `nightly-test-package-dep`, `lib-get-package-versions`,
`dev/generate_versions.py`, `dev/config/package_versions.json` and the version table in the README
(about a fifth of the CI surface). If equality of array arguments is wanted, make `coola` an
optional extra and import it lazily, as CLAUDE.md already requires for numpy/torch.

### 4.2 (P2) Lazy `__version__` saves nothing and hides the attribute from tools

[verified] `importlib.metadata` is already imported by `coola` (it shows in the import profile under
`coola`), so the PEP 562 `__getattr__`/`__dir__` in `__init__.py` defers a cost that is paid anyway.
Meanwhile `ty`/IDEs cannot see `minevent.__version__`, `__all__` lists a name that is not defined,
and four tests plus a `"0.0.0"` fallback exist to support it. Either import `version` eagerly (3
lines), or, if `coola` goes away (4.1), keep it lazy and measure.

### 4.3 (P2) `ruff` config

- Keep `ERA` (already on). Enable `ANN401` and `DOC` (pydoclint, preview) to enforce the
  `Args/Returns/Raises` convention that CLAUDE.md demands.
- `pytest` `addopts` uses `--color yes` unconditionally, which pollutes CI logs and redirected output
  . Let pytest auto-detect.
- `[project.optional-dependencies]` is an empty table whose only purpose is the generated, empty
  `all` extra (`Provides-Extra: all` in the built wheel). The nightly workflow installs
  `minevent[all]` for nothing. Remove the table, the `autoextras` build hook, and the `-all`
  nightly jobs, or document why they stay.
- Classifiers: `Operating System :: POSIX :: Linux` and `MacOS` only, but the package is pure
  Python and nothing blocks Windows. Either use `OS Independent` or add Windows to CI. "Development
  Status :: 4 - Beta" contradicts the README's "no API is guaranteed" notice; use `3 - Alpha` or
  update the notice. `Python :: 3.15` is advertised: confirm the matrix tests it.

### 4.4 (P3) `__init__.py` export list is hand-maintained in three places

Each new symbol is added to the submodule `__all__`, the import block, and the top-level `__all__`.
That is fine at this size; `tests/package_checks.py::check_exports` guards it.

---

## 5. Documentation

### 5.1 (P1) [verified] The Markdown docs are not tested and have already drifted

`ci-doctest.yaml` only runs `xdoctest` on `src/`. Running the docs through
`pytest --doctest-glob='*.md' docs/docs README.md` shows `quickstart.md:227` already fails (see 1.9).
Only the `pycon` blocks (29 in `quickstart.md`, one each in `README.md` and `index.md`) are
executable at all; `get_started`, `architecture`, `faq`, `best_practices` and `troubleshooting` have
none, and their plain `python` blocks are checked by nothing. Add that command to CI, convert
code blocks to `pycon` where practical, and consider `pytest-markdown-docs` or `mktestdocs` for the
plain blocks.

### 5.2 (P1) [verified] `best_practices.md`, `faq.md`, `troubleshooting.md` do not know the new API

Zero mentions of `Subscription`, `missing_ok`, `once=True` or `atrigger_event` in these three files
(`quickstart.md` was updated). Concretely:

- `faq.md:167`, `architecture.md:244` and `troubleshooting.md:149` define custom handlers as
  `def handle(self) -> None`. With a payload, `trigger_event("e", epoch=1)` raises `TypeError` for
  such a handler. They must be `handle(self, **payload)`.
- `troubleshooting.md` "Event Does Not Exist" / "Handler Not Found" teach
  `if manager.has_event_handler(...): try: remove...`, which is racy and verbose; the answer is
  `missing_ok=True` or the `Subscription`.
- `troubleshooting.md` "Memory Leaks" shows a `weakref` handler that is not a `BaseEventHandler`
  (no `equal`, wrong `handle`); see 2.9.
- `architecture.md` "Custom Event Manager" sketches `trigger_event(self, event)` with no payload,
  without `atrigger_event`, `clear_event`, `once`; and the registration flow still says
  `_event_handlers["event"].append(...)` as if it were a `defaultdict`. The "Use Cases" under it
  ("Thread-safe event managers") are now what `EventManager` is.
- `README.md` "Features" does not mention payloads, `once`, subscriptions, async or thread safety,
  which are the library's main additions since 0.5.0.

### 5.3 (P2) Overlap between FAQ, troubleshooting and best practices

The three pages repeat the same advice (duplicates, exceptions in handlers, testing with mocks,
logging). About 1,100 lines for a 3-class library. Merge into one "Guide" page plus an FAQ of
short answers that link into it, and let `quickstart.md` own all runnable examples.

### 5.4 (P2) Contributor docs refer to commands that do not exist

[verified] `CONTRIBUTING.md` step 4 says `make unit-test-cov`; `make: *** No rule to make target
'unit-test-cov'`. The unit tests run through `inv test.unit --cov` (see `.github/workflows`).
`CONTRIBUTING.md` should list the real entry points (`inv env.install`, `inv test.unit`,
`inv lint.check-python`, `pre-commit run --all-files`), which are three tools (`make`, `inv`,
`pre-commit`) with no overview. `CONTRIBUTING.md` also never mentions type checking (`ty`).

### 5.5 (P2) `mkdocs.yml`

`pymdownx.emoji` uses `!!python/name:` tags, which is why `check-yaml --unsafe` is needed. Drop the
extension unless emoji are used (grep shows none in `docs/docs`). `pymdownx.snippets` is enabled but
unused. The `GitHub` nav entry duplicates `repo_url`.

### 5.6 (P3) Other

- `CITATION.cff` has no `version` / `date-released`; update them in the release workflow.
- The README version table keeps 14 rows of history; keep the last three rows and link the
  changelog for the rest.
- `CHANGELOG.md` has no link targets for `0.5.0` and no release procedure; add "move `Unreleased`
  into a dated heading" to the release checklist.

---

## 6. CI/CD and tooling (`.github/`, `.make/`, `dev/`)

For a library with about 400 statements there are 35 workflow files. Not wrong, but the following
add cost without adding signal.

- (P1) **Redundant `min` job.** `ci-test.yaml` runs the `all` and `min` jobs; `min` uses
  `--no-optional-deps` but there are no optional dependencies, so it is an exact duplicate on every
  OS x Python cell. Replace it with `uv sync --resolution lowest-direct`, which tests the real
  `coola>=1.0` lower bound, or delete it.
- (P1) **No `concurrency` group** on `ci.yaml` (only `release-pypi` and the Makefile-sync workflow
  have one), so every push to a PR branch runs the full matrix to completion. Add
  `concurrency: {group: ${{ github.workflow }}-${{ github.ref }}, cancel-in-progress: true}` for PR
  events. It would also likely reduce the need for the hourly `bot-cancel-stale-queued-runs`
  workflow.
- (P1) **No tag/version consistency check in `release-pypi.yaml`.** The workflow triggers on
  `v*.*.*` but `pyproject.toml` has a static `version = "0.5.0"`. Nothing verifies the tag equals the
  project version, so a mismatched tag publishes the wrong number to PyPI. Add a step comparing
  `${GITHUB_REF_NAME#v}` with `uv version --short` before building.
- (P2) **`ci.yaml` also runs on a daily `schedule`** (full matrix, including docs build) while
  `nightly-package.yaml` and `nightly-test-package*.yaml` run separately. One nightly entry point
  is easier to read.
- (P2) **Overlapping dependency bots.** `dependabot.yml` (uv + actions, weekly),
  `bot-update-deps` (Saturday), `bot-pre-commit-autoupdate`, `bot-pin-action` and
  `bot-generate-package-versions` all touch dependency pins. Keep one mechanism per concern, for
  example Dependabot for `uv` and actions, `pre-commit.ci` or Dependabot for hooks. Check whether
  `bot-pin-action` (which maintains the `ratchet:` pins) overlaps with the Dependabot actions entry.
- (P2) **Timeouts and cost.** The test suite runs in 0.6 s but every cell gets a 10-minute timeout
  and runs on all Python versions x OS. Test the full matrix on Linux and only oldest/newest on
  macOS; `ci-test.yaml` already notes macOS and free-threaded cells are slow.
- (P2) **Docs build job** in `ci-doctest.yaml` publishes to a throwaway branch name
  (`tmp-doc-build-1234`) with `mike deploy`; `mkdocs build --strict` checks the same thing without
  needing git credentials or the bot email secret, and `--strict` turns broken cross-references into
  failures. Add `--strict` either way.
- (P2) `dev/generate_versions.py` has no test and depends on the `feu` network API; if 4.1 is not
  adopted, add a smoke test with the network call mocked.
- (P3) `.pre-commit-config.yaml`: `ty` runs as `language: system` (`uv run ty check`) and
  `docformatter` also runs as a `local` hook; the former bypasses pre-commit's isolated
  environments, so it deserves a one-line comment. The `uvx pip-audit` step
  in `security-audit.yaml` is weekly only; also run it on PRs that touch `uv.lock`.
- (P3) `CODEOWNERS` has the same owner on both lines, so the `/.github/` rule adds nothing.
- (P3) `.make/` holds a second copy of `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `LICENSE`,
  `SECURITY.md`, `README.md` (synced from a shared repository). Searching the repo for a policy file
  returns two hits; the root copies should be the only ones indexed (exclude `.make/*.md` from
  markdownlint and from editors' search, or generate the root files from the shared source).

---

## 7. Suggested order of work

1. **Bug-fix PR (small, no API change):** 1.1 and 1.2 (`once` atomicity and ordering) with a
   deterministic test, 1.5, 1.9, and the `CONTRIBUTING.md` command (5.4).
2. **Semantics PR (small, breaking only for odd callers):** 1.3 positional-only `event`/`self`/payload
   parameters, 1.4 coroutine through `trigger_event`, 1.6 `once` with a false condition.
3. **Docs PR:** 5.2 (stale handler signatures and removal recipes) and 5.1 (run Markdown doctests
   in CI), then merge FAQ/troubleshooting/best practices (5.3).
4. **Test hygiene PR:** section 3 (split multi-assert tests, headers, duplicates, replace `Tracer`).
5. **CI PR:** 6 (`concurrency`, drop the `min` job, tag/version check, `mkdocs build --strict`).
6. **Decision PR (breaking):** 4.1 drop or make optional `coola`, 2.1 `last_triggered_event`,
   then 2.2-2.4 conveniences and 2.9 weak references if wanted.

## Not changed / decisions that look right

- Snapshot-on-trigger with a reentrant lock and handlers running outside it is the correct design,
  and the thread-safety section of the architecture page matches the code.
- `Subscription` removing by identity (not equality) is the right primitive.
- `EventHandler` copying `handler_kwargs` and rejecting `str` `handler_args`; `PeriodicCondition`
  validation; `TypeError` for non-`str` events and `ValueError` + `missing_ok` for removal.
- Combinators evaluating all operands (documented), keeping stateful conditions in step.
- Keeping `tests/integration` for cross-thread tests, `filterwarnings = error`, and the pinned
  (`ratchet:`) GitHub Actions.
