# Calls

How the handlers and the conditions are called. `minevent` exports `Handler` only, and
`validate_signature` states [the calling rule](../architecture.md#the-calling-rule). It is not part
of the [public API](../architecture.md#overview), and neither are the other functions of the module.

<!-- prettier-ignore -->
::: minevent.calls
    options:
      members:
        - Handler
        - validate_signature
