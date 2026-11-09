.PHONY: dev down seed migrate test lint benchmark

dev:
	docker compose up --build -d

down:
	docker compose down

migrate:
	cd backend && alembic upgrade head

seed:
	cd backend && python -m app.scripts.seed --customers 10000 --leads 200000 --activities 500000

test:
	cd backend && pytest -v
	cd frontend && npm run test -- --run

lint:
	cd backend && ruff check app tests && mypy app
	cd frontend && npm run lint

benchmark:
	cd backend && python -m app.scripts.benchmark_async
	cd backend && python -m app.scripts.benchmark_pagination

