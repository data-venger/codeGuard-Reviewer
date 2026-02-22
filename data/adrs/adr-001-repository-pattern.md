---
service: all
status: accepted
date: 2024-11-15
tags:
  - architecture
  - database
  - patterns
---

# ADR-001: Use Repository Pattern for Data Access

## Status

Accepted — November 2024

## Context

Multiple services in our codebase had inconsistent approaches to database access.
Some controllers contained direct SQL queries, others used a thin wrapper, and a few
used an ORM inconsistently. This led to:

- SQL injection vulnerabilities in user-facing endpoints
- Difficulty testing business logic independently of the database
- Duplicated query logic across controllers
- No single place to enforce caching or audit logging on data access

## Decision

All services must use the **Repository Pattern** for database access:

1. **Repository classes** are the only code that may execute database queries
2. **Service classes** call repository methods — they never construct SQL directly
3. **Controllers/Routes** call service methods — they never call repositories directly
4. Each entity (e.g., User, Order, Product) has its own repository class
5. Repository methods return domain objects, not raw database rows

### Example Structure

```
app/
├── routes/          # HTTP handlers — call services only
├── services/        # Business logic — call repositories only
├── repositories/    # Data access — only layer that touches the DB
└── models/          # Domain objects / data classes
```

## Consequences

- All SQL is centralised in repository classes, making auditing easier
- Business logic can be unit tested with mocked repositories
- Caching can be added at the repository layer without changing service code
- New developers have a clear pattern to follow
- Adds a small amount of boilerplate per entity (one repository class)

## Anti-Patterns (Forbidden)

- Direct DB calls from route handlers
- SQL string concatenation anywhere in the codebase
- Returning raw cursor results from repositories (must return typed objects)
- Repositories containing business logic (they should only handle data access)
