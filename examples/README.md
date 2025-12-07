# minevent Examples

This directory contains practical examples demonstrating how to use `minevent` in various scenarios.

## Examples

### Basic Examples

- [`basic_usage.py`](basic_usage.py) - Simple event handling basics
- [`conditional_handlers.py`](conditional_handlers.py) - Using conditional event handlers
- [`multiple_handlers.py`](multiple_handlers.py) - Managing multiple event handlers

### Machine Learning Examples

- [`ml_training_logger.py`](ml_training_logger.py) - Logging metrics during ML training
- [`ml_checkpoint_saver.py`](ml_checkpoint_saver.py) - Saving model checkpoints periodically
- [`ml_early_stopping.py`](ml_early_stopping.py) - Implementing early stopping with events

### Advanced Examples

- [`custom_condition.py`](custom_condition.py) - Creating custom conditions
- [`plugin_system.py`](plugin_system.py) - Building a plugin system with events
- [`callback_wrapper.py`](callback_wrapper.py) - Wrapping minevent as a callback API

## Running the Examples

Each example is a standalone Python script. To run an example:

```bash
python examples/basic_usage.py
```

Make sure you have `minevent` installed:

```bash
pip install minevent
```

## Contributing Examples

If you have a useful example you'd like to share, please submit a pull request! Examples should be:

- Self-contained (can run independently)
- Well-commented
- Demonstrate a specific use case
- Follow PEP 8 style guidelines
