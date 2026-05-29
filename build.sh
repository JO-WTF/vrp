#!/bin/bash
# Build Rust workspace and Python packages in one step
# Usage: ./build.sh [options]
# Options:
#   --clean     Remove build artifacts before building
#   --debug     Build in debug mode (default: release)
#   --no-python Skip Python wheel build and install
#   --no-rust   Skip Rust build

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
USE_UV=false

# Parse arguments
CLEAN=false
DEBUG=false
NO_PYTHON=false
NO_RUST=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --clean) CLEAN=true; shift ;;
        --debug) DEBUG=true; shift ;;
        --no-python) NO_PYTHON=true; shift ;;
        --no-rust) NO_RUST=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

BUILD_PROFILE=$([ "$DEBUG" = true ] && echo "debug" || echo "release")
CARGO_ARGS=$([ "$DEBUG" = true ] && echo "" || echo "--release")

echo "=== VRP Build Script ==="
echo "Root directory: $ROOT_DIR"
echo "Build profile: $BUILD_PROFILE"
echo ""

# Check prerequisites
if command -v uv >/dev/null 2>&1; then
    USE_UV=true
fi

if [ "$USE_UV" = true ] && [ ! -f "$VENV_PYTHON" ]; then
    echo "Python virtual environment not found; creating .venv with uv..."
    cd "$ROOT_DIR"
    uv venv .venv
elif [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Python virtual environment not found at $VENV_PYTHON"
    echo "Please create a .venv with: uv venv .venv (or python -m venv .venv)"
    exit 1
fi


ensure_pip() {
    if ! "$VENV_PYTHON" -m pip --version >/dev/null 2>&1; then
        echo "  pip not found in .venv; bootstrapping with ensurepip..."
        if ! "$VENV_PYTHON" -m ensurepip --upgrade >/dev/null 2>&1; then
            echo "ERROR: pip is not available in $VENV_PYTHON and ensurepip failed."
            echo "Please install uv, recreate the environment with pip, or install python3-venv/python ensurepip support."
            exit 1
        fi
    fi
}

# Step 1: Clean (optional)
if [ "$CLEAN" = true ]; then
    echo "Step 1: Cleaning build artifacts..."
    rm -rf "$ROOT_DIR/target" 2>/dev/null || true
    rm -rf "$ROOT_DIR/vrp-cli/target" 2>/dev/null || true
    echo "  Clean complete."
    echo ""
fi

# Step 2: Build Rust workspace (unless skipped)
if [ "$NO_RUST" != true ]; then
    echo "Step 2: Building Rust workspace ($BUILD_PROFILE)..."
    cd "$ROOT_DIR"
    if command -v cargo &> /dev/null; then
        cargo build $CARGO_ARGS --all
    else
        echo "ERROR: cargo not found in PATH"
        exit 1
    fi
    echo "  Rust build complete."
    echo ""
fi

# Step 3: Build and install Python package (unless skipped)
if [ "$NO_PYTHON" != true ]; then
    echo "Step 3: Building Python wheel with maturin..."

    cd "$ROOT_DIR/vrp-cli"
    echo "  Installing Python build dependencies from vrp-cli/requirements.txt..."
    if [ "$USE_UV" = true ]; then
        uv pip install --python "$ROOT_DIR/.venv/bin/python" -r "$ROOT_DIR/vrp-cli/requirements.txt" -q
        uv run --python "$ROOT_DIR/.venv/bin/python" maturin build --release
    else
        ensure_pip
        "$VENV_PYTHON" -m pip install -r "$ROOT_DIR/vrp-cli/requirements.txt" -q
        "$VENV_PYTHON" -m maturin build --release
    fi
    echo "  Python wheel build complete."
    echo ""
    
    echo "Step 4: Installing Python wheel..."
    WHEEL_FILE=$(ls -t "$ROOT_DIR/target/wheels/vrp_cli-"*.whl 2>/dev/null | head -1)
    if [ -z "$WHEEL_FILE" ]; then
        echo "ERROR: No .whl file found at $ROOT_DIR/target/wheels/"
        exit 1
    fi
    
    echo "  Installing from: $(basename $WHEEL_FILE)"
    if [ "$USE_UV" = true ]; then
        uv pip install --python "$ROOT_DIR/.venv/bin/python" "$WHEEL_FILE" --reinstall -q
    else
        ensure_pip
        "$VENV_PYTHON" -m pip install "$WHEEL_FILE" --force-reinstall -q
    fi
    echo "  Installation complete."
    echo ""
fi

# Step 5: Verification
echo "Step 5: Verifying installation..."
if [ "$USE_UV" = true ]; then
    uv run --python "$ROOT_DIR/.venv/bin/python" python -c "import vrp_cli; print('vrp_cli module imported successfully'); print([x for x in dir(vrp_cli) if not x.startswith('_')])" || true
else
    $VENV_PYTHON -c "import vrp_cli; print('vrp_cli module imported successfully'); print([x for x in dir(vrp_cli) if not x.startswith('_')])" || true
fi

echo ""
echo "=== Build Complete ==="
echo "Next steps:"
echo "  - Test with: python examples/python-interop/run_pragmatic_example.py --list"
echo "  - Run example: python examples/python-interop/run_pragmatic_example.py simple.basic.problem.json"
echo "  - Run all:    python examples/python-interop/run_pragmatic_example.py --all"
