# Mission Planning Tool - Development Commands
# Usage: make <target>

ROOT_DIR := $(CURDIR)
VENV_PYTHON := $(ROOT_DIR)/.venv/bin/python
PYTHON_BIN ?= $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),python3)
PDM_BIN := $(shell if command -v pdm >/dev/null 2>&1; then command -v pdm; elif [ -x "$(VENV_PYTHON)" ] && "$(VENV_PYTHON)" -m pdm --version >/dev/null 2>&1; then printf '%s -m pdm' "$(VENV_PYTHON)"; elif python3 -m pdm --version >/dev/null 2>&1; then printf '%s -m pdm' "python3"; fi)

.PHONY: help install dev test lint format clean build release-gate lint-fe-strict assert-pdm

# Default target
help:
	@echo "Mission Planning Tool - Available Commands"
	@echo ""
	@echo "  make install     Install all dependencies (backend + frontend)"
	@echo "  make dev         Start development servers (backend + frontend)"
	@echo "  make test        Run all tests"
	@echo "  make lint        Run linters (Python + TypeScript)"
	@echo "  make format      Format code (Python + TypeScript)"
	@echo "  make typecheck   Run type checkers"
	@echo "  make clean       Clean build artifacts"
	@echo "  make build       Build for production"
	@echo "  make release-gate Run the local release verification workflow"
	@echo ""
	@echo "Backend only:"
	@echo "  make backend     Start backend server only"
	@echo "  make test-py     Run Python tests"
	@echo "  make lint-py     Lint Python code"
	@echo "  make format-py   Format Python code"
	@echo ""
	@echo "Frontend only:"
	@echo "  make frontend    Start frontend server only"
	@echo "  make test-fe     Run frontend tests"
	@echo "  make format-fe   Format frontend code (Prettier)"
	@echo "  make lint-fe     Lint TypeScript code"
	@echo "  make lint-fe-strict  Fail on frontend warnings too"
	@echo ""

# ============================================
# Full Stack Commands
# ============================================

install: install-py install-fe
	@echo "✅ All dependencies installed"

assert-pdm:
	@if [ -z "$(strip $(PDM_BIN))" ]; then \
		echo "❌ PDM not found. Install it with 'python3 -m pip install pdm' or activate an environment that provides it."; \
		exit 1; \
	fi

dev:
	@./run_dev.sh

test: test-py test-fe
	@echo "✅ All tests passed"

lint: lint-py lint-fe
	@echo "✅ All linting passed"

format: format-py format-fe
	@echo "✅ Code formatted"

typecheck: typecheck-py typecheck-fe
	@echo "✅ Type checking passed"

clean:
	@echo "🧹 Cleaning build artifacts..."
	@rm -rf dist/ build/ *.egg-info/ .pytest_cache/ .mypy_cache/ .coverage htmlcov/
	@rm -rf frontend/dist/ frontend/node_modules/.cache/
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Clean complete"

build: build-fe
	@echo "✅ Build complete"

release-gate:
	@./scripts/release_gate.sh

# ============================================
# Backend (Python) Commands
# ============================================

install-py:
	@$(MAKE) assert-pdm
	@echo "📦 Installing Python dependencies (via PDM)..."
	@$(PDM_BIN) install --dev -q

backend:
	@echo "🚀 Starting backend server..."
	@PYTHONPATH=. $(PYTHON_BIN) -m uvicorn backend.main:app --reload --port 8000

test-py:
	@echo "🧪 Running Python tests..."
	@PYTHONPATH=. $(PYTHON_BIN) -m pytest tests/ -v

test-py-cov:
	@echo "🧪 Running Python tests with coverage..."
	@PYTHONPATH=. $(PYTHON_BIN) -m pytest tests/ --cov=src/mission_planner --cov-report=html

lint-py:
	@echo "🔍 Linting Python code..."
	@PYTHONPATH=. $(PYTHON_BIN) -m flake8 src/ backend/ --max-line-length=88 --extend-ignore=E203,W503

format-py:
	@echo "🎨 Formatting Python code..."
	@PYTHONPATH=. $(PYTHON_BIN) -m black src/ backend/ tests/
	@PYTHONPATH=. $(PYTHON_BIN) -m isort src/ backend/ tests/

typecheck-py:
	@echo "📝 Type checking Python..."
	@PYTHONPATH=. $(PYTHON_BIN) -m mypy src/ --ignore-missing-imports

# ============================================
# Frontend (TypeScript) Commands
# ============================================

install-fe:
	@echo "📦 Installing frontend dependencies..."
	@cd frontend && npm install --silent

frontend:
	@echo "🚀 Starting frontend server..."
	@cd frontend && npm run dev

test-fe:
	@echo "🧪 Running frontend tests..."
	@cd frontend && npm run test:run

test-fe-watch:
	@echo "🧪 Running frontend tests (watch mode)..."
	@cd frontend && npm run test

format-fe:
	@echo "🎨 Formatting frontend code..."
	@cd frontend && npm run format

lint-fe:
	@echo "🔍 Linting TypeScript code..."
	@cd frontend && npm run lint

lint-fe-strict:
	@echo "🔍 Linting TypeScript code (strict)..."
	@cd frontend && npm run lint:strict

typecheck-fe:
	@echo "📝 Type checking TypeScript..."
	@cd frontend && npx tsc --noEmit

build-fe:
	@echo "🏗️ Building frontend..."
	@cd frontend && npm run build

# ============================================
# Utility Commands
# ============================================

benchmark:
	@echo "📊 Running benchmarks..."
	@PYTHONPATH=. $(PYTHON_BIN) scripts/benchmark_adaptive.py

validate:
	@echo "✅ Running validation..."
	@PYTHONPATH=. $(PYTHON_BIN) scripts/validate_adaptive_stepping.py

# Quick checks before commit
precommit: format lint typecheck test
	@echo "✅ Pre-commit checks passed"
