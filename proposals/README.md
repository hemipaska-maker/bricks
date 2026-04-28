# Brick Proposals

When a Track 1 case reveals a gap in the brick stdlib, RA writes a proposal here. Coder implements it later via a normal PR through an Ops-created GitHub Issue. RA does NOT write brick code directly.

## File naming

`brick-<category>-<name>.md` — e.g. `brick-string-regex-extract.md`, `brick-list-group-by.md`.

## Template

```markdown
# Brick proposal: <name>

**Category:** string | list | dict | numeric | date | io | ...
**Proposed by:** RA session, during case `<case-slug>`
**Date:** YYYY-MM-DD

## Signature

one-line: `brick(input, params) → output`

## Motivation

Which case(s) needed this. Quote the blueprint YAML that would use it.

## Spec

- Input types: ...
- Param schema: ...
- Output type: ...
- Edge cases: ...

## Example

Minimal YAML snippet showing use in context:

\`\`\`yaml
steps:
  - name: example_step
    brick: <name>
    params:
      ...
    save_as: result
\`\`\`

## Test cases

3–5 input/output pairs to be used as unit tests:

| Input | Params | Expected output |
|---|---|---|
| ... | ... | ... |

## Notes

Any concerns, alternatives considered, or implementation hints for Coder.
```

## Workflow

1. RA writes the proposal here during case work
2. RA flags to Hemi in chat: "new brick proposal ready — `<filename>`"
3. Hemi reviews, tells Ops to create a GitHub Issue referencing the proposal file
4. Coder implements, opens PR
5. When PR merges, RA updates status in the proposal file (add a `**Status:** Shipped in #<PR>` line at the top) and can now use the brick in subsequent cases
