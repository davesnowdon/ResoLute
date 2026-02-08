# ResoLute Makefile
# Convenience commands for building, testing, and running
# Uses hatch for Python environment management (see agent/pyproject.toml)

.PHONY: export-web serve clean help run dev build-all test lint format check-hatch

# Default Godot command (can be overridden)
GODOT_CMD ?= godot

# Check if hatch is available
HATCH := $(shell command -v hatch 2> /dev/null)

#
# Hatch check
#

check-hatch:
	@if [ -z "$(HATCH)" ]; then \
		echo "❌ hatch not found. Please install it:"; \
		echo "   pipx install hatch  (recommended)"; \
		echo "   pip install hatch"; \
		exit 1; \
	fi

#
# Game Export Commands
#

export-web: ## Export the Godot project for web
	@./export_web.sh

serve-game: ## Start a local web server to test the game build only
	@echo "Starting local server at http://localhost:8080"
	@cd build/web && python3 -m http.server 8080

clean: ## Clean build artifacts
	@rm -rf build/web/*
	@echo "Build directory cleaned"

import: ## Import Godot project resources
	@$(GODOT_CMD) --headless --path ui --import

#
# Backend Commands (using hatch)
#

install: check-hatch ## Install backend dependencies via hatch
	@cd agent && hatch env create
	@echo "✅ Hatch environment created. Use 'make run' to start the server."

run: check-hatch ## Run the full ResoLute service (backend + game frontend)
	@echo "Starting ResoLute service at http://0.0.0.0:8000"
	@cd agent && hatch run server

dev: run ## Alias for run (hatch server already has --reload)

client: check-hatch ## Run the ResoLute client
	@cd agent && hatch run client $(ARGS)

test: check-hatch ## Run tests
	@cd agent && hatch run test $(ARGS)

lint: check-hatch ## Run linter
	@cd agent && hatch run lint

format: check-hatch ## Format code
	@cd agent && hatch run format

#
# Combined Commands
#

build-all: export-web install ## Build game and install backend dependencies
	@echo "✅ Build complete! Run 'make run' to start the service."

deploy-check: check-hatch ## Check if everything is ready for deployment
	@echo "Checking deployment readiness..."
	@test -f build/web/index.html && echo "✅ Game build exists" || echo "❌ Game not built - run 'make export-web'"
	@cd agent && hatch run python -c "from resolute.server.app import app" 2>/dev/null && echo "✅ Backend imports OK" || echo "❌ Backend import failed - run 'make install'"
	@echo ""
	@echo "To deploy: run 'make run' or use Docker"

#
# Help
#

help: ## Show this help message
	@echo "ResoLute - Music Learning Adventure Game"
	@echo ""
	@echo "Prerequisites:"
	@echo "  - Godot 4.x (for game export)"
	@echo "  - hatch (Python environment manager): pipx install hatch"
	@echo ""
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
