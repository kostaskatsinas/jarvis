COMPOSE      = docker compose
COMPOSE_DEV  = $(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml

.PHONY: prod prod-home dev down logs ps secrets

## Production on the VPS (no Ollama)
prod:
	$(COMPOSE) up -d --build

## Production on the home server (adds Ollama)
prod-home:
	$(COMPOSE) --profile local-llm up -d --build

## Local development: backend (hot reload) + Vite dev server + Postgres.
## Add langfuse-web etc. to the list if you need tracing locally.
dev:
	$(COMPOSE_DEV) up --build backend postgres frontend-dev

down:
	$(COMPOSE) --profile local-llm down

logs:
	$(COMPOSE) logs -f --tail=100 $(S)

ps:
	$(COMPOSE) ps

## Print fresh values for every secret in .env.example
secrets:
	@for k in JARVIS_SECRET_KEY POSTGRES_PASSWORD LANGFUSE_SALT \
	  LANGFUSE_ENCRYPTION_KEY LANGFUSE_NEXTAUTH_SECRET CLICKHOUSE_PASSWORD \
	  REDIS_PASSWORD MINIO_ROOT_PASSWORD; do \
	  echo "$$k=$$(openssl rand -hex 32)"; \
	done; \
	echo "LANGFUSE_PUBLIC_KEY=pk-lf-$$(openssl rand -hex 16)"; \
	echo "LANGFUSE_SECRET_KEY=sk-lf-$$(openssl rand -hex 16)"
