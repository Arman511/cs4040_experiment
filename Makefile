UV ?= uv
R ?= Rscript
TIME_ARGS ?=
MEMORY_ARGS ?=

.PHONY: data test test-python test-java test-rust benchmark benchmark-time benchmark-memory analyse

data:
	$(UV) run scripts/generate_test_data.py

test: test-python test-java test-rust

test-python:
	$(UV) run python -m unittest discover -s python -p "test_*.py"

test-java:
	mvn -q -f java/pom.xml test

test-rust:
	cargo test --manifest-path rust/Cargo.toml

benchmark: data benchmark-time benchmark-memory

benchmark-time: 
	$(UV) run scripts/run_time.py $(TIME_ARGS)

benchmark-memory: 
	$(UV) run scripts/run_memory.py $(MEMORY_ARGS)

analyse:
	$(R) analysis/main.r
