#!/bin/bash

# Jellyfin Manager - Environment Setup Script
# Interactive script for managing Python environment and dependencies

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

# Function to show main menu
show_menu() {
    echo ""
    echo "========================================="
    echo "Jellyfin Manager - Environment Setup"
    echo "========================================="
    echo ""
    echo -e "${BLUE}Project Directory:${NC} $PROJECT_DIR"
    echo ""
    echo "Please select an option:"
    echo ""
    echo -e "  ${CYAN}1)${NC} Full Setup - Install Python 3.13 and all dependencies"
    echo -e "  ${CYAN}2)${NC} Update Libraries - Check for and install updates"
    echo -e "  ${CYAN}3)${NC} Verify Dependencies - Check all packages are installed"
    echo -e "  ${CYAN}4)${NC} Exit"
    echo ""
    echo -n "Enter your choice [1-4]: "
}

# Function to check Python version and verify it works
check_python_version() {
    local python_cmd=$1
    if command -v "$python_cmd" &> /dev/null; then
        # Check version
        local version=$("$python_cmd" --version 2>&1 | grep -oP '\d+\.\d+\.\d+')
        if [[ "$version" == 3.13.* ]]; then
            # Verify Python actually works by running multiple checks
            if "$python_cmd" -c "import sys, encodings; print('OK')" &> /dev/null; then
                # Also verify it can create a basic venv
                local test_venv="/tmp/test_venv_$$"
                if "$python_cmd" -m venv "$test_venv" 2>/dev/null; then
                    rm -rf "$test_venv"
                    echo "$python_cmd"
                    return 0
                else
                    rm -rf "$test_venv" 2>/dev/null
                    echo -e "${YELLOW}Warning: $python_cmd version $version found but cannot create venv, skipping...${NC}" >&2
                fi
            else
                echo -e "${YELLOW}Warning: $python_cmd version $version found but appears broken (missing encodings), skipping...${NC}" >&2
            fi
        fi
    fi
    return 1
}

# Function to install Python via conda
install_python_conda() {
    echo -e "${YELLOW}Attempting to install Python 3.13 via conda...${NC}"

    # Check if conda is available
    if command -v conda &> /dev/null; then
        echo -e "${BLUE}Found conda, installing Python 3.13...${NC}"

        # Use only conda-forge to avoid TOS issues with default channels
        if conda install -y python=3.13.11 --override-channels -c conda-forge 2>/dev/null || \
           conda install -y "python>=3.13,<3.14" --override-channels -c conda-forge; then
            return 0
        else
            return 1
        fi
    elif command -v mamba &> /dev/null; then
        echo -e "${BLUE}Found mamba, installing Python 3.13...${NC}"
        if mamba install -y python=3.13.11 -c conda-forge 2>/dev/null || \
           mamba install -y "python>=3.13,<3.14" -c conda-forge; then
            return 0
        else
            return 1
        fi
    else
        echo -e "${YELLOW}conda/mamba not found${NC}"
        return 1
    fi
}

# Function to download and install standalone Python
install_python_standalone() {
    echo -e "${YELLOW}Attempting to install Python 3.13.11 standalone build...${NC}" >&2

    local python_dir="$PROJECT_DIR/.python"
    mkdir -p "$python_dir"

    # Detect architecture
    local arch=$(uname -m)
    local os=$(uname -s | tr '[:upper:]' '[:lower:]')

    if [[ "$os" == "linux" ]]; then
        if [[ "$arch" == "x86_64" ]]; then
            local python_url="https://github.com/indygreg/python-build-standalone/releases/download/20251205/cpython-3.13.11+20251205-x86_64-unknown-linux-gnu-install_only.tar.gz"
        else
            echo -e "${RED}Unsupported architecture: $arch${NC}" >&2
            return 1
        fi
    else
        echo -e "${RED}Unsupported OS: $os${NC}" >&2
        return 1
    fi

    echo -e "${BLUE}Downloading Python from: $python_url${NC}" >&2
    local temp_file=$(mktemp)
    if curl -L -o "$temp_file" "$python_url" 2>&1 | grep -E "^\s*[0-9]+" >&2; then
        echo -e "${BLUE}Extracting Python...${NC}" >&2
        tar -xzf "$temp_file" -C "$python_dir" --strip-components=1 2>&2
        rm "$temp_file"

        # Check if extraction was successful
        if [ -f "$python_dir/bin/python3" ]; then
            if ! "$python_dir/bin/python3" -c "import sys; assert sys.version_info[:3] == (3, 13, 11)" &> /dev/null; then
                echo -e "${RED}Extracted Python version mismatch; expected 3.13.11${NC}" >&2
                return 1
            fi
            echo "$python_dir/bin/python3"
            return 0
        fi
    fi

    echo -e "${RED}Failed to download/extract Python${NC}" >&2
    return 1
}

