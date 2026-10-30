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

ganache-restart:
	${DC} restart ganache

ganache-wipe:
	${DC} down --volume ganache

#up:
#	${DA} runserver 0.0.0.0:${PORT} &
#	sleep 3 && open http://localhost:${PORT}

up:
	${DC} up -d

stop:
	${DC} stop

rm:
	${DC} rm

shell-old:
	${DA} shell_plus

shell:
	${DC} exec -it backend bash

ganache-shell:
	${DC} exec -it ganache bash


emergency-shell:
	${DC} run --rm -it backend bash 



ps:
	${DC} ps

logs:
	${DC} logs -f

static:
	${DC} exec -it backend ${DA} collectstatic --noinput --clear

migrate:
	#${DA} makemigrations
	#${DA} migrate
	${DC} exec -it backend ${DA} makemigrations
	${DC} exec -it backend ${DA} migrate

migrate-old:
	${DA} makemigrations
	${DA} migrate

cli:
	#${DA} cli
	${DC} exec -it backend ${DA} cli

cli-old:
	${DA} cli

cli_help:
	${DA} cli --help

.PHONY: test
test:
	${DA} test test_mpst

ganache:
	npx ganache --db ./ganache_data --mnemonic "${MNEMONIC}" --accounts 5 --defaultBalanceEther 10000

init: up static
	${DC} exec -it backend ${DA} loaddata /app/data/initial/fixtures.json
	${DC} exec -it backend tar zxvf /app/data/initial/fixtures_media.tar.gz -C /app/public

fixtures-create:
	${DC} exec backend ${DA} dumpdata mpst.MPST auth.User sites.Site bpmn_parser.Choreography engine.Configuration --indent 2 -o data/initial/fixtures.json

wipe: stop rm
	${DC} down --volumes
