# Development Guide

## Repository Structure
- `apps/` — Application code
- `docs/` — Documentation
- `tests/` — Test suite

## How to Add a Broker
- Implement a new broker_adapter and broker_client
- Register in broker_registry
- Add configuration and secrets handling

## How to Add Endpoints
- Add FastAPI route in API app
- Implement handler in execution engine or relevant engine

## Error Handling Principles
- Explicit exception handling
- Use HTTPException for API errors
- Audit all critical failures

## Testing Expectations
- Unit and integration tests for all new features
- Use monkeypatching for broker isolation

## Commit Conventions
- Functional changes and documentation changes must be committed separately

## Documentation Rules
- All new features must be documented in the relevant doc file

## Corrected Development Flow
1. Design the change
2. Implement code
3. Update/create tests
4. Commit the functional change
5. Update documentation if needed
6. Commit documentation separately
