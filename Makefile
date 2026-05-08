# --- PROJECT CONFIGURATION ---
PROJECT_NAME := stock-market-crawler
PYTHON_VERSION := 3.12
.DEFAULT_GOAL := help

# --- OS DETECTION & PATHS ---
ifeq ($(OS),Windows_NT)
    OS_TYPE   := Windows
    SEP       := \\
    BIN_DIR   := Scripts
    EXT       := .exe
    WHICH     := where
    RM        := rmdir /s /q
    PYTHON    := python
    LOCAL_UV  := .\uv.exe
    LOCAL_UV_CHECK := ./uv.exe
else
    OS_TYPE   := $(shell uname -s)
    BIN_DIR := bin
    EXT       :=
    SEP       := /
    WHICH     := which
    RM        := rm -rf
    PYTHON    := python3
    LOCAL_UV  := ./uv
    LOCAL_UV_CHECK := ./uv
endif

# --- UV INFRASTRUCTURE ---
GLOBAL_UV_TEST := $(shell $(WHICH) uv 2>$(if $(filter Windows,$(OS_TYPE)),nul,/dev/null))

ifneq ("$(wildcard $(LOCAL_UV_CHECK))","")
    UV := $(LOCAL_UV)
else ifneq ($(GLOBAL_UV_TEST),)
    UV := uv
else
    UV := MISSING
endif

ifeq ($(UV),MISSING)
    RUN      := @$(MAKE) --no-print-directory check-uv && uv run
    RUFF     := @$(MAKE) --no-print-directory check-uv && uv run ruff
    PYTEST   := @$(MAKE) --no-print-directory check-uv && uv run pytest
    SYNC     := @$(MAKE) --no-print-directory check-uv && uv sync
else
    RUN      := $(UV) run
    RUFF     := $(RUN) ruff
    PYTEST   := $(RUN) pytest
    SYNC     := $(UV) sync
endif

# --- TARGETS ---

.PHONY: help install up down run-async test lint format clean build build-no-cache install-uv-user install-uv-project start

## Show this help message
help:
	@echo Usage: make [target]
	@echo.
	@echo Targets:
ifeq ($(OS_TYPE),Windows)
	@powershell -NoProfile -ExecutionPolicy Bypass -Command " \
		Get-Content $(MAKEFILE_LIST) | \
		Where-Object { $$_ -match '^[a-zA-Z0-9_-]+:.*?##' } | \
		ForEach-Object { \
			$$parts = $$_ -split ':.*?## '; \
			'  {0,-20} {1}' -f $$parts[0].Trim(), $$parts[1].Trim() \
		}"
else
	@grep -E '^[a-zA-Z0-9_-]+:.*?##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
endif

## Build, start infrastructure and run the crawler (Complete Cycle)
start: build up
	@echo "Waiting for services to stabilize (5s)..."
	@$(if $(filter Windows,$(OS_TYPE)),timeout /t 5 /nobreak > nul,sleep 5)
	@$(MAKE) --no-print-directory run-async

## Install dependencies using uv sync
install:
	@echo "Syncing dependencies..."
	@$(SYNC)

## Start Docker infrastructure (Database, Redis, Grafana)
up:
	@echo "Starting infrastructure (Cleaning old containers)..."
	@docker-compose up -d --remove-orphans

## Stop Docker infrastructure
down:
	@docker-compose down

## Run the crawler in asynchronous mode
run-async:
	@echo "Launching crawler..."
	@$(RUN) $(PYTHON) main.py

## Run the optimized test suite
test:
	@echo "Running tests..."
	@$(PYTEST) tests/ -v

## Check code quality with Ruff
lint:
	@echo "Checking linting..."
	@$(RUFF) check .

## Format code according to project standards
format:
	@echo "Formatting code..."
	@$(RUFF) format .

## Deep clean project caches and temporary files
clean:
	@echo "Cleaning up for $(OS_TYPE)..."
