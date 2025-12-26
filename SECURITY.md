# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
|---------|--------------------|
| 0.4.x   | :white_check_mark: |
| < 0.4   | :x:                |

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

When using `minevent`, please follow these security best practices:

### 1. Validate Event Handler Inputs

Always validate inputs to event handlers to prevent injection attacks or unexpected behavior:

```python
from minevent import EventHandler, EventManager


def safe_handler(user_input: str) -> None:
    # Validate input before processing
    if not isinstance(user_input, str):
        raise TypeError("Expected string input")
    # Additional validation...
    print(f"Processing: {user_input}")


manager = EventManager()
manager.add_event_handler("user_action", EventHandler(safe_handler))
```

### 2. Be Cautious with Dynamic Handler Creation

Avoid creating event handlers from untrusted sources or user input:

```python
# DON'T DO THIS
user_function_name = input("Enter function name: ")
handler = EventHandler(eval(user_function_name))  # DANGEROUS!

# DO THIS INSTEAD
allowed_handlers = {
    "handler1": safe_handler1,
    "handler2": safe_handler2,
}
user_choice = input("Choose handler (handler1/handler2): ")
if user_choice in allowed_handlers:
    handler = EventHandler(allowed_handlers[user_choice])
```

### 3. Keep Dependencies Updated

Regularly update `minevent` and its dependencies to get the latest security patches:

```shell
uv pip install --upgrade minevent
```

### 4. Review Event Handler Code

Regularly review event handler code for potential security issues, especially handlers that:

- Access file systems
- Make network requests
- Execute system commands
- Process user input

## Disclosure Policy

When we receive a security bug report, we will:

1. Confirm the problem and determine the affected versions
2. Audit code to find any potential similar problems
3. Prepare fixes for all supported versions
4. Release new security fix versions as soon as possible

## Comments on this Policy

If you have suggestions on how this process could be improved, please submit a pull request or open
an issue to discuss.
