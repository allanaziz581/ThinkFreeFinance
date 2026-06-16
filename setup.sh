#!/usr/bin/env bash
# ThinkFree Finance — Environment Setup Script
# Creates tf_env (Python 3.10) venv with all dependencies.
# Usage: bash setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$SCRIPT_DIR/tf_env"
PY310_CONDA="/Users/allanaziz/.conda/envs/pythonProject1/bin/python3.10"

echo ""
echo "======================================================"
echo "  ThinkFree Finance — Setup"
echo "======================================================"
echo ""

# -----------------------------------------------------------
# Resolve Python 3.10
# -----------------------------------------------------------
if [ -x "$PY310_CONDA" ]; then
    PYTHON="$PY310_CONDA"
elif command -v python3.10 &>/dev/null; then
    PYTHON="$(command -v python3.10)"
else
    echo "ERROR: Python 3.10 not found. Install via conda or pyenv." >&2
    exit 1
fi

PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python: $PYTHON ($PY_VERSION)"

# -----------------------------------------------------------
# Create venv
# -----------------------------------------------------------
if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment at tf_env/ ..."
    "$PYTHON" -m venv "$VENV"
else
    echo "Virtual environment already exists at tf_env/"
fi
PYTHON="$VENV/bin/python"

# -----------------------------------------------------------
# Create .env if missing
# -----------------------------------------------------------
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "Created .env from .env.example — add your API keys before running the pipeline."
    else
        cat > .env <<'EOF'
OPENAI_API_KEY=
FINNHUB_API_KEY=
SEC_API_KEY=
QUANDL_API_KEY=
QUIVERQUANT_API_KEY=
FRED_API_KEY=
EOF
        echo "Created blank .env — add your API keys before running the pipeline."
    fi
else
    echo ".env already exists — skipping creation."
fi

# -----------------------------------------------------------
# Install Python dependencies
# -----------------------------------------------------------
echo ""
echo "Installing Python packages (this may take a few minutes)..."
$PYTHON -m pip install --upgrade pip --quiet
# Pin numpy<2 first (torch 2.2.x requires numpy 1.x on this platform)
$PYTHON -m pip install "numpy<2" --quiet
# Pin sentence-transformers + transformers to compatible versions
$PYTHON -m pip install "sentence-transformers==2.7.0" "transformers==4.41.2" --quiet
$PYTHON -m pip install -r requirements.txt --quiet

echo "Core packages installed."

# -----------------------------------------------------------
# Download spaCy language model (needed for Phase 3 NER)
# -----------------------------------------------------------
echo ""
echo "Downloading spaCy English model (en_core_web_sm)..."
$PYTHON -m spacy download en_core_web_sm --quiet 2>/dev/null || \
    echo "  [WARN] spaCy model download failed. NER will use fallback. Run manually: python -m spacy download en_core_web_sm"

# -----------------------------------------------------------
# Create required output directories
# -----------------------------------------------------------
echo ""
echo "Creating output directories..."
mkdir -p news_output
mkdir -p Module_2_Technical_Analysis/results_run
mkdir -p dashboard
mkdir -p agents
mkdir -p GPT_Economy/Intelligence_layer\ \(IN\ PROGRESS\)

echo "Directories ready."

# -----------------------------------------------------------
# Run validate_env.py
# -----------------------------------------------------------
echo ""
echo "Running environment validation..."
if [ -f "validate_env.py" ]; then
    $PYTHON validate_env.py
else
    echo "  validate_env.py not found — skipping validation."
fi

echo ""
echo "======================================================"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Edit .env and add your API keys"
echo "  2. Run: python validate_env.py   (check readiness)"
echo "  3. Run: ./tf_env/bin/python controller.py     (full pipeline)"
echo "  4. Run: ./tf_env/bin/streamlit run dashboard/app.py"
echo "======================================================"
echo ""
