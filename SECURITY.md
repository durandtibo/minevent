# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.6.x   | :white_check_mark: |
| < 0.6   | :x:                |

## Reporting a Vulnerability

The `minevent` team takes security bugs seriously. We appreciate your efforts to responsibly
disclose your findings, and will make every effort to acknowledge your contributions.

To report a security issue, please use the GitHub Security Advisory
["Report a Vulnerability"](https://github.com/durandtibo/minevent/security/advisories/new) tab.

The `minevent` team will send a response indicating the next steps in handling your report. After
the initial reply to your report, the security team will keep you informed of the progress towards a
fix and full announcement, and may ask for additional information or guidance.

Please report security bugs in third-party modules to the person or team maintaining that module.

## Security Best Practices

### Validate the Payload

The values of a `Context` are not checked by `minevent`. If the data of a trigger comes from an
untrusted source, validate it in the handler to prevent injection attacks or unexpected behavior:

```python
from minevent import Context, EventManager


def safe_handler(context: Context) -> None:
    # Validate input before processing
    user_input = context["user_input"]
    if not isinstance(user_input, str):
        raise TypeError("Expected string input")
    # Additional validation...
    print(f"Processing: {user_input}")


manager = EventManager()
manager.add_event_handler("user_action", safe_handler)
manager.trigger_event("user_action", {"user_input": "hello"})
```

### Run Trusted Code and Load Trusted Data

A handler or a condition runs with the privileges of your program, so register only code that you
trust. A `Context` and a `PeriodicCondition` can be pickled: load a pickle from a source that you
trust only.

## Disclosure Policy

When we receive a security bug report, we will:

1. Confirm the problem and determine the affected versions
2. Audit code to find any potential similar problems
3. Prepare fixes for all supported versions
4. Release new security fix versions as soon as possible

## Comments on this Policy

If you have suggestions on how this process could be improved, please submit a pull request or open
an issue to discuss.
