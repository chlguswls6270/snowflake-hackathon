# Security and deployment

This is a portfolio demo, not a multi-user production service.

- Keep provider credentials in server environment variables. Never put them in
  `NEXT_PUBLIC_`, `VITE_`, a browser bundle, a ZIP, logs, or Git.
- Set `DEMO_ACCESS_TOKEN` to a randomly generated access code of at least 32
  characters. An unset or short code disables protected operations. Share the
  code only with people you authorize to use the demo; it is not a provider key.
  The browser asks for it when needed and keeps it in memory only.
- `ALLOW_LOCAL_DEMO=true` is an explicit local testing exception. Bind the
  backend to loopback and never enable this exception on a public host.
- Use HTTPS for deployments. Set allowed origins to the actual frontend origin.
- Request limits are per process, not a distributed quota. Before sharing a
  live paid API broadly, add a persistent gateway rate limit and configure the
  provider's usage restrictions and billing alerts.
- Raw provider errors, uploaded data, and model responses must not appear in
  public error responses or logs.
- If a credential was ever committed, revoke/rotate it first. Deleting the file,
  archiving the repository, or making it private does not revoke a credential.
  Coordinate any history rewrite with collaborators; forks and old clones can
  retain the original data.
- Run the security regression tests before merging changes. Tests use fake
  credentials and mocked provider calls; they do not contact paid services.

## Snowflake

Use a dedicated least-privilege demo role, not ACCOUNTADMIN. Grant only the
warehouse/database/Cortex access needed by the application. SQL values are
bound separately from queries; configured database names are validated.

Run tests from the repository root: `python -m pytest tests -q`.

A password existed in historical commits. Rotation and any coordinated history
cleanup must be completed separately; these source changes do not revoke it.

Use Node.js 20.19+ for frontend tooling. The scoped minimatch override patches
ESLint's parser dependency; remove it when upstream declares a patched version.
Python runtime versions are resolved from backend/requirements.in and pinned in
backend/requirements.txt. Re-run the dependency audit after resolving updates.

