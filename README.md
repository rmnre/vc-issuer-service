# Issuer Service

## Configure
Edit the following files:
- compose.yaml
- Dockerfile
- config/
  - agent-config.yaml
  - webapp-config.yaml
  - agent.env
  - webapp.env

## Build
```shell
docker compose build
```

## Run
```shell
docker compose up -d
```

## Follow logs
```shell
docker compose logs -f
```

## Stop and remove
```shell
docker compose down
```

## Stop and keep containers
```shell
docker compose stop
```
