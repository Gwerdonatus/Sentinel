# Sentinel Security Policy

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email: security@sentinel-platform.io

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if known)

We will acknowledge within 48 hours and provide a fix timeline within 7 days.

---

## Security Principles

### Least Privilege

Every component operates with the minimum permissions required:
- Database user has no `CREATE`, `DROP`, or `ALTER` permissions in production
- Application service account has read/write on specific tables only
- Worker processes cannot access the web server's file system
- API keys are scoped to specific permission sets, not global access

### Zero Trust Assumptions

Sentinel assumes hostile environments:
- All inputs are untrusted until validated
- Internal service-to-service calls are authenticated
- Database connections from workers are authenticated separately
- Redis connections use AUTH passwords in production

### Secrets Management

**Never:**
- Commit secrets to version control (enforced by `.gitignore` and `git-secrets`)
- Log secrets, even partially
- Pass secrets as command-line arguments (they appear in process lists)
- Store secrets in environment variables that are exported to child processes unnecessarily

**Always:**
- Use environment variables injected at runtime by the container orchestrator
- Rotate secrets on compromise immediately
- Use separate secrets for each environment (dev, staging, production)

### Cryptography

- Passwords: `argon2` (via `django-argon2`)
- API keys: `HMAC-SHA256` for storage, never stored in plain text
- JWT: `RS256` (asymmetric) in production, `HS256` acceptable in local dev
- Tokens: cryptographically random via `secrets.token_urlsafe()`
- No custom cryptography implementations

### Input Validation

All external input is validated at the serializer layer before reaching business logic:
- String length limits enforced
- UUID format validated before database lookup
- JSON payloads schema-validated
- File uploads rejected (Sentinel does not accept file uploads)

### Rate Limiting

Default rate limits (configurable per environment):
- Authentication endpoints: 10 requests/minute per IP
- API endpoints (authenticated): 1000 requests/minute per API key
- API endpoints (unauthenticated): 60 requests/minute per IP
- Webhook ingestion: 10,000 requests/minute per source

### Dependency Security

- Dependabot enabled for automated security updates
- `pip-audit` runs in CI to check for known vulnerabilities
- No dependency with a known critical CVE is acceptable in `main`

---

## OWASP Top 10 Coverage

| Risk | Mitigation |
|---|---|
| A01 Broken Access Control | RBAC + object-level permissions via `django-guardian` |
| A02 Cryptographic Failures | `argon2` passwords, `RS256` JWT, HTTPS-only |
| A03 Injection | ORM only, parameterized queries, input validation |
| A04 Insecure Design | Service layer separates concerns, security review in PR process |
| A05 Security Misconfiguration | Security headers middleware, Docker security, env-only secrets |
| A06 Vulnerable Components | `pip-audit` in CI, Dependabot |
| A07 Auth Failures | JWT rotation, brute force protection (`django-axes`), MFA (Phase 2) |
| A08 Software Integrity | Signed commits recommended, CI verifies checksums |
| A09 Logging Failures | Structured logging, immutable audit trail, SIEM export (Phase 3) |
| A10 SSRF | Allowlist for outbound webhook URLs, no user-controlled request targets |

---

## Security Response SLA

| Severity | Response Time | Fix Time |
|---|---|---|
| Critical | 4 hours | 24 hours |
| High | 24 hours | 7 days |
| Medium | 72 hours | 30 days |
| Low | 7 days | 90 days |
