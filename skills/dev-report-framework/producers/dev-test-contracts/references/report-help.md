# Help: Consumer contract verification

This report part is the verdict of running the provider against the consumer
contracts that depend on it — not a static read of the pact files. The
provider was started and every consumer interaction was replayed against it.

## How to read it

- **Status.** `error` means at least one interaction failed — a consumer's
  expectation is no longer met and the release would break that consumer.
  `warn` means every interaction passed but one or more had no provider
  state, or nothing was verified at all (a coverage gap, not a clean pass).
  `ok` means every interaction passed and every one asserted a provider
  state.
- **Metric cards.** Total interactions, how many passed, how many failed, and
  how many ran without a provider state.
- **Verified interactions table.** One row per interaction: the consumer, the
  interaction, the provider state it set up (`(none)` when it set none), the
  result, and the mismatch detail for failures. The table's heading icon
  mirrors the verdict.
- **A `(none)` provider state is a weak pass.** The interaction passed only
  because no precondition was asserted; treat it as lower-confidence than a
  stated pass.

## Suggested provider verification stack

The "Suggested provider verification stack" section is **advisory**. Nothing
was wired or installed this run. It describes the four parts of a real
verification setup (a verifier, provider-state handlers, a contract source,
and a CI `can-i-deploy` gate) and names a concrete verifier matched to the
detected provider stack, so the team has a starting point. It is guidance,
not a result.

## What this part does not tell you

Whether the consumer's own tests pass, whether the contract is the right
contract, or whether unconsumed provider endpoints exist. It only answers:
does the provider still honor the contracts it was given?
