# User guide

This guide collects the recommendations and the troubleshooting tips for using `minevent`. The
[quickstart](quickstart.md) shows the basics, the [examples](examples.md) are the recipes, the
[how it works page](architecture.md) states the rules and the limits of the library and the
[design choices page](design.md) explains them.

## Recommendations

### Events

- Name the event after what happens: `epoch_end`, `checkpoint_saved`, not `event1` or `done`.
- Pick one convention for the whole project, for example `snake_case` (`batch_end`) or a namespace
  (`training.batch.end`). Names are only strings, so `minevent` has no notion of hierarchy.
- Define the names in one place (constants or a `StrEnum`) to avoid typos: the events
  `"epoch_end"` and `"epoch-end"` are different, and triggering an event without handler does
  nothing. A member of a plain `Enum` is not a `str`, so it is rejected (see
  [Name the events in one place](examples.md#name-the-events-in-one-place)).

### Handlers and payload

- One handler does one thing (log, save, update a progress bar). Register the handlers of an event
  in the order they must run.
- Pass the data of a trigger as a dict. Build a `Context` yourself to reuse it for several triggers:
  it is validated and copied only once.
- Read a required value with `context["key"]` and an optional one with `context.get(key, default)`,
  so that handlers with different needs can share an event.
- Write `def f(_)` for a handler that ignores the context, and wrap an existing function in a lambda
  such as `lambda _: model.train()` (see [the calling rule](architecture.md#the-calling-rule)).
- If the failure of a handler must not stop the program,
  [catch the exception in the handler](examples.md#continue-after-a-handler-fails).
- A synchronous handler that is slow blocks the caller (and the event loop in `atrigger_event`).
  Hand the work to an executor in the handler if the caller must not wait, and
  [return nothing](examples.md#start-background-work-from-a-handler).

### Conditions

- Give each registration its own `PeriodicCondition`: an instance shared by two handlers advances
  the same counter. Call `reset()` to restart it.
- For a warm-up, use `PeriodicCondition(freq=1, start=n)`: it is `False` for the first `n` calls,
  then `True`.
- To combine conditions, write a function. `lambda context: a(context) and b(context)` skips `b` when
  `a` is `False`, so use it when `b` is costly and stateless.
  `lambda context: all([a(context), b(context)])` evaluates both, so stateful conditions advance
  together.
- Use a condition to avoid the work of an expensive handler.

### The event manager

- Create the manager once and pass it where it is needed. `minevent` has no global manager (see
  [the design choice](design.md#the-manager-is-an-explicit-object)).
- Keep the `Subscription` of a handler that you may remove. A registered handler lives as long as
  the manager (`obj.method` keeps `obj` alive, and so do the arguments of a `functools.partial` and
  the closures), and `minevent` uses no weak reference. Remove the subscriptions that you do not
  need any more with `remove()`, a `with` block, `clear_event` or `reset`.

### Tests

- Test a handler without a manager, and the wiring with `create_autospec` (see
  [Test a handler](examples.md#test-a-handler)).
- Use a new `EventManager` in each test, or call `manager.reset()` if the manager is shared.

### Performance

The cost of a trigger is mostly the cost of the handlers (see
[Performance](architecture.md#performance)). To find a slow handler, time it or wrap it (see
[Trace the handlers](examples.md#trace-the-handlers)). In a loop that triggers often with the same
data, build one `Context` and reuse it.

## Troubleshooting

### My handler does not run

1. The handler is registered for that event: `print(manager.get_subscriptions("my_event"))` lists
   the registrations of the event, with `once=True` and `condition='...'` for the ones that have
   these options.
2. The event name matches exactly (case-sensitive).
3. The condition returns `True` (a `PeriodicCondition(freq=5)` skips four calls out of five).
4. The registration was not removed, for example consumed by `once=True` or removed by its own
   condition: the `repr` of a removed `Subscription` that you kept shows `active=False`.
5. A handler of the same event ahead of it raised: the next handlers are skipped.

### `KeyError: "key 'epoch' not found in the context; ..."`

The trigger did not give the key that the handler requires. The message lists the available keys.
Give the key to the trigger, or read it as an optional value.

### `TypeError: context must be a mapping or None` and `the keys of data must be str`

The data of a trigger is a mapping with `str` keys, such as a dict, given as the second argument:
`manager.trigger_event("epoch_end", {"epoch": 1})`.

### `TypeError` about unexpected or positional-only arguments of `trigger_event`

`trigger_event` and `atrigger_event` take the event and the context as positional arguments only.
Neither `trigger_event("epoch_end", epoch=1)` nor `trigger_event("epoch_end", context=data)` is
valid: write `trigger_event("epoch_end", {"epoch": 1})`.

### `TypeError: event must be a str`

An event is a `str`, for example a `StrEnum` member. A member of a plain `Enum` is not.

### `TypeError: once must be a bool`

`once` is `True` or `False`. A value that is only truthy or falsy, such as `1` or the string
`"False"`, is rejected: convert it first.

### `TypeError: EventManager cannot be copied or pickled` and `Subscription cannot be ...`

A manager or a subscription, or an object that holds one, was copied or sent to another process.
Create a new manager there and register the handlers, or
[exclude the manager and the subscriptions](examples.md#copy-an-object-that-holds-a-manager) from the
state of the object.

### `TypeError: handler must be callable` and `condition must be callable`

The value given is not a function. A frequent cause is a call at registration:
`add_event_handler("epoch_end", save())` gives the result of `save`. Pass the function itself, or
wrap the call in a lambda: `lambda _: save()`.

### `TypeError: unhashable type: 'Context'`

The handler or the condition is cached with `functools.cache` or `functools.lru_cache`, which hash
their arguments (see [the limits](architecture.md#handlers-and-conditions)). Register a function that
reads the values that it needs from the context, and passes them to the cached function.

### `TypeError: ... must take the context as its only required argument`

The manager cannot call the handler or the condition as `f(context)`, for example a function without
parameter, or `def f(context=None)`. Give it one parameter without default, wrap it in a function or
a lambda, or bind the extra arguments with `functools.partial` (see
[the calling rule](architecture.md#the-calling-rule)).

### `TypeError: ... must not be a generator function`

Calling a function with `yield`, or an object whose `__call__` has one, runs none of its code.
Register a function that iterates over the generator.

### `TypeError: condition must be synchronous` and `condition ... returned an awaitable`

The condition is asynchronous: a coroutine function, or an object with `async def __call__`, is
rejected at registration, and a condition that returns an awaitable another way (a lambda that
returns a coroutine) fails at the trigger. Compute the value before the trigger and pass it in the
payload, or decide inside a coroutine handler.

### `TypeError: ... is a coroutine function; use atrigger_event` and `... returned an awaitable`

A coroutine handler was triggered with `trigger_event`. Call
`await manager.atrigger_event(...)`. For a coroutine function, nothing ran. A handler that returns
an awaitable another way (a lambda that returns a coroutine) fails after its call, so the handlers
before it have run.

A handler that starts a background task must not return it: see
[Start background work from a handler](examples.md#start-background-work-from-a-handler).

### `subscription.remove()` returns `False`

The registration is already removed. This is not an error.

### Debug

`minevent` does not log. `print(manager)` shows the number of handlers of each event, and
`manager.get_subscriptions(event)` lists the registrations of an event with the name of each handler
and its options.
To see the calls and the payload, [trace the handlers](examples.md#trace-the-handlers).
