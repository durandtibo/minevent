"""Basic usage example of minevent.

This example demonstrates the fundamental concepts of minevent:
- Creating an event manager
- Adding event handlers
- Triggering events
"""

from minevent import EventHandler, EventManager


def hello_handler() -> None:
    """Simple handler that prints a greeting."""
    print("Hello from event handler!")


def goodbye_handler() -> None:
    """Simple handler that prints a farewell."""
    print("Goodbye from event handler!")


def parameterized_handler(name: str, count: int = 1) -> None:
    """Handler that accepts parameters."""
    for i in range(count):
        print(f"  {i + 1}. Hello, {name}!")


def main() -> None:
    """Run the basic usage example."""
    print("=== Basic minevent Usage ===\n")

    # Create an event manager
    print("1. Creating event manager...")
    manager = EventManager()
    print(f"Manager created: {manager}\n")

    # Add simple event handlers
    print("2. Adding event handlers...")
    manager.add_event_handler("greeting", EventHandler(hello_handler))
    manager.add_event_handler("farewell", EventHandler(goodbye_handler))
    print("Handlers added.\n")

    # Trigger events
    print("3. Triggering 'greeting' event:")
    manager.trigger_event("greeting")
    print()

    print("4. Triggering 'farewell' event:")
    manager.trigger_event("farewell")
    print()

    # Add handler with arguments
    print("5. Adding handler with arguments...")
    manager.add_event_handler(
        "personalized_greeting",
        EventHandler(
            parameterized_handler,
            handler_args=("Alice",),
            handler_kwargs={"count": 3},
        ),
    )
    print()

    print("6. Triggering 'personalized_greeting' event:")
    manager.trigger_event("personalized_greeting")
    print()

    # Multiple handlers for same event
    print("7. Adding multiple handlers to same event...")
    manager.add_event_handler("multi_event", EventHandler(hello_handler))
    manager.add_event_handler("multi_event", EventHandler(goodbye_handler))
    print()

    print("8. Triggering 'multi_event' (executes all handlers in order):")
    manager.trigger_event("multi_event")
    print()

    # Check last triggered event
    print(f"9. Last triggered event: {manager.last_triggered_event}\n")

    # Check if handler exists
    print("10. Checking if handler exists...")
    exists = manager.has_event_handler(EventHandler(hello_handler), "greeting")
    print(f"hello_handler is registered for 'greeting': {exists}\n")

    # Remove a handler
    print("11. Removing hello_handler from 'greeting' event...")
    manager.remove_event_handler("greeting", EventHandler(hello_handler))
    print()

    print("12. Triggering 'greeting' after removal (should do nothing):")
    manager.trigger_event("greeting")
    print("(No output - handler was removed)\n")

    # Reset manager
    print("13. Resetting event manager...")
    manager.reset()
    print(f"Manager after reset: {manager}\n")

    print("=== Example Complete ===")


if __name__ == "__main__":
    main()
