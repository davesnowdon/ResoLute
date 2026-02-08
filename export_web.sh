#!/bin/bash
# ResoLute Godot Web Export Script
# This script automates the export of the Godot project for web deployment
# Supports automatic detection and installation of export templates

set -e  # Exit on error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/ui"
BUILD_DIR="$SCRIPT_DIR/build/web"
GODOT_CMD="${GODOT_CMD:-godot}"
EXPORT_PRESET="${EXPORT_PRESET:-Web}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ResoLute Web Export Script${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if Godot is available
if ! command -v $GODOT_CMD &> /dev/null; then
    # Try alternative names
    for cmd in godot godot4 godot-4 Godot_v4*; do
        if command -v $cmd &> /dev/null; then
            GODOT_CMD=$cmd
            break
        fi
    done

    if ! command -v $GODOT_CMD &> /dev/null; then
        echo -e "${RED}Error: Godot not found in PATH${NC}"
        echo "Please install Godot 4.x or set GODOT_CMD environment variable"
        echo "Example: GODOT_CMD=/path/to/godot ./export_web.sh"
        exit 1
    fi
fi

# Get Godot version
GODOT_VERSION=$($GODOT_CMD --version 2>/dev/null | head -1)
echo -e "${YELLOW}Using Godot: $GODOT_VERSION${NC}"

# Extract version number (e.g., "4.6.stable" from "4.6.stable.official.89cea1439")
VERSION_SHORT=$(echo "$GODOT_VERSION" | grep -oE '^[0-9]+\.[0-9]+\.?[a-z]*' | head -1)
if [[ -z "$VERSION_SHORT" ]]; then
    VERSION_SHORT=$(echo "$GODOT_VERSION" | cut -d'.' -f1-2)
fi
echo -e "${BLUE}Version identifier: $VERSION_SHORT${NC}"

# Determine templates directory
if [[ "$OSTYPE" == "darwin"* ]]; then
    TEMPLATES_DIR="$HOME/Library/Application Support/Godot/export_templates/$VERSION_SHORT"
else
    TEMPLATES_DIR="$HOME/.local/share/godot/export_templates/$VERSION_SHORT"
fi

# Check if export templates exist
if [[ ! -f "$TEMPLATES_DIR/web_release.zip" ]]; then
    echo -e "${YELLOW}Export templates not found for Godot $VERSION_SHORT${NC}"
    echo -e "${YELLOW}Templates directory: $TEMPLATES_DIR${NC}"
    echo ""
    echo -e "${BLUE}To install export templates:${NC}"
    echo "  1. Open Godot Editor"
    echo "  2. Go to Editor -> Manage Export Templates"
    echo "  3. Click 'Download and Install'"
    echo ""
    echo -e "${BLUE}Or download manually from:${NC}"

    # Construct download URL based on version
    MAJOR_MINOR=$(echo "$VERSION_SHORT" | grep -oE '^[0-9]+\.[0-9]+')
    if [[ "$VERSION_SHORT" == *"stable"* ]]; then
        DOWNLOAD_URL="https://github.com/godotengine/godot/releases/download/${MAJOR_MINOR}-stable/Godot_v${MAJOR_MINOR}-stable_export_templates.tpz"
    else
        DOWNLOAD_URL="https://github.com/godotengine/godot/releases/tag/${MAJOR_MINOR}-stable"
    fi
    echo "  $DOWNLOAD_URL"
    echo ""

    # Ask user if they want to auto-install
    read -p "Would you like to download and install templates automatically? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Downloading export templates...${NC}"

        TEMP_DIR=$(mktemp -d)
        TEMPLATES_FILE="$TEMP_DIR/export_templates.tpz"

        # Try to download
        if command -v wget &> /dev/null; then
            wget -q --show-progress -O "$TEMPLATES_FILE" "$DOWNLOAD_URL" || {
                echo -e "${RED}Download failed. Please install templates manually.${NC}"
                rm -rf "$TEMP_DIR"
                exit 1
            }
        elif command -v curl &> /dev/null; then
            curl -L --progress-bar -o "$TEMPLATES_FILE" "$DOWNLOAD_URL" || {
                echo -e "${RED}Download failed. Please install templates manually.${NC}"
                rm -rf "$TEMP_DIR"
                exit 1
            }
        else
            echo -e "${RED}Neither wget nor curl found. Please install templates manually.${NC}"
            rm -rf "$TEMP_DIR"
            exit 1
        fi

        echo -e "${YELLOW}Installing export templates...${NC}"
        mkdir -p "$TEMPLATES_DIR"

        # Extract templates (tpz is a zip file)
        unzip -q -o "$TEMPLATES_FILE" -d "$TEMP_DIR/extracted"
        mv "$TEMP_DIR/extracted/templates/"* "$TEMPLATES_DIR/" 2>/dev/null ||         mv "$TEMP_DIR/extracted/"* "$TEMPLATES_DIR/" 2>/dev/null || true

        rm -rf "$TEMP_DIR"

        if [[ -f "$TEMPLATES_DIR/web_release.zip" ]]; then
            echo -e "${GREEN}Export templates installed successfully!${NC}"
        else
            echo -e "${RED}Template installation may have failed. Please check $TEMPLATES_DIR${NC}"
            exit 1
        fi
    else
        echo -e "${RED}Export templates required. Please install them and try again.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}Export templates found at: $TEMPLATES_DIR${NC}"
fi

# Create build directory if it doesn't exist
mkdir -p "$BUILD_DIR"

# Clean previous build
echo -e "${YELLOW}Cleaning previous build...${NC}"
rm -rf "$BUILD_DIR"/*

# Import project resources (required for first-time exports)
echo -e "${YELLOW}Importing project resources...${NC}"
$GODOT_CMD --headless --path "$PROJECT_DIR" --import 2>/dev/null || true

# Export the project
echo -e "${YELLOW}Exporting project for Web...${NC}"
$GODOT_CMD --headless --path "$PROJECT_DIR" --export-release "$EXPORT_PRESET" "$BUILD_DIR/index.html"

# Check if export was successful
if [ -f "$BUILD_DIR/index.html" ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Export Successful!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e "Output directory: ${YELLOW}$BUILD_DIR${NC}"
    echo ""
    echo "Files exported:"
    ls -lh "$BUILD_DIR"
    echo ""
    echo -e "${YELLOW}To test locally, serve the build directory with a web server:${NC}"
    echo "  cd $BUILD_DIR && python3 -m http.server 8080"
else
    echo -e "${RED}Export failed! Check the output above for errors.${NC}"
    exit 1
fi
