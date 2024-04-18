.PHONY: build install clean test

build:
	python -m build

install:
	if [ -d "archives" ]; then mv -n "archives" ".archives"; fi
	pip install -e .
	if [ -d ".archives" ]; then mv -n ".archives" "archives"; fi


clean:
	rm -rf build dist *.egg-info
	pip uninstall broadcastify-cli 

test:
	pytest tests/