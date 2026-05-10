# Backend Tests Directory

This directory contains all backend tests organized by category.

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_indicators.py

# Run with verbose output
pytest -v
```

## Test Structure

- `conftest.py` - Shared fixtures and test configuration
- `test_indicators.py` - Indicator function tests (EMA, Darvas)
- `test_api_endpoints.py` - API endpoint integration tests
- `test_signal_engine.py` - Signal generation logic tests (to be added)
