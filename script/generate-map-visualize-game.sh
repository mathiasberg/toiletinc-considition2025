#!/bin/bash

# Script to visualize game result for any Considition 2025 map
# Usage: ./visualize-game-result.sh <mapName>

if [ -z "$1" ]; then
    echo "Usage: $0 <mapName>"
    echo "Example: $0 Turbohill"
    exit 1
fi

MAP_NAME="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_DIR="$SCRIPT_DIR/python"
MAP_NAME_LOWER=$(echo "$MAP_NAME" | tr '[:upper:]' '[:lower:]')
MAP_DIR="$SCRIPT_DIR/maps/$MAP_NAME_LOWER"
MAP_FILE="$MAP_DIR/${MAP_NAME_LOWER}-map.json"
CONFIG_FILE="$MAP_DIR/${MAP_NAME_LOWER}-map-config.json"

echo "🎮 Game Result Visualizer"
echo "================================="
echo ""
echo "Map: $MAP_NAME"
echo ""

# Check if map data exists
if [ ! -f "$MAP_FILE" ]; then
    echo "❌ Error: Map file not found: $MAP_FILE"
    exit 1
fi

# Check if config exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: Map config not found: $CONFIG_FILE"
    exit 1
fi

# Get max ticks from config
MAX_TICKS=$(jq -r '.ticks' "$CONFIG_FILE")
echo "Max ticks: $MAX_TICKS"

# Find latest result file
LATEST_LINK="$MAP_DIR/logs/latest"
if [ ! -L "$LATEST_LINK" ]; then
    echo "❌ Error: No 'latest' run found in $MAP_DIR/logs/"
    exit 1
fi

RESULT_FILE="$LATEST_LINK/tick_${MAX_TICKS}/${MAP_NAME_LOWER}_tick_${MAX_TICKS}_result.json"
if [ ! -f "$RESULT_FILE" ]; then
    echo "❌ Error: Result file not found: $RESULT_FILE"
    exit 1
fi

echo "✅ Using result file: $RESULT_FILE"
echo ""

# Check if Python environment is set up
if [ ! -d "$PYTHON_DIR/venv" ]; then
    echo "📦 Python environment not found. Setting up..."
    cd "$PYTHON_DIR"
    ./setup.sh
    cd "$SCRIPT_DIR"
    echo ""
fi

# Output file
OUTPUT_FILE="$MAP_DIR/${MAP_NAME_LOWER}-result-visualization.png"

# Run visualization
echo "🎨 Generating visualization..."
cd "$PYTHON_DIR"
source venv/bin/activate

python visualize_game_result_customers.py "$MAP_FILE" "$RESULT_FILE" "$OUTPUT_FILE"

echo ""
echo "✅ Visualization complete!"
echo ""
echo "Generated file:"
echo "  📊 $OUTPUT_FILE"
echo ""
echo "View with:"
echo "  open $OUTPUT_FILE"
