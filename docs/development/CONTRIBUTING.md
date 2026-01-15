# Contributing Guide

> Guidelines for contributing to COSMOS42 Mission Planning

## Getting Started

### Prerequisites

- **Node.js** 22+ (via nvm)
- **Python** 3.11+
- **PDM** for Python dependency management

### Setup

```bash
# Clone repository
git clone <repo-url>
cd mission-planning

# Install Python dependencies
pdm install

# Install frontend dependencies
cd frontend
npm install

# Start development servers
cd ..
./run_dev.sh
```

---

## Code Style

### Frontend (TypeScript/React)

- **ESLint** for linting
- **Prettier** for formatting
- **TypeScript** strict mode

```bash
# Run linting
cd frontend
npm run lint

# Fix issues
npm run lint:fix
```

#### Guidelines

1. Use functional components with hooks
2. Prefer named exports over default exports
3. Use TypeScript interfaces for props
4. Keep components under 200 lines
5. Extract logic into custom hooks

### Backend (Python)

- **Black** for formatting
- **isort** for imports
- **mypy** for type checking
- **flake8** for linting

```bash
# Format code
pdm run black .
pdm run isort .

# Type check
pdm run mypy src/

# Lint
pdm run flake8
```

#### Guidelines

1. Use type hints for all functions
2. Follow PEP 8 naming conventions
3. Keep functions under 50 lines
4. Use Pydantic for data validation

---

## Git Workflow

### Branch Naming

```text
feature/short-description
bugfix/issue-description
docs/documentation-update
refactor/component-name
```

### Commit Messages

Follow conventional commits:

```text
feat: add satellite search functionality
fix: correct incidence angle calculation
docs: update API reference
refactor: split MissionPlanning component
test: add scheduler unit tests
chore: update dependencies
```

### Pull Request Process

1. Create feature branch from `main`
2. Make changes with clear commits
3. Update documentation if needed
4. Run tests locally
5. Create PR with description
6. Request review
7. Address feedback
8. Squash and merge

---

## Testing

### Frontend Tests

```bash
cd frontend
npm run test        # Run tests
npm run test:watch  # Watch mode
npm run test:cov    # Coverage report
```

### Backend Tests

```bash
# Run all tests
pdm run pytest

# Run with coverage
pdm run pytest --cov=src/mission_planner

# Run specific test file
pdm run pytest tests/integration/test_scheduler_algorithms.py
```

### Adding Tests

**Frontend:**

```typescript
// ComponentName.test.tsx
import { render, screen } from '@testing-library/react'
import { ComponentName } from './ComponentName'

describe('ComponentName', () => {
  it('renders correctly', () => {
    render(<ComponentName />)
    expect(screen.getByText('Expected text')).toBeInTheDocument()
  })
})
```

**Backend:**

```python
# test_feature.py
import pytest
from mission_planner.feature import function_to_test

def test_function_basic():
    result = function_to_test(input_value)
    assert result == expected_value

def test_function_edge_case():
    with pytest.raises(ValueError):
        function_to_test(invalid_input)
```

---

## Documentation

### Where to Document

| Type | Location |
|------|----------|
| API endpoints | `docs/api/` |
| Architecture | `docs/architecture/` |
| Components | `docs/frontend/` |
| Algorithms | `docs/algorithms/` |
| Setup guides | `docs/getting-started/` |

### Documentation Style

- Use Markdown with proper headings
- Include code examples
- Add tables for props/parameters
- Keep language concise and clear

---

## Project Structure

```text
mission-planning/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── routers/             # API routers
│   └── *.py                 # Backend modules
├── config/                  # YAML configuration
├── data/                    # TLE and data files
├── docs/                    # Documentation
├── frontend/
│   ├── src/
│   │   ├── api/            # API client
│   │   ├── components/     # React components
│   │   ├── context/        # React context
│   │   ├── hooks/          # Custom hooks
│   │   ├── store/          # Zustand store
│   │   └── types/          # TypeScript types
│   └── package.json
├── scripts/                 # Utility scripts
├── src/mission_planner/     # Core Python library
└── tests/                   # Test files
```

---

## Common Tasks

### Adding a New Component

1. Create component file in appropriate directory
2. Add TypeScript interfaces for props
3. Export from index.ts
4. Add tests
5. Update documentation

### Adding an API Endpoint

1. Add endpoint to appropriate router
2. Define Pydantic models
3. Implement logic
4. Add tests
5. Update API documentation

### Updating Dependencies

**Frontend:**

```bash
cd frontend
npm update
npm audit fix
```

**Backend:**

```bash
pdm update
pdm lock
```

---

## Getting Help

- Check existing documentation
- Search closed issues
- Open new issue with details
- Join team discussions

---

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on technical merit
- Help others learn and grow
