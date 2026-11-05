# Frequently Asked Questions (FAQ)

The answers are short; the [user guide](guide.md) has the details and the
[quickstart](quickstart.md) the runnable examples.

## General

### What is minevent?

`minevent` is a minimal event system for Python, designed for Machine Learning workflows. You
register event handlers, and they run when an event is triggered, so you can add logging, monitoring
or checkpointing to a training loop without changing it.

### How is minevent different from other event systems?

It is minimal: events are strings, `trigger_event` is synchronous (`atrigger_event` awaits coroutine
handlers), handlers run in the registration order, and it has no dependency.

### What Python versions are supported?

Python 3.11 and above. Install it with `pip install minevent`; see [Get Started](get_started.md).

### Can I use it with PyTorch, TensorFlow or scikit-learn?

Yes. `minevent` does not depend on any ML framework.

## Usage

### How do I pass data to the handlers?

As keyword arguments of `trigger_event`: `manager.trigger_event("epoch_end", epoch=3)`. See
[the payload](guide.md#pass-the-data-as-a-payload). Use `handler_args` and `handler_kwargs` for the
arguments that are fixed at registration.

### How do I run a handler only sometimes?

Give the `EventHandler` a condition, for example `condition=PeriodicCondition(freq=5)`, or any
function that returns a boolean. See [conditions](guide.md#conditions).

### How do I run a handler only once?

`manager.add_event_handler("my_event", handler, once=True)`.

### How do I remove a handler?

Call `remove()` on the `Subscription` returned by `add_event_handler`. See
[subscriptions](guide.md#keep-the-subscription).

### How do I know if a handler is registered?

`subscription.active`, or look at `manager.get_subscriptions("my_event")`. Event handlers are
compared by identity.

### What happens if I trigger an event with no handler?

Nothing.

### In which order do the handlers run?

In the order they were registered. A handler added or removed by a running handler takes effect at
the next trigger.

### What happens if a handler raises?

The exception propagates to the caller of `trigger_event`, with a note that names the event and the
handler, and the next handlers are skipped.

### Can I use coroutine handlers?

Yes, with `await manager.atrigger_event(...)`. `trigger_event` raises a `TypeError` for a coroutine
handler.

### Is it thread-safe?

The registry is: you can register handlers in one thread and trigger events from others. The
handlers run in the triggering thread, concurrently if several threads trigger the same event, and
the counter of a stateful condition is not protected. See
[Thread Safety](architecture.md#thread-safety).

### Can I create custom handlers and conditions?

Yes. A handler is a `BaseEventHandler` subclass with a `handle(self, /, **payload)` method. A
condition is any function without argument that returns a boolean, or a class with `__call__`.

### What is the overhead?

About 0.5 µs per trigger with one trivial handler. See [performance](guide.md#performance).

## Help

### Where can I report a bug or ask for a feature?

On the [GitHub issue tracker](https://github.com/durandtibo/minevent/issues).

### How can I contribute?

See the [contributing guide](https://github.com/durandtibo/minevent/blob/main/CONTRIBUTING.md).
