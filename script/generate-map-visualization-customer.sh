#!/bin/bash
# Generate customer journey visualization
# Usage: ./generate-map-visualization-customer.sh <map-name> <customer-id>

set -e

# Check arguments
if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: $0 <map-name> <customer-id>"
    echo ""
    echo "Examples:"
    echo "  $0 turbohill 0.0"
    echo "  $0 turbohill 0.16"
    echo "  $0 turbohill 42.21"
    echo ""
    echo "The script will:"
    echo "  - Use the latest result from maps/<map-name>/logs/latest/"
    echo "  - Generate visualization: maps/<map-name>/customer_<id>.png"
    exit 1
fi

MAP_NAME="$1"
CUSTOMER_ID="$2"

# Convert to lowercase for consistency
MAP_NAME_LOWER=$(echo "$MAP_NAME" | tr '[:upper:]' '[:lower:]')

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Paths
PYTHON_SCRIPT="$SCRIPT_DIR/python/visualize_customer.py"
MAP_DIR="$SCRIPT_DIR/maps/$MAP_NAME_LOWER"

# Check if map directory exists
if [ ! -d "$MAP_DIR" ]; then
    echo "❌ Map directory not found: $MAP_DIR"
    exit 1
fi

# Check if Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "❌ Python script not found: $PYTHON_SCRIPT"
    exit 1
fi

# Check if latest logs exist
LATEST_DIR="$MAP_DIR/logs/latest"
if [ ! -d "$LATEST_DIR" ]; then
    echo "❌ No latest logs found: $LATEST_DIR"
    echo "   Run a simulation first to generate logs"
    exit 1
fi

echo "🎨 Generating customer journey visualization..."
echo "   Map:         $MAP_NAME_LOWER"
echo "   Customer ID: $CUSTOMER_ID"
echo ""

# Activate Python virtual environment
cd "$SCRIPT_DIR/python"
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "❌ Python virtual environment not found: python/venv/"
    echo "   Please run: cd python && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Run Python script
python visualize_customer.py "$CUSTOMER_ID" --map-name "$MAP_NAME_LOWER"

echo ""
echo "✅ Visualization complete!"
echo "   Output: $MAP_DIR/customer_${CUSTOMER_ID//./_}.png"