# Function to ensure venv exists and is activated
ensure_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${RED}Virtual environment not found!${NC}"
        echo -e "${YELLOW}Please run 'Full Setup' first (option 1)${NC}"
        return 1
    fi

    if [ -z "$VIRTUAL_ENV" ] || [ "$VIRTUAL_ENV" != "$VENV_DIR" ]; then
        if [ -n "$VIRTUAL_ENV" ]; then
            echo -e "${YELLOW}Warning: Another virtual environment is active (${VIRTUAL_ENV}).${NC}"
            echo -e "${YELLOW}Switching to project venv: $VENV_DIR${NC}"
        else
            echo -e "${BLUE}Activating virtual environment...${NC}"
        fi
        source "$VENV_DIR/bin/activate"
    fi

    if [ ! -x "$VENV_PYTHON" ]; then
        echo -e "${RED}Virtual environment Python not found at $VENV_PYTHON${NC}"
        return 1
    fi
    echo -e "${BLUE}Active venv python: $VENV_PYTHON${NC}"
    echo -e "${BLUE}Shell python resolves to: $(command -v python)${NC}"
    return 0
}

venv_pip() {
    "$VENV_PYTHON" -m pip "$@"
}

# Function to check for updates
check_updates() {
    echo ""
    echo "========================================="
    echo "Checking for Updates"
    echo "========================================="
    echo ""

    if ! ensure_venv; then
        return 1
    fi

    echo -e "${YELLOW}Checking for package updates...${NC}"
    echo ""

    # Get list of outdated packages
    outdated=$(venv_pip list --outdated --format=json 2>/dev/null)

    if [ "$outdated" == "[]" ] || [ -z "$outdated" ]; then
        echo -e "${GREEN}✓ All packages are up to date!${NC}"

        # Check Python version
        echo ""
        echo -e "${YELLOW}Checking Python version...${NC}"
        current_python=$(python --version 2>&1 | grep -oP '\d+\.\d+\.\d+')
        echo -e "${BLUE}Current Python version: $current_python${NC}"
        return 0
    fi

    # Parse and display outdated packages
    echo -e "${YELLOW}The following packages have updates available:${NC}"
    echo ""
    echo "$outdated" | "$VENV_PYTHON" -c "
import sys, json
data = json.load(sys.stdin)
for pkg in data:
    print(f\"  {pkg['name']:30s} {pkg['version']:15s} -> {pkg['latest_version']}\")
"

    echo ""
    echo -n "Do you want to update these packages? [y/N]: "
    read -r response

    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo ""
        echo -e "${BLUE}Updating packages...${NC}"
        venv_pip install --upgrade $(echo "$outdated" | "$VENV_PYTHON" -c "
import sys, json
data = json.load(sys.stdin)
print(' '.join([pkg['name'] for pkg in data]))
")
        echo ""
        echo -e "${GREEN}✓ Packages updated successfully!${NC}"
    else
        echo -e "${YELLOW}Update cancelled${NC}"
    fi
}

# Function to verify dependencies
verify_dependencies() {
    echo ""
    echo "========================================="
    echo "Verify Dependencies"
    echo "========================================="
    echo ""

    if ! ensure_venv; then
        return 1
    fi

    echo -e "${YELLOW}Checking dependencies from pyproject.toml...${NC}"
    echo ""

    # Use Python to parse pyproject.toml and check packages
    "$VENV_PYTHON" << 'PYEOF'
import sys
import tomllib
from pathlib import Path
import subprocess

# Colors
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
CYAN = '\033[0;36m'
NC = '\033[0m'

def get_installed_version(pkg_name):
    """Get installed version of a package, or None if not installed."""
    # Normalize package name for pip show
    normalized = pkg_name.lower().replace('_', '-').split('[')[0]
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'show', normalized],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.startswith('Version:'):
                    return line.split(':', 1)[1].strip()
    except Exception:
        pass
    return None

def parse_dep_name(dep):
    """Extract package name from dependency string like 'foo>=1.0' or 'bar[extra]'."""
    import re
    match = re.match(r'^([a-zA-Z0-9_-]+)', dep.replace('_', '-'))
    return match.group(1).lower() if match else dep.lower()

# Read pyproject.toml
pyproject_path = Path('pyproject.toml')
if not pyproject_path.exists():
    print(f"{RED}✗ pyproject.toml not found{NC}")
    sys.exit(1)

with open(pyproject_path, 'rb') as f:
    config = tomllib.load(f)

# Get dependencies
deps = config.get('project', {}).get('dependencies', [])
optional_deps = config.get('project', {}).get('optional-dependencies', {})

installed = []
missing = []

print(f"{CYAN}Core dependencies:{NC}")
for dep in deps:
    name = parse_dep_name(dep)
    version = get_installed_version(name)
    if version:
        installed.append((name, version))
        print(f"  {GREEN}✓{NC} {name} ({version})")
    else:
        missing.append(name)
        print(f"  {RED}✗{NC} {name} (missing)")

if optional_deps:
    print()
    print(f"{CYAN}Optional dependencies:{NC}")
    for group, group_deps in optional_deps.items():
        print(f"  [{group}]:")
        for dep in group_deps:
            name = parse_dep_name(dep)
            version = get_installed_version(name)
            if version:
                print(f"    {GREEN}✓{NC} {name} ({version})")
            else:
                print(f"    {YELLOW}○{NC} {name} (not installed)")

print()
if missing:
    print(f"{RED}✗ Missing core packages: {len(missing)}{NC}")
    for name in missing:
        print(f"  {name}")
else:
    print(f"{GREEN}✓ All core dependencies installed!{NC}")

# Summary
print()
print(f"{GREEN}Summary: {len(installed)} core packages installed, {len(missing)} missing{NC}")
PYEOF

    local exit_code=$?

    if [ $exit_code -ne 0 ]; then
        echo -e "${RED}Failed to verify dependencies${NC}"
        return 1
    fi

    # Offer to install missing
    echo ""
    echo -n "Install/update all dependencies? [y/N]: "
    read -r response

    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo ""
        echo -e "${BLUE}Installing dependencies from pyproject.toml...${NC}"
        venv_pip install -e ".[dev]"
        echo ""
        echo -e "${GREEN}✓ Dependencies installed/updated${NC}"
    fi
}

# Function for full setup
full_setup() {
    echo ""
    echo "========================================="
    echo "Full Setup"
    echo "========================================="
    echo ""

    # Step 1: Find or install Python 3.13
    echo -e "${YELLOW}[1/3] Checking for Python 3.13...${NC}"

    PYTHON_CMD=""

    # Initialize conda if it exists but isn't in PATH
    if [ -z "$(command -v conda)" ]; then
        for conda_path in \
            "$HOME/miniconda3/etc/profile.d/conda.sh" \
            "$HOME/anaconda3/etc/profile.d/conda.sh" \
            "/opt/conda/etc/profile.d/conda.sh" \
            "/opt/miniconda3/etc/profile.d/conda.sh" \
            "$HOME/.conda/etc/profile.d/conda.sh"; do
            if [ -f "$conda_path" ]; then
                echo -e "${BLUE}Found conda at: $conda_path${NC}"
                source "$conda_path"
                break
            fi
        done
    fi

    # First, try to install via conda if available (preferred method)
    if command -v conda &> /dev/null || command -v mamba &> /dev/null; then
        echo -e "${BLUE}Conda/Mamba detected, installing Python 3.13...${NC}"
        if install_python_conda; then
            for py in python3.13 python3 python; do
                if PYTHON_CMD=$(check_python_version "$py"); then
                    echo -e "${GREEN}✓ Installed Python 3.13 via conda: $PYTHON_CMD${NC}"
                    break
                fi
            done
        fi
    else
        echo -e "${YELLOW}Conda/Mamba not detected in PATH${NC}"
    fi

    # If conda install failed or not available, try to find existing Python 3.13
    if [ -z "$PYTHON_CMD" ]; then
        echo -e "${YELLOW}Checking for existing Python 3.13...${NC}"
        for py in python3.13 python3 python; do
            if PYTHON_CMD=$(check_python_version "$py"); then
                echo -e "${GREEN}✓ Found Python 3.13: $PYTHON_CMD${NC}"
                break
            fi
        done
    fi

    # If still not found, try standalone as last resort
    if [ -z "$PYTHON_CMD" ]; then
        echo -e "${YELLOW}Python 3.13 not found. Downloading standalone build...${NC}"
        if PYTHON_CMD=$(install_python_standalone); then
            echo -e "${GREEN}✓ Installed Python 3.13 standalone: $PYTHON_CMD${NC}"
        else
            echo -e "${RED}Failed to install Python 3.13${NC}"
            echo ""
            echo "Please install Python 3.13 manually:"
            echo "  - Via conda: conda install python=3.13"
            echo "  - Or download from: https://www.python.org/downloads/"
            exit 1
        fi
    fi

    # Verify Python version
    PYTHON_VERSION=$("$PYTHON_CMD" --version)
    echo -e "${BLUE}Using: $PYTHON_VERSION${NC}"
    echo -e "${BLUE}Base interpreter: $PYTHON_CMD${NC}"
    echo ""

    # Step 2: Create virtual environment
    echo -e "${YELLOW}[2/3] Setting up virtual environment...${NC}"

    if [ -d "$VENV_DIR" ]; then
        echo -e "${YELLOW}Removing existing virtual environment...${NC}"
        rm -rf "$VENV_DIR"
    fi

    echo -e "${BLUE}Creating virtual environment at: $VENV_DIR${NC}"

    # Try creating venv with pip first
    if "$PYTHON_CMD" -m venv "$VENV_DIR" 2>/dev/null; then
        echo -e "${GREEN}✓ Virtual environment created${NC}"
    else
        # If that fails (missing ensurepip), create without pip and install manually
        echo -e "${YELLOW}ensurepip not available, creating venv without pip...${NC}"
        if ! "$PYTHON_CMD" -m venv --without-pip "$VENV_DIR" 2>/dev/null; then
            echo -e "${RED}Failed to create virtual environment${NC}"
            echo -e "${YELLOW}The Python installation appears to be broken or incomplete${NC}"
            echo ""
            echo "Attempting to download and install a working Python 3.13..."

            # Remove the broken venv if it exists
            [ -d "$VENV_DIR" ] && rm -rf "$VENV_DIR"

            # Try standalone Python installation
            if PYTHON_CMD=$(install_python_standalone); then
                echo -e "${GREEN}✓ Installed working Python: $PYTHON_CMD${NC}"
                # Try creating venv again with the new Python
                if ! "$PYTHON_CMD" -m venv "$VENV_DIR" 2>/dev/null; then
                    echo -e "${RED}Still unable to create virtual environment${NC}"
                    exit 1
                fi
            else
                echo -e "${RED}Failed to install a working Python${NC}"
                exit 1
            fi
        fi

        # Activate and install pip manually
        source "$VENV_DIR/bin/activate"

        # Verify venv actually works
        if ! python -c "import sys; sys.exit(0)" 2>/dev/null; then
            echo -e "${RED}Virtual environment is broken${NC}"
            exit 1
        fi

        echo -e "${BLUE}Installing pip manually...${NC}"
        if ! curl -sS https://bootstrap.pypa.io/get-pip.py | python; then
            echo -e "${RED}Failed to install pip${NC}"
            exit 1
        fi

        if ! command -v pip &> /dev/null; then
            echo -e "${RED}pip is not available after installation${NC}"
            exit 1
        fi
        echo -e "${GREEN}✓ pip installed successfully${NC}"
    fi

    # Activate virtual environment
    source "$VENV_DIR/bin/activate"

    # Verify the venv is actually working and isolated
    if python -c "import sys; sys.exit(0 if 'site-packages' not in sys.prefix or sys.prefix.startswith('$VENV_DIR') else 1)" 2>/dev/null; then
        echo -e "${GREEN}✓ Virtual environment activated${NC}"
    else
        echo -e "${RED}Warning: Virtual environment may not be properly isolated${NC}"
    fi

    # Upgrade pip
    echo -e "${BLUE}Upgrading pip...${NC}"
    venv_pip install --upgrade pip

    echo -e "${GREEN}✓ Virtual environment ready${NC}"
    echo ""

    # Step 3: Install dependencies
    echo -e "${YELLOW}[3/3] Installing dependencies...${NC}"
    echo "This may take a few minutes..."

    cd "$PROJECT_DIR"

    # Install from pyproject.toml (editable mode)
    echo -e "${BLUE}Installing dependencies from pyproject.toml...${NC}"
    venv_pip install -e .

    echo -e "${GREEN}✓ Dependencies installed${NC}"
    echo ""

    # Verify installation
    echo -e "${YELLOW}Verifying installation...${NC}"
    python --version
    echo -e "${GREEN}✓ Setup complete!${NC}"
    echo ""

    echo "========================================="
    echo -e "${GREEN}Environment setup successful!${NC}"
    echo "========================================="
    echo ""
    echo "To run the application, use:"
    echo -e "  ${BLUE}./launch.sh${NC}"
    echo ""
    echo "Or manually activate the environment and run:"
    echo -e "  ${BLUE}source .venv/bin/activate${NC}"
    echo -e "  ${BLUE}python jellyfin_manager.py${NC}"
    echo ""
}

# Main script execution
main() {
    # If script is run with arguments, execute directly
    case "$1" in
        --full-setup)
            full_setup
            exit 0
            ;;
        --update)
            check_updates
            exit 0
            ;;
        --verify)
            verify_dependencies
            exit 0
            ;;
    esac

    # Interactive menu mode
    while true; do
        show_menu
        read -r choice

        case $choice in
            1)
                full_setup
                ;;
            2)
                check_updates
                ;;
            3)
                verify_dependencies
                ;;
            4)
                echo ""
                echo -e "${GREEN}Goodbye!${NC}"
                echo ""
                exit 0
                ;;
            *)
                echo ""
                echo -e "${RED}Invalid choice. Please enter 1-4.${NC}"
                ;;
        esac

        echo ""
        echo -n "Press Enter to return to menu..."
        read -r
    done
}

# Run main function
main "$@"
