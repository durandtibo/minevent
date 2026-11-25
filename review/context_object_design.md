# Design: pass a read-only `Context` to the handlers instead of the payload as keywords

Status: implemented with option A (#840, #841, #842, and the integration tests of step 4). The
body below is the proposal as it was written, and is not updated.
Nothing in `src`, `tests` or `docs` is changed by this document.
Items are tagged **[reading]** (from the code on `main`, `2f28f29`) or **[proposal]** (a design
choice, not measured). No prototype was built, so no cost or speed claim is made.

## 1. Problem

Today `trigger_event("epoch_end", epoch=3, loss=0.1)` calls every handler as
`handler(**payload)` [reading]. The handlers of one event usually need different values, so the
signature of a handler is coupled to the payload of the trigger:

- A handler that does not accept a key raises a `TypeError` (`unexpected keyword argument`), unless
  it was registered with `filter_payload=True` or has a `**kwargs` parameter.
- `filter_payload=True` makes the registration inspect the signature (`_accepted_keywords`) and
  drop the keys that the handler does not name. This is about 35 lines of `inspect` logic with
  special cases: `**kwargs` means "everything", `functools.partial` hides bound arguments, and a
  callable that cannot be inspected receives everything [reading].
- A key that the trigger does not provide is a `TypeError` at call time (`missing required
argument`), raised by Python, not by `minevent`. The handler cannot choose a default or a
  fallback unless it declares one in its signature.
- The whole behaviour is decided by two mechanisms (the signature of the handler and the
  `filter_payload` flag) that the reader of the handler must combine in their head.

## 2. Proposal

### 2.1 `Context`

A new public class `minevent.Context`: an immutable mapping from `str` to values, built by the
manager once per trigger from the payload.

```python
class Context(Mapping[str, object]):
    def __init__(self, data: Mapping[str, object] | None = None) -> None: ...
    def __getitem__(self, key: str) -> object: ...  # KeyError names the key and the available keys
    def __iter__(self) -> Iterator[str]: ...
    def __len__(self) -> int: ...

    # inherited from Mapping: get(key, default=None), __contains__, keys, items, values, ==
```

- **Read-only**: no `__setitem__`, no `update`, no `pop`. The data is copied at construction and
  held in a `types.MappingProxyType`, so neither the caller of `trigger_event` nor a handler can
  change what the next handler sees. The values themselves are not copied (a mutable value stays
  mutable, as today).
- **`get(key, default=None)`** is the way to read an optional value; `context[key]` is the way to
  read a required value and raises `KeyError`. The handler decides the behaviour when a value is
  missing: a default, a skip, or an error. `minevent` does not decide.
- Subclassing `collections.abc.Mapping` costs nothing at import (the module is already loaded by the
  interpreter) and gives `get`, `in`, `keys`, `items`, `==` and `dict(context)` for free. The
  alternative is a minimal class with only `get`, `__getitem__` and `__contains__`; it is smaller
  but a `Context` could not be passed where a `Mapping` is expected [proposal].
- A `Context` has no `event` or other metadata in this proposal. Adding `context.event` later is
  possible without a breaking change, which is an argument for an object over a bare `dict`.

### 2.2 Calling the handlers

```python
def on_epoch_end(context):
    epoch = context["epoch"]  # required
    loss = context.get("loss")  # optional


manager.add_event_handler("epoch_end", on_epoch_end)
manager.trigger_event("epoch_end", epoch=3, loss=0.1)  # trigger call is unchanged
```

`trigger_event(event, /, **payload)` keeps its signature. The manager builds one `Context` per
trigger and shares it with all the handlers (safe because it is immutable).

### 2.3 What replaces `filter_payload`

As asked, the registration only checks **whether the handler needs the context**:

| Handler signature            | Called as          |
| ---------------------------- | ------------------ |
| no parameter, e.g. `def f()` | `handler()`        |
| one positional parameter     | `handler(context)` |
| cannot be inspected          | `handler(context)` |

The check is done once at registration (like `_accepted_keywords` today) and replaces it. It
counts parameters, with no key matching and no `**kwargs`/`partial` special cases for keys. A
`functools.partial` that binds the first argument is handled by `inspect.signature` (the bound
argument is not counted).

Two ways to express the choice; the first follows the request:

- **A. Inferred from the signature** (recommended): no option; `filter_payload` is removed.
  Zero-argument handlers keep working without change, which is the common case in the README.
- **B. Explicit flag** `with_context: bool = False` keyword-only: no inspection at all, the
  registration never calls `inspect`, and the behaviour is visible at the registration site
  ("explicit over implicit" in `architecture.md`). The cost is one more option that every
  handler that reads the context must remember; forgetting it gives `handler()` and a `TypeError`
  on the missing argument, with the event and the handler in the note.

A and B can be combined (the flag overrides the inference) but that is two mechanisms again, so
this document does not propose it.

## 3. Comparison with the current design

| Aspect                                   | Current (`**payload`, `filter_payload`)                                           | Proposed (`Context`)                                                      |
| ---------------------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Handler signature                        | `def f(epoch, loss)`: self-documenting, checked by Python                         | `def f(context)`: the keys are read in the body                           |
| Handlers that need different subsets     | Needs `filter_payload=True` or `**kwargs` on each                                 | Natural: each handler reads what it needs, no option                      |
| Missing value                            | `TypeError` from Python, unless a default is in the signature                     | The handler chooses: `context["k"]` (`KeyError`), `get("k", d)`, `"k" in` |
| Extra value the handler ignores          | `TypeError` unless filtered                                                       | Always fine                                                               |
| Signature inspection                     | Key names, `**kwargs`, `partial`, uninspectable fallback (`_accepted_keywords`)   | Parameter count only (0 or 1)                                             |
| Options on the registration              | `once`, `condition`, `filter_payload`                                             | `once`, `condition` (A) or plus `with_context` (B)                        |
| Third-party or generic handlers          | Must match key names or use `**kwargs`                                            | One uniform shape, `handler(context)`                                     |
| Static typing of the keys                | Partial: a type checker sees `epoch: int` in the handler, not against the trigger | None: `context["epoch"]` is `object`; the handler must narrow or cast     |
| Sharing between handlers                 | Each handler gets its own `dict` of the same objects                              | One immutable `Context` shared; same objects, no way to rebind a key      |
| Future metadata (event name, trigger id) | Cannot be added without colliding with payload keys                               | Can be added as attributes of `Context`                                   |
| Public surface                           | 5 names                                                                           | 6 names (`Context`)                                                       |
| Error message for a missing key          | Python's, no list of available keys                                               | `KeyError` can list the available keys                                    |
| Cost                                     | Unpack `**payload` per handler                                                    | One `Context` per trigger; not measured                                   |

### Where the current design is better

- The signature **is** the documentation and the contract. `def log_epoch(epoch: int, loss: float)`
  is checked by `ty` at the definition and is readable without opening the body. A `Context`
  moves that contract into runtime lookups and loses the type of each value. This is the main
  cost and it has no cheap fix inside the zero-dependency, no-magic principles.
- Simple handlers (`def hello(name)`) get shorter code than `def hello(context)` followed by
  `context["name"]`.
- Existing handlers keep working.

### Where the proposal is better

- No `filter_payload`, no key matching, no `**kwargs` special case: the surface that surprises
  users (a handler silently receiving fewer keys than the trigger sends) disappears.
- The handler owns the missing-value policy, which matches the intent: the library routes, the
  handler decides.
- One shape for every handler, so a handler written for one event can be registered on another
  without re-checking the names of its parameters.

### Pros and cons of the proposal

#### Pros

- No `filter_payload` option and no key matching: a handler can no longer receive fewer keys than
  the trigger sends without the reader knowing why.
- About 35 lines of signature inspection (`_accepted_keywords`, its `**kwargs` and `partial` special
  cases) shrink to a parameter count (option A) or disappear (option B).
- The handler owns the missing-value policy (`[]`, `get`, `in`), as requested; the library only
  routes.
- Extra keys never break a handler, so adding a key to a trigger is not a breaking change for the
  existing handlers.
- One uniform handler shape: generic and third-party handlers need no knowledge of the key names of
  each trigger.
- Immutable and shared: a handler cannot change what the next handler sees.
- Room to grow: metadata (`context.event`) can be added without colliding with payload keys.
- A `KeyError` from the context can list the available keys, which is a better message than
  Python's `missing required argument`.

#### Cons

- The typed, self-documenting signature is lost: `def f(epoch: int)` becomes `context["epoch"]`,
  typed as `object`, and a typo in a key is found at run time, not by `ty`.
- More boilerplate for the simple handlers (one lookup line per value).
- Breaking change for every handler that takes a payload key, and for `filter_payload` users.
  Zero-argument handlers are unaffected.
- One more public name (`Context`) to document, test and keep stable.
- A required key that is missing fails inside the handler body (a `KeyError` with the event and
  handler note) instead of at the call boundary, so the failure is further from its cause.
- Option A infers behaviour from the signature (implicit), and an uninspectable callable gets a
  context it may not accept. Option B avoids this by adding an option.
- The cost of building one `Context` per trigger was not measured.

## 4. Behaviour changes and migration [proposal]

This is a breaking change of the handler contract. The README says the API is unstable before 1.0
and `CHANGELOG.md` already has a migration section, so it fits that section.

| Before                                           | After                                                         |
| ------------------------------------------------ | ------------------------------------------------------------- |
| `def f(): ...`                                   | unchanged                                                     |
| `def f(epoch): ...`                              | `def f(context): epoch = context["epoch"]`                    |
| `add_event_handler("e", f, filter_payload=True)` | `add_event_handler("e", f)` with `f(context)`                 |
| `def f(**kwargs): ...`                           | `def f(context): ...` (`dict(context)` gives the old kwargs)  |
| `functools.partial(f, "a", k=1)`                 | unchanged (the partial must still accept zero or one context) |

A bridge for the migration, if wanted: `lambda context: f(**context)` registers an old handler
unchanged. No built-in adapter is proposed (a second way to register would keep the old design
alive).

## 5. Open points

1. **`Mapping` subclass or minimal class** (2.1). Recommended: subclass.
2. **A or B** for the "needs the context" check (2.3). Recommended: A, because the request is to
   keep the check light and zero-argument handlers stay valid.
3. **Uninspectable callables** receive the context (as they receive the whole payload today). A
   C callable that takes no argument would then fail with a `TypeError` carrying the event and the
   handler note. B removes this case.
4. **Conditions** (`PeriodicCondition`, `AfterNCondition`) still take no argument. Passing the
   context to a condition is a natural next step (a condition on `context["epoch"]`) but is out of
   scope here.
5. **Non-`str` keys.** Kwargs force `str` keys today. `Context` should keep that rule
   (`TypeError` otherwise) so that `dict(context)` stays a valid `**kwargs` bridge.

## 6. Recommendation

Adopt the `Context` as a **replacement** of the payload keywords and of `filter_payload`, with
option A, **if** handlers are expected to be generic or to differ in what they read, which is the
case that motivated the review. Keep the current design if the main use is small handlers whose
typed signature is the point: there the context adds a lookup and loses the types for little gain.
Mixing both (keyword payload plus an optional context) is not recommended: it keeps
`_accepted_keywords` and adds a second contract.

## 7. Implementation plan (stacked PRs, each small)

1. Add `Context` with its tests and docstrings (`src/minevent/context.py`), export it.
2. Pass the `Context` to the handlers and replace the payload filter by the parameter-count check;
   remove `filter_payload`, `_accepted_keywords` and their tests.
3. Update the README, `docs/docs/*.md`, `architecture.md` (property P1 surface count) and the
   `CHANGELOG.md` migration section, with the PR numbers.
4. Add an integration test: several handlers of one event reading different keys, one missing
   key with `get` and with `[]`, across threads and with `atrigger_event`.
