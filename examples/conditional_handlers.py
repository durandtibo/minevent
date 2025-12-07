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

    # Shared state to track current step
    state = {"step": 0}

    # Handler that executes every time
    print("1. Setting up handlers:")

    def step_logger() -> None:
        print(f"Step {state['step']} complete")

    manager.add_event_handler(
        "step_complete",
        EventHandler(step_logger),
    )

    # Handler that executes every 5 steps
    print("   - Checkpoint: every 5 steps")

    def checkpoint_wrapper() -> None:
        checkpoint_handler(state["step"])

    manager.add_event_handler(
        "step_complete",
        ConditionalEventHandler(checkpoint_wrapper, PeriodicCondition(freq=5)),
    )

    # Handler that executes every 10 steps
    print("   - Validation: every 10 steps")

    def validation_wrapper() -> None:
        validation_handler(state["step"])

    manager.add_event_handler(
        "step_complete",
        ConditionalEventHandler(validation_wrapper, PeriodicCondition(freq=10)),
    )

    # Handler that executes every 2 steps
    print("   - Logging: every 2 steps")

    def log_wrapper() -> None:
        log_handler(state["step"])

    manager.add_event_handler(
        "step_complete",
        ConditionalEventHandler(log_wrapper, PeriodicCondition(freq=2)),
    )

    print("\n2. Simulating 15 training steps:\n")

    # Simulate training loop
    for step in range(1, 16):
        state["step"] = step
        print(f"Step {step}:")
        manager.trigger_event("step_complete")
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
