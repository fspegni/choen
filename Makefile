PORT = 8000
DC = django-admin

MNEMONIC = test test test test test test test test test test test test

up:
	${DC} runserver 0.0.0.0:${PORT} &
	sleep 3 && open http://localhost:${PORT}

shell:
	${DC} shell_plus

static:
	${DC} collectstatic --clear

migrate:
	${DC} makemigrations
	${DC} migrate

cli:
	${DC} cli

cli_help:
	${DC} cli --help

.PHONY: test
test:
	${DC} test test_mpst

ganache:
	npx ganache --db ./ganache_data --mnemonic "${MNEMONIC}" --accounts 5 --defaultBalanceEther 10000

