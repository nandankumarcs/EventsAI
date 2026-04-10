SHELL := /bin/bash

BACKEND_DIR := backend
VENV        := $(BACKEND_DIR)/.venv
PYTHON      := $(VENV)/bin/python

# Configurable network port params
HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: start build-frontend migrate runserver

## Build the React frontend and start the Django backend server (one command)
start:
	@bash start.sh

## Apply any pending Django migrations
migrate:
	@echo "→ Applying migrations..."
	$(PYTHON) $(BACKEND_DIR)/manage.py migrate

## Start only the Django development server (no frontend build)
runserver:
	@echo "→ Starting Django server at http://$(HOST):$(PORT)"
	$(PYTHON) $(BACKEND_DIR)/manage.py runserver $(HOST):$(PORT)
