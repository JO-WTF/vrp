# Building the Python Interop (`vrp-cli`)

The Python facade and its native bindings are built using [PyO3](https://pyo3.rs/) and [maturin](https://github.com/PyO3/maturin). 

## Local Development

If you want to build and test the Python bindings locally, you should use `maturin`.

### 1. Prerequisites
- **Python 3.10+**
- **Rust Toolchain** (latest stable)
- **maturin** (installed via `pip install maturin`)

### 2. Building

Navigate to the root directory where `Cargo.toml` is located (not just this folder, but the project root or the `vrp-cli` directory containing the `Cargo.toml`).

```bash
# To build a development unoptimized wheel and install it to your current environment
maturin develop --features py_bindings

# To build a production release wheel
maturin build --release --features py_bindings
```

### 3. Testing
Once built (using `maturin develop`), you can run the python tests:

```bash
# In the repository root
python -m unittest discover -s vrp-cli/python/tests
```

## CI/CD Pipeline

The repository currently has a GitHub Actions workflow `.github/workflows/maturin.yaml` which automatically builds cross-platform wheels for Linux, Windows, and macOS, and publishes them to PyPI upon a release.

To ensure everything stays clean during local development, you should periodically verify that the Python bindings compile successfully via:
```bash
cargo check --features py_bindings
```