ifeq ($(OS_TYPE),Windows)
	@if exist .pytest_cache $(RM) .pytest_cache
	@if exist .ruff_cache $(RM) .ruff_cache
	@for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
else
	@rm -rf .pytest_cache .ruff_cache
	@find . -type d -name "__pycache__" -exec rm -rf {} +
endif
	@echo "Cleanup complete."

## Build Docker images
build:
	@echo "Building Docker images..."
	@docker-compose build

## Build Docker images without cache (Use this if files are missing in container)
build-no-cache:
	@echo "Building Docker images (forcing no-cache)..."
	@docker-compose build --no-cache

## [SETUP] Install uv globally for the current user
install-uv-user:
ifeq ($(OS_TYPE),Windows)
	@echo "Iniciando instalacao global robusta..."
	@powershell -NoProfile -ExecutionPolicy Bypass -Command " \
		$$uv_dir = \"$$env:APPDATA\uv\bin\"; \
		if (!(Test-Path $$uv_dir)) { New-Item -ItemType Directory -Path $$uv_dir -Force | Out-Null }; \
		echo 'Baixando binarios do uv...'; \
		curl.exe -L https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip -o uv_global.zip; \
		tar.exe -xf uv_global.zip; \
		if (Test-Path 'uv-x86_64-pc-windows-msvc') { \
			Move-Item 'uv-x86_64-pc-windows-msvc\uv*.exe' $$uv_dir -Force; \
			Remove-Item 'uv-x86_64-pc-windows-msvc' -Recurse -Force; \
		} else { \
			Move-Item 'uv*.exe' $$uv_dir -Force; \
		}; \
		Remove-Item 'uv_global.zip' -Force; \
		echo '----------------------------------------------------------------'; \
		echo 'INSTALACAO GLOBAL CONCLUIDA!'; \
		Write-Host Local: + $$uv_dir; \
		echo ''; \
		echo 'IMPORTANTE: Verifique se este caminho esta no seu PATH.'; \
		echo 'Se nao estiver, rode o comando abaixo no PowerShell (ADMIN) para corrigir:'; \
		echo ''; \
		$$path_cmd = \"[Environment]::SetEnvironmentVariable(`\"Path`\", [Environment]::GetEnvironmentVariable(`\"Path`\", `\"User`\") + `\";$$uv_dir`\", `\"User`\")\"; \
    Write-Host $$path_cmd; \
		echo ''; \
		echo '----------------------------------------------------------------';"
else
	@curl -LsSf https://astral.sh/uv/install.sh | sh
endif

## [SETUP] Install uv only inside the project root
install-uv-project:
ifeq ($(OS_TYPE),Windows)
	@echo "Downloading uv.exe to project root..."
	@curl.exe -L https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip -o uv.zip
	@tar.exe -xf uv.zip
	@move /y uv-x86_64-pc-windows-msvc\uv.exe .\uv.exe
	@move /y uv-x86_64-pc-windows-msvc\uvw.exe .\uvw.exe
	@move /y uv-x86_64-pc-windows-msvc\uvx.exe .\uvx.exe
	@rmdir /s /q uv-x86_64-pc-windows-msvc
	@del uv.zip
	@echo "uv.exe is now in your project root."
else
	@curl -L https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz -o uv.tar.gz
	@tar -xzf uv.tar.gz
	@mv uv-x86_64-unknown-linux-gnu/uv ./uv
	@rm -rf uv-x86_64-unknown-linux-gnu uv.tar.gz
	@chmod +x ./uv
endif

# Internal helper to check for uv
check-uv:
ifeq ($(UV),MISSING)
	@echo.
	@echo  ================================================================
	@echo   AVISO: O utilitario 'uv' nao foi encontrado! (OS: $(OS_TYPE))
	@echo  ================================================================
	@echo   Use o comando abaixo para instalar:
	@echo.
	@echo   make install-uv-user
	@echo  ================================================================
	@echo.
	@exit 1
endif
