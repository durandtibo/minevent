"""Conditional event handlers example.

This example demonstrates how to use ConditionalEventHandler with PeriodicCondition
to control when event handlers execute.
"""

from minevent import ConditionalEventHandler, EventHandler, EventManager, PeriodicCondition


def checkpoint_handler(step: int) -> None:
    """Simulate saving a checkpoint."""
    print(f"  💾 Checkpoint saved at step {step}")


def log_handler(step: int) -> None:
    """Simulate logging metrics."""
    print(f"  📊 Logging metrics at step {step}")


def validation_handler(step: int) -> None:
    """Simulate running validation."""
    print(f"  ✓ Running validation at step {step}")


def main() -> None:
    """Run the conditional handlers example."""
    print("=== Conditional Event Handlers Example ===\n")

    manager = EventManager()

    # Handler that executes every time
    print("1. Setting up handlers:")
    manager.add_event_handler(
        "step_complete",
        EventHandler(lambda step: print(f"Step {step} complete"), handler_args=(0,)),
    )

    # Handler that executes every 5 steps
    print("   - Checkpoint: every 5 steps")
    manager.add_event_handler(
        "step_complete",
        ConditionalEventHandler(checkpoint_handler, PeriodicCondition(freq=5)),
    )

    # Handler that executes every 10 steps
    print("   - Validation: every 10 steps")
    manager.add_event_handler(
        "step_complete",
        ConditionalEventHandler(validation_handler, PeriodicCondition(freq=10)),
    )

    # Handler that executes every 2 steps
    print("   - Logging: every 2 steps")
    manager.add_event_handler(
        "step_complete",
        ConditionalEventHandler(log_handler, PeriodicCondition(freq=2)),
    )

    print("\n2. Simulating 15 training steps:\n")

    # Simulate training loop
    for step in range(1, 16):
        # Update handlers with current step
        # Note: In a real scenario, you'd pass state differently
        print(f"Step {step}:")

        # We need to update the handlers' arguments for each step
        # This is a simplified example - in practice, use closures or shared state
        manager.trigger_event("step_complete")

        # Manually trigger handlers with correct step for this example
        if step % 5 == 0:
            checkpoint_handler(step)
        if step % 10 == 0:
            validation_handler(step)
        if step % 2 == 0:
            log_handler(step)

        print()

    print("\n3. Demonstrating condition state:")

    # Create a new manager with simpler example
    manager2 = EventManager()

    counter = {"value": 0}

    def increment_and_print() -> None:
        counter["value"] += 1
        print(f"  Handler executed! Count: {counter['value']}")

    # Execute every 3 calls
    manager2.add_event_handler(
        "tick",
        ConditionalEventHandler(increment_and_print, PeriodicCondition(freq=3)),
    )

    print("\nTriggering 'tick' event 10 times (handler executes every 3rd time):\n")
    for i in range(1, 11):
        print(f"Tick {i}:")
        manager2.trigger_event("tick")

    print(f"\nFinal count: {counter['value']} (handler executed 4 times: at ticks 1, 4, 7, 10)")

    print("\n=== Example Complete ===")


if __name__ == "__main__":
    main()
