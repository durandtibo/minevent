"""Custom condition example.

This example demonstrates how to create and use custom conditions
for more sophisticated event handler control logic.
"""

from typing import Any

from minevent import ConditionalEventHandler, EventManager
from minevent.conditions import BaseCondition


class ThresholdCondition(BaseCondition):
    """Execute handler only when value exceeds threshold.

    This condition maintains internal state and evaluates based on
    values set via update_value().
    """

    def __init__(self, threshold: float) -> None:
        """Initialize threshold condition.

        Args:
            threshold: Minimum value required for condition to be True
        """
        self.threshold = threshold
        self.current_value = 0.0

    def update_value(self, value: float) -> None:
        """Update the current value for evaluation.

        Args:
            value: New value to compare against threshold
        """
        self.current_value = value

    def evaluate(self) -> bool:
        """Evaluate if current value exceeds threshold.

        Returns:
            True if current_value > threshold, False otherwise
        """
        return self.current_value > self.threshold

    def equal(self, other: Any) -> bool:
        """Check equality with another condition.

        Args:
            other: Object to compare with

        Returns:
            True if other is ThresholdCondition with same threshold
        """
        return isinstance(other, ThresholdCondition) and self.threshold == other.threshold


class AccuracyImprovementCondition(BaseCondition):
    """Execute handler only when accuracy improves.

    Tracks best accuracy seen so far and evaluates to True
    only when a new best is achieved.
    """

    def __init__(self) -> None:
        """Initialize accuracy improvement condition."""
        self.best_accuracy = 0.0
        self.current_accuracy = 0.0

    def update_accuracy(self, accuracy: float) -> None:
        """Update current accuracy.

        Args:
            accuracy: New accuracy value to check
        """
        self.current_accuracy = accuracy

    def evaluate(self) -> bool:
        """Check if current accuracy is better than best seen.

        Returns:
            True if current accuracy is new best, False otherwise
        """
        if self.current_accuracy > self.best_accuracy:
            self.best_accuracy = self.current_accuracy
            return True
        return False

    def equal(self, other: Any) -> bool:
        """Check equality with another condition.

        Args:
            other: Object to compare with

        Returns:
            True if other is same type of condition
        """
        return isinstance(other, AccuracyImprovementCondition)


class CountBasedCondition(BaseCondition):
    """Execute handler after N evaluations, then stop.

    Unlike PeriodicCondition which continues forever,
    this condition executes exactly once after N calls.
    """

    def __init__(self, trigger_after: int) -> None:
        """Initialize count-based condition.

        Args:
            trigger_after: Number of evaluations before triggering
        """
        self.trigger_after = trigger_after
        self.count = 0
        self.has_triggered = False

    def evaluate(self) -> bool:
        """Evaluate based on call count.

        Returns:
            True only on the trigger_after-th call, then False forever
        """
        if self.has_triggered:
            return False

        self.count += 1
        if self.count >= self.trigger_after:
            self.has_triggered = True
            return True
        return False

    def equal(self, other: Any) -> bool:
        """Check equality with another condition.

        Args:
            other: Object to compare with

        Returns:
            True if other is same type with same trigger_after
        """
        return (
            isinstance(other, CountBasedCondition)
            and self.trigger_after == other.trigger_after
        )


def main() -> None:
    """Run the custom condition examples."""
    print("=== Custom Condition Examples ===\n")

    # Example 1: ThresholdCondition
    print("1. ThresholdCondition Example")
    print("   (Handler executes when value > 0.8)\n")

    manager = EventManager()
    threshold_condition = ThresholdCondition(threshold=0.8)

    # Store current value in shared state
    current_value = {"value": 0.0}

    def alert_high_value() -> None:
        print(f"   🚨 Alert! High value detected: {current_value['value']:.2f}")

    manager.add_event_handler(
        "value_update",
        ConditionalEventHandler(
            alert_high_value,
            threshold_condition,
        ),
    )

    test_values = [0.5, 0.7, 0.85, 0.9, 0.6, 0.95]
    for value in test_values:
        current_value["value"] = value
        threshold_condition.update_value(value)
        print(f"   Value: {value:.2f}")
        manager.trigger_event("value_update")

    # Example 2: AccuracyImprovementCondition
    print("\n2. AccuracyImprovementCondition Example")
    print("   (Handler executes only when accuracy improves)\n")

    manager2 = EventManager()
    accuracy_condition = AccuracyImprovementCondition()

    # Store current accuracy in shared state
    current_accuracy = {"value": 0.0}

    def save_best_model() -> None:
        print(f"   💾 Saving new best model! Accuracy: {current_accuracy['value']:.3f}")

    manager2.add_event_handler(
        "validation_complete",
        ConditionalEventHandler(
            save_best_model,
            accuracy_condition,
        ),
    )

    test_accuracies = [0.750, 0.820, 0.810, 0.855, 0.840, 0.890, 0.875]
    for acc in test_accuracies:
        current_accuracy["value"] = acc
        accuracy_condition.update_accuracy(acc)
        print(f"   Validation accuracy: {acc:.3f}")
        manager2.trigger_event("validation_complete")

    # Example 3: CountBasedCondition
    print("\n3. CountBasedCondition Example")
    print("   (Handler executes exactly once after 5 calls)\n")

    manager3 = EventManager()
    count_condition = CountBasedCondition(trigger_after=5)

    def one_time_action() -> None:
        print("   ⚡ One-time action executed!")

    manager3.add_event_handler(
        "step",
        ConditionalEventHandler(one_time_action, count_condition),
    )

    print("   Triggering 'step' event 10 times:")
    for i in range(1, 11):
        print(f"   Step {i}:", end=" ")
        manager3.trigger_event("step")
        print()

    print("\n=== Example Complete ===")
    print(
        "\nKey Takeaways:"
        "\n  - Custom conditions give you full control over handler execution"
        "\n  - Conditions can maintain state between evaluations"
        "\n  - Multiple conditions can be combined for complex logic"
        "\n  - Conditions are reusable across different handlers"
    )


if __name__ == "__main__":
    main()
