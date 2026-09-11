#PORT := 8000
DA := django-admin
DC_FOLDER := contrib/docker
DC_FILE := ${DC_FOLDER}/docker-compose.yml
ENV_FILE := ${DC_FOLDER}/.env

DC = docker compose -f ${DC_FILE} --env-file ${ENV_FILE} --project-directory .

MNEMONIC = test test test test test test test test test test test test

build:
	${DC} build --force-rm backend

rebuild: build stop rm up

restart: stop rm up 

#up:
#	${DA} runserver 0.0.0.0:${PORT} &
#	sleep 3 && open http://localhost:${PORT}

up:
	${DC} up -d backend

stop:
	${DC} stop

rm:
	${DC} rm

#shell:
#	${DA} shell_plus
shell:
	${DC} exec -it backend bash

emergency-shell:
	${DC} run --rm -it backend bash 



ps:
	${DC} ps

logs:
	${DC} logs -f

static:
	${DA} collectstatic --clear

migrate:
	${DA} makemigrations
	${DA} migrate

cli:
	${DA} cli

cli_help:
	${DA} cli --help

.PHONY: test
test:
	${DA} test test_mpst

ganache:
	npx ganache --db ./ganache_data --mnemonic "${MNEMONIC}" --accounts 5 --defaultBalanceEther 10000

init_data:
	env | grep DJANGO && ${DC} exec -it backend django-admin createsuperuser --noinput --username "$${DJANGO_SUPERUSER_USERNAME}" --email "$${DJANGO_SUPERUSER_EMAIL}"
