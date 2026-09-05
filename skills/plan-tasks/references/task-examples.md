# Task Examples

Good vs bad task descriptions.

## Example 1: Database Model

### Bad
```
Add user model
```
Why: No location, no fields, no constraints.

### Good
```
Create User model

Location: src/models/user.ts

Fields:
- id: UUID, primary key, auto-generated
- email: string, unique, not null
- passwordHash: string, not null
- createdAt: timestamp, default now()
- updatedAt: timestamp, auto-update

Verify: Model file exists, can import and instantiate User
```

## Example 2: API Endpoint

### Bad
```
Add login endpoint
```
Why: No path, no request/response format, no error cases.

### Good
```
Add POST /api/auth/login endpoint

Location: src/routes/auth.ts

Request body:
- email: string (required)
- password: string (required)

Response:
- 200: { token: string, user: { id, email } }
- 400: { error: "Invalid credentials" }
- 429: { error: "Too many attempts" } (after 5 failures)

Verify: Can login with valid credentials, get 400 on invalid
```

## Example 3: Refactoring

### Bad
```
Refactor auth module
```
Why: No specific changes, no boundaries, no success criteria.

### Good
```
Extract token generation from login handler

Location: src/routes/auth.ts → src/services/token.ts

Changes:
- Create TokenService class in new file
- Move generateToken() and verifyToken() functions
- Update imports in auth.ts
- Keep same function signatures

Verify: All auth tests still pass, no changes to API behavior
```

## Example 4: Bug Fix

### Bad
```
Fix login bug
```
Why: Which bug? What's the expected behavior?

### Good
```
Fix: Login returns 500 when email contains uppercase

Location: src/services/auth.ts:45

Problem: Email comparison is case-sensitive, user "John@example.com"
can register but can't login as "john@example.com"

Fix: Lowercase email before lookup in findUserByEmail()

Verify: Can login with any case variation of registered email
```

## Example 5: Separable vs Coupled Splits (Step 4.6 Eligibility Trigger)

The eligibility trigger considers backend tasks with two-or-more expected
implementor-writable files and targets one-file pieces only when each piece
independently compiles, carries its own passing gate, and introduces no symbol
required by a sibling. Read-only Tess tests do not count as implementor writes.

### Separable — independently gated one-file pieces

A Sonnet task updates existing `src/cache/lru.rs` and
`src/cache/invalidation.rs`. The PRD names eviction and invalidation as
independent capabilities; both modules already exist, neither change introduces
a symbol the other needs, and each has its own independently passing gate.
Split into two one-file subtasks: each has `qwen_eligible: true` if neither
edits a public contract. A new `metrics.rs` plus its required `mod.rs` export
is different: keep that correlated two-file slice together, with
`qwen_eligible: false`, `qwen_excluded_reason: "files"` at Sonnet tier; it uses
the existing Codex/Claude fences.

### Coupled — stays whole and routes above Qwen

A task changes an internal interface in `src/storage/mod.rs` and its caller in
`src/storage/file.rs`. The PRD's dependency graph says the caller needs the
new signature, so either file shipped alone leaves the build or tests red.
With `contract_edit` and `algorithmic_risk` both false, the eligibility split
is considered but rejected: the inseparable two-file task stays one task,
`qwen_eligible: false`, `qwen_excluded_reason: "files"`, and routes through the
existing Codex/Claude fences. If the interface is public, `contract_edit` is
true and the risk exemption already prevents eligibility splitting; the tier
and exclusion follow step 4.7's existing precedence. Context-budget splitting
remains independent in either case.
