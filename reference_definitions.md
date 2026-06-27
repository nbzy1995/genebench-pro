# Reference Definitions

This package is organized around one public contract per problem:
`eval_config.json`. The config is intentionally self-contained so readers do
not need private benchmark metadata.

## `eval_config.json`

- `id`: stable public eval identifier.
- `eval_uuid`: UUID for this released problem instance.
- `task`: the released prompt shown to the agent.
- `data_files`: paths, relative to the problem directory, for the staged files
  visible to the agent.
- `ground_truth`: released reference answer values.
- `grader`: the public grading contract. `grader.type` selects the grading
  rule, and `grader.config` contains key-specific tolerances and constraints.

## Answer Shape

Most tasks ask for:

```json
{
  "answer": {
    "<field_name>": "<value>"
  },
  "reasoning": "<method and quality-control description>"
}
```

The reference grader accepts either that nested shape or a direct answer object,
unless `strict_answer_schema` is enabled in `grader.config`. When strict schema
is enabled, the top-level object must contain exactly `answer` and `reasoning`,
`answer` must contain exactly the graded keys, and `reasoning` must be a string.

## Grader Types

### `numeric_tolerance`

Grades one numeric field. The field name is `grader.config.key`, with `h2` as
the default if no key is specified. The submitted value must be convertible to a
finite floating-point number. Optional `min_value` and `max_value` are sanity
constraints. A value passes if it satisfies either the configured
`absolute_tolerance` or `relative_tolerance`.

Some configs include `answer_field` as display metadata. The authoritative
graded field is still `key`.

### `multi_numeric_tolerance`

Grades several numeric fields. Each field is listed under
`grader.config.keys`. Every listed field must pass its own numeric tolerance for
the overall submission to pass. Per-field `weight` values affect the reported
score but not the all-fields pass requirement.

### `composite`

Grades a mixture of field types:

- `numeric_keys`: numeric fields graded with absolute and/or relative
  tolerance.
- `integer_keys`: integer fields graded by exact integer equality, with
  optional `min_value` and `max_value` sanity constraints.
- `exact_match_keys`: string-like fields graded by exact match, optionally
  case-sensitive.

By default, every configured key is required. Setting `required: false` allows a
field to fail without failing the whole submission, although it still affects
the reported score if present. If `forbid_extra_keys` is true, extra keys inside
`answer` fail the submission.

Exact-match fields are normalized by converting values to strings and trimming
leading and trailing whitespace. Case is ignored unless the field config sets
`case_sensitive: true`.

For all grader types, `passed` is the authoritative grading decision. `score`
is a diagnostic summary over graded fields and should not be interpreted as a
substitute for `passed`.

## Reference Implementation

`reference_grader.py` implements the public grading semantics for the grader
types used in this package. It is designed for external validation of
`eval_answer.json` files.
