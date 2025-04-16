PORT = 8000
DC = django-admin

up:
	${DC} runserver 0.0.0.0:${PORT}

shell:
	${DC} shell_plus

static:
	${DC} collectstatic -clear

migrate:
	${DC} makemigrations
	${DC} migrate

cli:
	${DC} cli

.PHONY: test
test:
	${DC} test test_mpst
