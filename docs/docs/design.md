# Design Choices

`minevent` is built to stay small: it routes an event to the code that you attached to it, in a
predictable order, and does nothing else. This page explains the main choices, what they give you
and what they cost, so you can decide if they fit your program and work with them. The rules
themselves are on the [how it works page](architecture.md).

## Events are strings

An event is a `str`, not an object.

- **Benefits**: nothing to declare or import to emit an event, names are easy to read, log and
  serialize, and any part of a program can agree on a name.
- **Costs**: a typo is silent, because triggering an event without handler is valid. There is no
  hierarchy or wildcard: `training.batch.end` is only a naming convention, and the data of an event
  goes in the payload, not in the event.
- **In practice**: define the names once, as constants or a `StrEnum`.

## A handler is a plain callable

There is no base class or protocol to implement, and a condition is a function too.

- **Benefits**: any function, method, lambda, `functools.partial` or callable object works, and a
  handler can be tested without a manager. There is one way to extend the library: write a callable.
- **Costs**: the library cannot attach a name, a priority or metadata to a handler. A mistake in a
  signature is found at registration (or by your type checker), not by an interface.
- **In practice**: use a class with `__call__` when a handler needs a state.

## The signature decides how a handler is called

A handler is called as `f()` or `f(context)`, according to the parameters that have no default
([the calling rule](architecture.md#the-calling-rule)). The signature is read once, at
registration.

- **Benefits**: a handler declares only what it needs, with no option to repeat at each
  registration, and functions with default arguments, such as `model.train(mode=True)`, are
  registered as they are. A callable that cannot be called is rejected immediately.
- **Costs**: the behavior is implicit. An optional parameter such as `context=None` never receives
  the context, and callables that accept `*args` (`print`, `Mock()`) or cannot be inspected are
  rejected, even when a call would work.
- **In practice**: wrap such a callable in a lambda or a function, which states how it is called.

## The payload is one read-only Context

The data of a trigger is passed as one `Context`, not as keyword arguments.

- **Benefits**: handlers of the same event can read different keys, adding a key to a trigger breaks
  no handler, each handler decides what a missing key means, and no handler can add, replace or
  remove a key seen by the next one.
- **Costs**: the signature of a handler does not list the data that it needs, a typo in a key is
  found at run time, and a dict is copied at each trigger.
- **In practice**: read a required value with `context["key"]` and an optional one with
  `context.get("key", default)`. Build a `Context` once to reuse it. To give named arguments to an
  existing function, adapt it: `lambda context: f(context["epoch"])`.

The protection is shallow: the values are not copied, because copying arbitrary objects (a model, a
tensor) is expensive or impossible. A mutable value can be changed by a handler; take a
`copy.deepcopy` if you need a snapshot.

## The values of a Context are typed Any

- **Benefits**: a handler computes with a value (`context["epoch"] + 1`) without a cast.
- **Costs**: a type checker does not check the keys or the use of the values.
- **In practice**: annotate the variable that receives a value (`epoch: int = context["epoch"]`), or
  check it at run time, if you need more safety.

## A registration is an object

`add_event_handler` returns a `Subscription`, and there is no method that removes a handler by
comparing callables.

- **Benefits**: the same callable can be registered several times with different options, a removal
  is exact and O(1), including for lambdas and partials that you cannot compare, and a `with` block
  scopes a registration.
- **Costs**: you must keep the `Subscription` if you want to remove it later, and an object that
  holds one cannot be copied or pickled as it is: a copy would describe a registration that does not
  exist.
- **In practice**: otherwise, search the result of `get_subscriptions(event)` for your handler.

## A trigger works on a snapshot

The registrations are read when the trigger starts. An addition waits for the next trigger, while a
removal applies immediately.

- **Benefits**: a handler can add or remove handlers without changing the list that is being
  visited, and a handler that registers another one cannot loop forever. A removed handler does not
  run any more, even if its own condition removed it.
- **Costs**: a handler cannot extend the current dispatch.
- **In practice**: trigger another event if some work must happen immediately.

## A trigger stops at the first error

An exception of a handler or a condition reaches the caller unchanged, with a note, and the next
handlers are skipped.

- **Benefits**: errors are never hidden, the traceback and the type of the exception are the ones of
  your code, and the dispatch has no error policy to configure.
- **Costs**: one failing handler prevents the next ones from running, and there is no option to
  collect the errors into an `ExceptionGroup`.
- **In practice**: if a handler must not stop the others, catch its exceptions inside it, or wrap it
  in a function that does.

## Handlers run one after the other

A trigger is synchronous and sequential. Coroutines are opt-in with `atrigger_event`, which awaits
them one at a time, and the library starts no thread.

- **Benefits**: the order is deterministic, a handler can rely on the work of the previous one, which
  suits the sequential workflows of Machine Learning, and it is easy to debug.
- **Costs**: a slow handler delays the next ones and the caller, handlers do not run concurrently,
  and a synchronous handler blocks the event loop.
- **In practice**: inside one handler, use `asyncio.gather`, `asyncio.to_thread` or an executor.

## A synchronous trigger rejects coroutine handlers first

`trigger_event` looks for a coroutine function among the handlers before it runs anything.

- **Benefits**: a trigger does not stop in the middle, no `once` registration is consumed, and the
  mistake appears at the first trigger, not at the first one where a condition is true.
- **Costs**: one more pass over the handlers at each trigger, and a coroutine handler whose
  condition is false rejects the trigger too.
- **In practice**: trigger an event that has coroutine handlers with `atrigger_event`.

## Conditions are synchronous

- **Benefits**: a condition has the same meaning with `trigger_event` and `atrigger_event`, and a
  coroutine, which is truthy, cannot make a handler run by mistake.
- **Costs**: a decision that needs I/O cannot be a condition.
- **In practice**: compute the value before the trigger and pass it in the payload, or decide inside
  a coroutine handler.

## `once` is claimed before the call

A `once` registration is removed after its condition and just before its handler.

- **Benefits**: the handler runs at most once, even with several threads, and a false condition
  keeps the registration for a later trigger.
- **Costs**: a handler that raises is not retried.
- **In practice**: for a retry, register without `once` and call `subscription.remove()` after the
  success.

## The manager is thread-safe, your code is not

A reentrant lock protects the registry only. A trigger takes its snapshot under the lock and calls
your code outside of it.

- **Benefits**: your code can use the manager, a slow handler does not block the registrations of
  other threads, and a lock of yours cannot deadlock with the one of the manager.
- **Costs**: handlers can run concurrently, and a removal in one thread cannot stop a call that
  another thread is about to make.
- **In practice**: protect the shared state of your handlers and conditions. The built-in conditions
  protect their counter.

## The manager is an explicit object

There is no global manager and no automatic discovery. A manager is always truthy, and it cannot be
copied or pickled.

- **Benefits**: the ownership is visible, tests do not share state, and `manager or default` means
  "is there a manager". A copy that silently shares or loses registrations cannot happen.
- **Costs**: you pass the manager to the code that triggers events, and an object that holds a
  manager needs its own rule to be pickled, for example to be sent to another process.
- **In practice**: create a new manager in each process and register the handlers there.

## The manager keeps strong references

- **Benefits**: a registered lambda or bound method cannot disappear unexpectedly.
- **Costs**: an object stays alive while one of its methods is registered.
- **In practice**: remove the subscriptions that you do not need, with `remove()`, a `with` block,
  `clear_event` or `reset`.

## Nothing is logged

- **Benefits**: no configuration, no output that you did not ask for, and no cost on a trigger.
- **Costs**: to see which handlers ran, you add the trace yourself.
- **In practice**: look at `repr(manager)` and `get_subscriptions(event)`, or
  [trace the handlers](examples.md#trace-the-handlers).

## No dependency and a small surface

`minevent` depends on the standard library only, so it can be added to any project without a version
conflict. It also leaves out features that other event libraries have:

| Not provided                              | What to do instead                                 |
| ----------------------------------------- | -------------------------------------------------- |
| Event objects with metadata               | Pass the data in the payload.                      |
| Priorities or ordering rules              | Register the handlers in the order they must run.  |
| Hierarchy or wildcards of events          | Register the handler to each event.                |
| Weak references, filtering by sender      | Remove the subscriptions; filter with a condition. |
| Collecting the errors of several handlers | Catch the exceptions in the handlers.              |
| Concurrent or background dispatch         | Start the tasks or threads inside a handler.       |
