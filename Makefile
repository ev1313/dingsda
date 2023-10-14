help:
	cat Makefile

test:
	python -m pytest --benchmark-disable --showlocals

verbose:
	python -m pytest --benchmark-disable --showlocals --verbose

xfails:
	python -m pytest --benchmark-disable --verbose | egrep --color=always "xfail|XFAIL|xpass|XPASS"

cover:
	python -m pytest --benchmark-disable --cov construct --cov-report html --cov-report term --verbose

bench:
	python -m pytest --benchmark-enable --benchmark-columns=min,stddev --benchmark-sort=name --benchmark-compare

benchsave:
	python -m pytest --benchmark-enable --benchmark-columns=min,stddev --benchmark-sort=name --benchmark-compare --benchmark-autosave

html:
	cd docs; make html

installdeps:
	apt-get install python python3-pip python3-sphinx --upgrade
	python -m pip install pytest pytest-benchmark pytest-cov twine wheel --upgrade
	python -m pip install enum34 numpy arrow ruamel.yaml cloudpickle lz4 cryptography --upgrade

version:
	./version-increment

upload:
	python ./setup.py sdist bdist_wheel
	python -m twine check dist/*
	python -m twine upload dist/*

