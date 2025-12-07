"""Plugin system example.

This example demonstrates how to use minevent to build an extensible
plugin system where plugins can hook into application lifecycle events.
"""


from minevent import EventHandler, EventManager


class Plugin:
    """Base class for plugins."""

    def __init__(self, name: str) -> None:
        """Initialize plugin with a name.

        Args:
            name: Plugin name
        """
        self.name = name

    def setup(self, manager: EventManager) -> None:
        """Setup plugin by registering event handlers.

        Args:
            manager: Event manager to register handlers with
        """
        raise NotImplementedError


class LoggingPlugin(Plugin):
    """Plugin that logs application events."""

    def __init__(self) -> None:
        """Initialize logging plugin."""
        super().__init__("LoggingPlugin")

    def setup(self, manager: EventManager) -> None:
        """Register logging handlers."""
        manager.add_event_handler(
            "app_start",
            EventHandler(self.log_app_start),
        )
        manager.add_event_handler(
            "app_stop",
            EventHandler(self.log_app_stop),
        )
        manager.add_event_handler(
            "task_complete",
            EventHandler(self.log_task),
        )

    def log_app_start(self) -> None:
        """Log application start."""
        print(f"[{self.name}] 📝 Application started")

    def log_app_stop(self) -> None:
        """Log application stop."""
        print(f"[{self.name}] 📝 Application stopped")

    def log_task(self) -> None:
        """Log task completion."""
        print(f"[{self.name}] 📝 Task completed")


class MetricsPlugin(Plugin):
    """Plugin that tracks application metrics."""

    def __init__(self) -> None:
        """Initialize metrics plugin."""
        super().__init__("MetricsPlugin")
        self.task_count = 0

    def setup(self, manager: EventManager) -> None:
        """Register metrics handlers."""
        manager.add_event_handler(
            "task_complete",
            EventHandler(self.increment_task_count),
        )
        manager.add_event_handler(
            "app_stop",
            EventHandler(self.report_metrics),
        )

    def increment_task_count(self) -> None:
        """Increment task counter."""
        self.task_count += 1

    def report_metrics(self) -> None:
        """Report collected metrics."""
        print(f"[{self.name}] 📊 Total tasks completed: {self.task_count}")


class NotificationPlugin(Plugin):
    """Plugin that sends notifications for important events."""

    def __init__(self, notify_on_errors: bool = True) -> None:
        """Initialize notification plugin.

        Args:
            notify_on_errors: Whether to notify on errors
        """
        super().__init__("NotificationPlugin")
        self.notify_on_errors = notify_on_errors

    def setup(self, manager: EventManager) -> None:
        """Register notification handlers."""
        manager.add_event_handler(
            "app_stop",
            EventHandler(self.notify_shutdown),
        )
        if self.notify_on_errors:
            manager.add_event_handler(
                "error_occurred",
                EventHandler(self.notify_error),
            )

    def notify_shutdown(self) -> None:
        """Send shutdown notification."""
        print(f"[{self.name}] 🔔 Notification: Application shutting down")

    def notify_error(self) -> None:
        """Send error notification."""
        print(f"[{self.name}] 🔔 Notification: Error occurred!")


class PluginManager:
    """Manages plugins and coordinates their interaction with the application."""

    def __init__(self) -> None:
        """Initialize plugin manager."""
        self.event_manager = EventManager()
        self.plugins: list[Plugin] = []

    def register_plugin(self, plugin: Plugin) -> None:
        """Register a plugin.

        Args:
            plugin: Plugin to register
        """
        print(f"Registering plugin: {plugin.name}")
        self.plugins.append(plugin)
        plugin.setup(self.event_manager)

    def trigger_event(self, event: str) -> None:
        """Trigger an event that plugins can respond to.

        Args:
            event: Event name to trigger
        """
        self.event_manager.trigger_event(event)


class Application:
    """Sample application that uses plugin system."""

    def __init__(self, plugin_manager: PluginManager) -> None:
        """Initialize application with plugin manager.

        Args:
            plugin_manager: Plugin manager instance
        """
        self.plugin_manager = plugin_manager

    def start(self) -> None:
        """Start the application."""
        print("\n" + "=" * 60)
        print("Starting application...")
        print("=" * 60 + "\n")
        self.plugin_manager.trigger_event("app_start")

    def run_task(self, task_name: str) -> None:
        """Run a task.

        Args:
            task_name: Name of task to run
        """
        print(f"\nExecuting task: {task_name}")
        # Simulate task execution
        self.plugin_manager.trigger_event("task_complete")

    def simulate_error(self) -> None:
        """Simulate an error occurring."""
        print("\n⚠️  Simulating error...")
        self.plugin_manager.trigger_event("error_occurred")

    def stop(self) -> None:
        """Stop the application."""
        print("\n" + "=" * 60)
        print("Stopping application...")
        print("=" * 60 + "\n")
        self.plugin_manager.trigger_event("app_stop")


def main() -> None:
    """Run the plugin system example."""
    print("=== Plugin System Example ===\n")

    # Create plugin manager
    print("1. Creating plugin manager and registering plugins:\n")
    plugin_manager = PluginManager()

    # Register plugins
    plugin_manager.register_plugin(LoggingPlugin())
    plugin_manager.register_plugin(MetricsPlugin())
    plugin_manager.register_plugin(NotificationPlugin(notify_on_errors=True))

    # Create and run application
    print("\n2. Running application with plugins:\n")
    app = Application(plugin_manager)

    app.start()

    # Simulate some work
    app.run_task("Data processing")
    app.run_task("Model training")
    app.run_task("Report generation")

    # Simulate an error
    app.simulate_error()

    # Stop application
    app.stop()

    print("\n" + "=" * 60)
    print("=== Example Complete ===")
    print(
        "\nKey Benefits of Plugin Architecture:"
        "\n  ✓ Extensibility: Add new functionality without modifying core code"
        "\n  ✓ Modularity: Each plugin is self-contained"
        "\n  ✓ Flexibility: Enable/disable plugins as needed"
        "\n  ✓ Maintainability: Easier to test and maintain separate plugins"
        "\n  ✓ Separation of Concerns: Core app logic separated from cross-cutting concerns"
    )


if __name__ == "__main__":
    main()
