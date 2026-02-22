---
language: python
category: general
severity: error
---

# Python Coding Standards

## Naming Conventions

- All module-level variables must use `UPPER_SNAKE_CASE`
- Class names must use `PascalCase`
- Function and method names must use `snake_case`
- Private methods must be prefixed with a single underscore `_`
- Constants must be defined at module level, never inside functions

## Error Handling

- Never use bare `except:` — always catch specific exception types
- Always log the full exception traceback using `logger.exception()`
- Use custom exception classes for domain-specific errors (e.g. `PaymentFailedError`)
- Never silently swallow exceptions — at minimum, log a warning
- All API endpoint handlers must have a top-level try/except that returns a structured error response

## Security

- Never commit secrets, API keys, or tokens to source control
- All secrets must be loaded from environment variables or a secrets manager
- All HTTP endpoints must require authentication middleware — no unauthenticated endpoints in production
- User input must always be validated and sanitized before use
- SQL queries must use parameterised queries — never use string concatenation for SQL
- All external API calls must use HTTPS, never plaintext HTTP

## Database Access

- Database calls must never be made directly from route handlers or controllers
- All database access must go through the Repository layer (see ADR-001)
- Use connection pooling — never create a new connection per request
- All database queries must have appropriate indexes; document index requirements in migration files
- Use transactions for multi-step operations that must be atomic

## Testing

- Every public function must have at least one unit test
- Minimum code coverage target: 80%
- Test files must be named `test_<module_name>.py`
- Use `pytest` as the test runner — do not use `unittest` directly
- Mock external dependencies (APIs, databases) in unit tests
- Integration tests must use a dedicated test database, never production

## Logging

- Use structured logging with the `structlog` library
- Every log entry must include: `event`, `level`, `timestamp`, and `correlation_id`
- Log all incoming API requests and outgoing responses at `INFO` level
- Log all exceptions at `ERROR` level with full stack trace
- Never log sensitive data (passwords, tokens, PII)

## Code Organisation

- Keep files under 300 lines; split large files into focused modules
- Group imports: stdlib → third-party → local, separated by blank lines
- Each module should have a module-level docstring explaining its purpose
- Avoid circular imports — if you need one, it's a sign of poor module boundaries
