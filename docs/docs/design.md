# Design Choices

This page explains why `minevent` works the way it does. For each choice, it gives what you gain,
what it costs and how to work with it, so you can decide if the library fits your program. The rules
themselves are on the [how it works page](architecture.md).

## Goals

The choices below serve four goals:

- **Stay small.** The library routes an event to the code that you attached to it, and does nothing
  else.
- **Be predictable.** You can tell which handlers run, in which order, from the registrations.
- **Report mistakes early, and never hide an error.** A long training should not discover a wrong
  handler after hours.
- **Fit any project.** No dependency, no global state and no base class to extend.

`minevent` fits a program that runs its steps in sequence in one process, such as a training or
evaluation loop, and wants to plug behavior into those steps. It is not a message queue, a signal
library with filtering, or a scheduler.

## Events and payload

### Events are strings

An event is a `str`, not an object.

- **Benefits**: nothing to declare or import to emit an event, names are easy to read, log and
  serialize, and any part of a program can agree on a name.
- **Costs**: a typo is silent, because triggering an event without handler is valid. There is no
  hierarchy or wildcard: `training.batch.end` is only a naming convention, and the data of an event
  goes in the payload, not in the event.
- **In practice**: see the [recommendations about events](guide.md#events).

### The payload is one read-only Context

The data of a trigger is passed as one `Context`, not as keyword arguments.

- **Benefits**: handlers of the same event can read different keys, adding a key to a trigger breaks
  no handler, each handler decides what a missing key means, and no handler can add, replace or
  remove a key seen by the next one.
- **Costs**: the signature of a handler does not list the data that it needs, a typo in a key is
  found at run time, and a dict is copied at each trigger. `Context` is final: it is data, so build
  one from your mapping, or wrap it, instead of subclassing it.
- **In practice**: see the [recommendations about the payload](guide.md#handlers-and-payload).

The protection is shallow: the values are not copied, because copying arbitrary objects (a model, a
tensor) is expensive or impossible. A mutable value can be changed by a handler; take a
[snapshot](examples.md#keep-a-snapshot-of-the-payload) if you need one.

### The values of a Context are typed Any

- **Benefits**: a handler computes with a value (`context["epoch"] + 1`) without a cast.
- **Costs**: a type checker does not check the keys or the use of the values.
- **In practice**: annotate the variable that receives a value (`epoch: int = context["epoch"]`), or
  check it at run time, if you need more safety.

## Handlers and conditions

### A handler is a plain callable

There is no base class or protocol to implement, and a condition is a function too.

- **Benefits**: any function, method, lambda, `functools.partial` or callable object that takes the
  context works (see [the calling rule](architecture.md#the-calling-rule)), and a handler can be
  tested without a manager. There is one way to extend the library: write a callable.
- **Costs**: the library cannot attach a name, a priority or metadata to a handler. A mistake in a
  signature is found at registration (or by your type checker), not by an interface.
- **In practice**: use a class with `__call__` when a handler
  [needs a state](examples.md#keep-a-state-in-a-handler).

### A handler is always called with the context

A handler and a condition are called as `f(context)`
([the calling rule](architecture.md#the-calling-rule)). The signature is checked once, at
registration.

- **Benefits**: there is one call to learn, and a context is always there. Adding or removing a
  default never changes the call, and a callable that cannot be called is rejected immediately,
  before a long training.
- **Costs**: a function that does not need the context declares it anyway, or is wrapped in a lambda,
  so `model.train` is not registered as it is. Callables that accept `*args` (`print`, `Mock()`) or
  cannot be inspected are rejected, even when a call would work.
- **In practice**: [adapt an existing function](examples.md#adapt-an-existing-function), and see the
  [recommendations about handlers](guide.md#handlers-and-payload).

### The result of a handler is ignored

A handler acts through its effects: a trigger gives nothing back to the code that called it.

- **Benefits**: the code that triggers an event does not depend on which handlers are registered,
  and there is no rule to combine the results of several handlers.
- **Costs**: a handler cannot answer the caller, for example to ask a training loop to stop.
- **In practice**: share an object, in the payload or in a
  [handler with a state](examples.md#keep-a-state-in-a-handler), and read it after the trigger, as in
  [stop a training early](examples.md#stop-a-training-early).

### Conditions are synchronous

A condition is a plain function, never a coroutine function.

- **Benefits**: a condition has the same meaning with `trigger_event` and `atrigger_event`, and a
  coroutine, which is truthy, cannot make a handler run by mistake.
- **Costs**: a decision that needs I/O cannot be a condition.
- **In practice**: see the
  [troubleshooting of asynchronous conditions](guide.md#typeerror-condition-must-be-synchronous-and-condition-returned-an-awaitable).

### A periodic condition counts its calls

`PeriodicCondition` keeps its own counter, and does not read a step from the payload.

- **Benefits**: it works with any event, without a naming convention for the keys of the payload.
- **Costs**: it has a state, so one instance serves one registration, and its count is not your epoch:
  it does not advance when it is not called, and a new process starts from 0.
- **In practice**: [decide from the payload](examples.md#decide-from-the-payload), or save the
  condition to [resume a training](examples.md#resume-a-training).

## Registrations

### A registration is an object

`add_event_handler` returns a `Subscription`, and there is no method that removes a handler by
comparing callables.

- **Benefits**: the same callable can be registered several times with different options, a removal
  is exact and O(1), including for lambdas and partials that you cannot compare, and a `with` block
  scopes a registration.
- **Costs**: you must keep the `Subscription` if you want to remove it later, and an object that
  holds one cannot be copied or pickled as it is: a copy would describe a registration that does not
  exist.
- **In practice**: otherwise, search the result of `get_subscriptions(event)` for your handler.

### `once` is claimed before the call

A `once` registration is removed after its condition and just before its handler.

- **Benefits**: the handler runs at most once, even with several threads, and a false condition
  keeps the registration for a later trigger.
- **Costs**: a handler that raises is not retried.
- **In practice**: for a retry,
  [remove the handler after it succeeds](examples.md#remove-a-handler-after-it-succeeds).

## Dispatch

### Handlers run one after the other

A trigger is sequential. Coroutines are opt-in with `atrigger_event`, which awaits them one at a
time, and the library starts no thread.

- **Benefits**: the order is deterministic, a handler can rely on the work of the previous one, which
  suits the sequential workflows of Machine Learning, and it is easy to debug.
- **Costs**: a slow handler delays the next ones and the caller, handlers do not run concurrently,
  and a synchronous handler blocks the event loop.
- **In practice**:
  [run the work of a handler concurrently](examples.md#run-the-work-of-a-handler-concurrently) inside
  one handler.

### A trigger works on a snapshot

The registrations are read when the trigger starts. An addition waits for the next trigger, while a
removal applies immediately.

- **Benefits**: a handler can add or remove handlers without changing the list that is being
  visited, and a handler that registers another one cannot loop forever. A removed handler does not
  run any more, even if its own condition removed it.
- **Costs**: a handler cannot extend the current dispatch.
- **In practice**: [trigger another event](examples.md#trigger-an-event-from-a-handler) if some work
  must happen immediately.

### A trigger stops at the first error

An exception of a handler or a condition reaches the caller unchanged, with a note, and the next
handlers are skipped.

- **Benefits**: errors are never hidden, the traceback and the type of the exception are the ones of
  your code, and the dispatch has no error policy to configure.
- **Costs**: one failing handler prevents the next ones from running, and there is no option to
  collect the errors into an `ExceptionGroup`.
- **In practice**:
  [catch in the handler](examples.md#continue-after-a-handler-fails) the errors that must not stop
  the program.

### A synchronous trigger rejects coroutine handlers first

`trigger_event` looks for a coroutine function among the handlers before it runs anything.

- **Benefits**: a trigger does not stop in the middle, no `once` registration is consumed, and the
  mistake appears at the first trigger, not at the first one where a condition is true.
- **Costs**: one more pass over the handlers at each trigger, and a coroutine handler whose
  condition is false rejects the trigger too.
- **In practice**: see the
  [troubleshooting of coroutine handlers](guide.md#typeerror-is-a-coroutine-function-use-atrigger_event-and-returned-an-awaitable).

## The manager

### The manager is an explicit object

There is no global manager and no automatic discovery. A manager is always truthy, it has no length,
and it cannot be copied or pickled.

- **Benefits**: the ownership is visible, tests do not share state, and `manager or default` means
  "is there a manager". A copy that silently shares or loses registrations cannot happen.
- **Costs**: you pass the manager to the code that triggers events, and an object that holds a
  manager needs its own rule to be pickled, for example to be sent to another process.
- **In practice**: see the
  [troubleshooting of copies](guide.md#typeerror-eventmanager-cannot-be-copied-or-pickled-and-subscription-cannot-be).

### The manager is thread-safe, your code is not

A reentrant lock protects the registry only. A trigger takes its snapshot under the lock and calls
your code outside of it.

- **Benefits**: your code can use the manager, a slow handler does not block the registrations of
  other threads, and a lock of yours cannot deadlock with the one of the manager.
- **Costs**: handlers can run concurrently, and a removal in one thread cannot stop a call that
  another thread is about to make.
- **In practice**: protect the shared state of your handlers and conditions. `PeriodicCondition`
  protects its counter.

### The manager keeps strong references

A registered handler stays alive until its registration is removed.

- **Benefits**: a registered lambda or bound method cannot disappear unexpectedly.
- **Costs**: an object stays alive while one of its methods is registered.
- **In practice**: see the [recommendations about the manager](guide.md#the-event-manager).

### Nothing is logged

The library writes no log and no output.

- **Benefits**: no configuration, no output that you did not ask for, and no cost on a trigger.
- **Costs**: to see which handlers ran, you add the trace yourself.
- **In practice**: see [how to debug](guide.md#debug).

## What is not provided

`minevent` depends on the standard library only, so it can be added to any project without a version
conflict. It also leaves out features that other event libraries have:

| Not provided                              | What to do instead                                                                               |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Event objects with metadata               | Pass the data in the payload.                                                                    |
| Priorities or ordering rules              | Register the handlers in the order they must run.                                                |
| Hierarchy or wildcards of events          | [Register the handler to each event](examples.md#register-a-handler-to-several-events).          |
| Weak references, filtering by sender      | Remove the subscriptions; filter with a condition.                                               |
| Collecting the errors of several handlers | [Catch the exceptions in the handlers](examples.md#continue-after-a-handler-fails).              |
| Concurrent or background dispatch         | [Start the tasks or threads inside a handler](examples.md#start-background-work-from-a-handler). |
