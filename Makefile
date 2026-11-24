PY ?= ./venv/bin/python

.PHONY: dev migrate admin test e2e lint format images vendor

dev:            ## run the development server with auto-reload
	$(PY) -m uvicorn app.main:app --reload --port 8000

migrate:        ## apply database migrations
	$(PY) -m alembic upgrade head

admin:          ## create an admin account: make admin EMAIL=you@example.com
	$(PY) -m scripts.create_admin $(EMAIL)

test:           ## backend tests
	$(PY) -m pytest -m "not browser"

e2e:            ## browser tests (uses local Google Chrome; PW_CHANNEL="" for bundled Chromium)
	$(PY) -m pytest -m browser

lint:
	$(PY) -m ruff check . && $(PY) -m ruff format --check .

format:
	$(PY) -m ruff format . && $(PY) -m ruff check . --fix

images:         ## regenerate optimised images from assets/source
	$(PY) scripts/build_images.py

vendor:         ## copy npm packages into app/static/vendor and fonts
	npm ci && npm run vendor
