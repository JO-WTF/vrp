#!/usr/bin/env bash
# Build and deploy VRP Studio frontend and backend in one step.
# Usage: ./vrp-studio/deploy.sh [--clean] [--no-start] [--port PORT]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
BACKEND_STATIC_DIR="$SCRIPT_DIR/vrp_studio/frontend"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
USE_UV=false
CLEAN=false
START_SERVER=true
PORT=8000

while [[ $# -gt 0 ]]; do
    case "$1" in
        --clean) CLEAN=true; shift ;;
        --no-start) START_SERVER=false; shift ;;
        --port)
            PORT="${2:-}"
            if [[ -z "$PORT" ]]; then
                echo "ERROR: --port requires a value"
                exit 1
            fi
            shift 2
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if command -v uv >/dev/null 2>&1; then
    USE_UV=true
fi

ensure_venv() {
    if [[ "$USE_UV" == true && ! -f "$VENV_PYTHON" ]]; then
        echo "Creating .venv with uv..."
        (cd "$ROOT_DIR" && uv venv .venv)
    elif [[ ! -f "$VENV_PYTHON" ]]; then
        echo "Creating .venv with python..."
        python -m venv "$ROOT_DIR/.venv"
    fi
}

ensure_pip() {
    if ! "$VENV_PYTHON" -m pip --version >/dev/null 2>&1; then
        echo "Bootstrapping pip with ensurepip..."
        "$VENV_PYTHON" -m ensurepip --upgrade
    fi
}

install_python_deps() {
    echo "Installing VRP Studio Python dependencies..."
    if [[ "$USE_UV" == true ]]; then
        uv pip install --python "$VENV_PYTHON" -r "$SCRIPT_DIR/requirements.txt" -q
    else
        ensure_pip
        "$VENV_PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt" -q
    fi
}

install_backend() {
    echo "Installing vrp-studio package in editable mode..."
    if [[ "$USE_UV" == true ]]; then
        uv pip install --python "$VENV_PYTHON" --no-deps -e "$SCRIPT_DIR" -q
    else
        ensure_pip
        "$VENV_PYTHON" -m pip install --no-deps -e "$SCRIPT_DIR" -q
    fi
}

build_frontend() {
    if ! command -v npm >/dev/null 2>&1; then
        echo "ERROR: npm not found in PATH. Please install Node.js/npm to build the frontend."
        exit 1
    fi

    echo "Building VRP Studio frontend..."
    if [[ "$CLEAN" == true ]]; then
        rm -rf "$FRONTEND_DIR/dist" "$BACKEND_STATIC_DIR/dist"
    fi

    if [[ -f "$FRONTEND_DIR/package-lock.json" ]]; then
        (cd "$FRONTEND_DIR" && npm ci && npm run build)
    else
        (cd "$FRONTEND_DIR" && npm install && npm run build)
    fi

    echo "Deploying frontend assets into backend package..."
    mkdir -p "$BACKEND_STATIC_DIR"
    rm -rf "$BACKEND_STATIC_DIR/dist"
    cp -R "$FRONTEND_DIR/dist" "$BACKEND_STATIC_DIR/dist"
}

start_server() {
    echo "Starting VRP Studio on http://127.0.0.1:$PORT ..."
    if [[ "$USE_UV" == true ]]; then
        cd "$ROOT_DIR"
        uv run --python "$VENV_PYTHON" vrp-studio --port "$PORT"
    else
        "$VENV_PYTHON" -m vrp_studio.server --port "$PORT"
    fi
}

ensure_venv
install_python_deps
install_backend
build_frontend

if [[ "$START_SERVER" == true ]]; then
    start_server
else
    echo "Build/deploy complete. Start later with: uv run --python $VENV_PYTHON vrp-studio --port $PORT"
fi
