"""Machine Learning training logger example.

This example demonstrates how to use minevent to add logging capabilities
to a machine learning training loop without modifying the core training logic.
"""

import random

from minevent import ConditionalEventHandler, EventHandler, EventManager, PeriodicCondition


class Trainer:
    """Simple trainer class that uses events for extensibility."""

    def __init__(self, manager: EventManager) -> None:
        """Initialize trainer with an event manager.

        Args:
            manager: Event manager for triggering training events
        """
        self.manager = manager
        self.epoch = 0
        self.best_loss = float("inf")

    def train(self, num_epochs: int) -> None:
        """Run training for specified number of epochs.

        Args:
            num_epochs: Number of training epochs
        """
        self.manager.trigger_event("training_start")

        for self.epoch in range(1, num_epochs + 1):
            self.manager.trigger_event("epoch_start")

            # Simulate training
            train_loss = self._train_epoch()

            # Simulate validation
            val_loss = self._validate()

            # Store metrics for handlers to access
            self.current_metrics = {
                "epoch": self.epoch,
                "train_loss": train_loss,
                "val_loss": val_loss,
            }

            # Update best loss
            if val_loss < self.best_loss:
                self.best_loss = val_loss
                self.manager.trigger_event("new_best_model")

            self.manager.trigger_event("epoch_end")

        self.manager.trigger_event("training_end")

    def _train_epoch(self) -> float:
        """Simulate training for one epoch."""
        # Simulate decreasing loss
        return max(0.1, 2.0 / self.epoch + random.uniform(-0.1, 0.1))

    def _validate(self) -> float:
        """Simulate validation."""
        # Simulate decreasing validation loss
        return max(0.15, 2.2 / self.epoch + random.uniform(-0.15, 0.15))


# Event handler functions
def log_training_start() -> None:
    """Log when training starts."""
    print("🚀 Training started!")
    print("=" * 50)


def log_epoch_start(trainer: Trainer) -> None:
    """Log when epoch starts."""
    print(f"\nEpoch {trainer.epoch} started...")


def log_metrics(trainer: Trainer) -> None:
    """Log training metrics after each epoch."""
    metrics = trainer.current_metrics
    print(
        f"  Train Loss: {metrics['train_loss']:.4f} | "
        f"Val Loss: {metrics['val_loss']:.4f}"
    )


def log_best_model(trainer: Trainer) -> None:
    """Log when a new best model is found."""
    print(f"  ⭐ New best model! Val Loss: {trainer.best_loss:.4f}")


def log_checkpoint(trainer: Trainer) -> None:
    """Log checkpoint saving (periodic)."""
    print(f"  💾 Checkpoint saved at epoch {trainer.epoch}")


def log_training_end(trainer: Trainer) -> None:
    """Log when training completes."""
    print("\n" + "=" * 50)
    print("✅ Training completed!")
    print(f"Best validation loss: {trainer.best_loss:.4f}")


def main() -> None:
    """Run the ML training logger example."""
    print("=== Machine Learning Training Logger Example ===\n")

    # Create event manager
    manager = EventManager()

    # Create trainer
    trainer = Trainer(manager)

    # Setup event handlers for logging
    print("Setting up logging handlers...\n")

    # Log training lifecycle
    manager.add_event_handler("training_start", EventHandler(log_training_start))

    manager.add_event_handler(
        "epoch_start",
        EventHandler(log_epoch_start, handler_args=(trainer,)),
    )

    manager.add_event_handler(
        "epoch_end",
        EventHandler(log_metrics, handler_args=(trainer,)),
    )

    manager.add_event_handler(
        "new_best_model",
        EventHandler(log_best_model, handler_args=(trainer,)),
    )

    # Log checkpoints every 3 epochs
    manager.add_event_handler(
        "epoch_end",
        ConditionalEventHandler(
            log_checkpoint,
            PeriodicCondition(freq=3),
            handler_args=(trainer,),
        ),
    )

    manager.add_event_handler(
        "training_end",
        EventHandler(log_training_end, handler_args=(trainer,)),
    )

    # Run training
    trainer.train(num_epochs=10)

    print("\n=== Example Complete ===")
    print(
        "\nNote: The trainer class doesn't know anything about logging!"
        "\nAll logging is added through event handlers, making it easy to:"
        "\n  - Add/remove logging without changing trainer code"
        "\n  - Customize logging for different experiments"
        "\n  - Add other functionality (checkpointing, monitoring, etc.)"
    )


if __name__ == "__main__":
    main()
