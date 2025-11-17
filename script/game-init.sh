#!/bin/bash

# Initialize and analyze a new map deployment
# Usage: ./game-init.sh <MapName>

if [ -z "$1" ]; then
    echo "Usage: $0 <MapName>"
    echo "Example: $0 Turbohill"
    exit 1
fi

MAP_NAME="$1"
MAP_NAME_LOWER=$(echo "$MAP_NAME" | tr '[:upper:]' '[:lower:]')

echo "🚀 Initializing new map deployment: $MAP_NAME"
echo "=============================================="
echo ""

# Check if Docker container is running
if ! curl -s http://localhost:8080/api/map-configs > /dev/null 2>&1; then
    echo "❌ Docker container not running!"
    echo "Start it with: docker run -p 8080:8080 considition/considition2025:latest"
    exit 1
fi

# Create map directory structure
MAP_DIR="maps/${MAP_NAME_LOWER}"
mkdir -p "$MAP_DIR/logs"
echo "📁 Created directory: $MAP_DIR"
echo ""

# 1. Fetch map data
MAP_FILE="$MAP_DIR/${MAP_NAME_LOWER}-map.json"
echo "📥 Fetching map data..."
curl -s "http://localhost:8080/api/map?mapName=${MAP_NAME}" > "$MAP_FILE"
if [ $? -eq 0 ] && [ -s "$MAP_FILE" ]; then
    echo "✅ Map data saved: $MAP_FILE"
else
    echo "❌ Failed to fetch map data"
    exit 1
fi

# Fetch map config
MAP_CONFIG_FILE="$MAP_DIR/${MAP_NAME_LOWER}-map-config.json"
echo "📥 Fetching map config..."
curl -s "http://localhost:8080/api/map-config?mapName=${MAP_NAME}" > "$MAP_CONFIG_FILE"
if [ $? -eq 0 ] && [ -s "$MAP_CONFIG_FILE" ]; then
    echo "✅ Map config saved: $MAP_CONFIG_FILE"
else
    echo "❌ Failed to fetch map config"
    exit 1
fi
echo ""

# 2. Generate map summary
echo "📊 Step 1/6: Generating map summary..."
./generate-map-summary.sh "$MAP_NAME"
if [ $? -ne 0 ]; then
    echo "⚠️  Warning: Map summary generation had issues"
fi
echo ""

# 3. Generate charging stations analysis
echo "⚡ Step 2/6: Generating charging stations analysis..."
./generate-map-stations.sh "$MAP_NAME"
if [ $? -ne 0 ]; then
    echo "⚠️  Warning: Charging stations analysis had issues"
fi
echo ""

# 4. Generate customers analysis
echo "👥 Step 3/6: Generating customers analysis..."
./generate-map-customers.sh "$MAP_NAME"
if [ $? -ne 0 ]; then
    echo "⚠️  Warning: Customers analysis had issues"
fi

# Wait and verify customer file was created
CUSTOMER_FILE="$MAP_DIR/${MAP_NAME_LOWER}-customers.json"
echo "⏳ Waiting for customer file: $CUSTOMER_FILE"
WAIT_COUNT=0
MAX_WAIT=30
while [ ! -f "$CUSTOMER_FILE" ] && [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    echo -n "."
done
echo ""

if [ -f "$CUSTOMER_FILE" ]; then
    echo "✅ Customer file created successfully"
else
    echo "❌ Customer file not created after ${MAX_WAIT}s"
    exit 1
fi
echo ""

# 5. Generate zone weather data
echo "🌤️  Step 4/6: Generating zone weather data..."
./generate-zone-weather-data.sh "$MAP_NAME"
if [ $? -ne 0 ]; then
    echo "⚠️  Warning: Zone weather data generation had issues"
fi
echo ""

# 6. Generate map visualization
echo "🎨 Step 5/6: Generating map visualization..."
./generate-map-visualization.sh "$MAP_NAME"
if [ $? -ne 0 ]; then
    echo "⚠️  Warning: Map visualization had issues"
fi
echo ""

# 7. Generate map analysis (if script exists)
ANALYSIS_FILE="$MAP_DIR/${MAP_NAME_LOWER}-analysis.md"
if [ -f "./generate-map-analysis.sh" ]; then
    echo "📈 Step 6/6: Generating map analysis..."
    ./generate-map-analysis.sh "$MAP_NAME"
    if [ $? -ne 0 ]; then
        echo "⚠️  Warning: Map analysis had issues"
    fi
else
    echo "ℹ️  Step 6/6: Skipping map analysis (script not found)"
fi
echo ""

# Show summary of generated files
echo "=============================================="
echo "✅ Map initialization complete!"
echo ""
echo "📂 Generated files in $MAP_DIR:"
echo ""

# List all generated files
if [ -f "$MAP_DIR/${MAP_NAME_LOWER}-summary.json" ]; then
    echo "   ✓ ${MAP_NAME_LOWER}-summary.json (Map summary)"
fi
if [ -f "$MAP_DIR/${MAP_NAME_LOWER}-stations.json" ]; then
    echo "   ✓ ${MAP_NAME_LOWER}-stations.json (Charging stations)"
fi
if [ -f "$MAP_DIR/${MAP_NAME_LOWER}-customers.json" ]; then
    echo "   ✓ ${MAP_NAME_LOWER}-customers.json (Customer data)"
fi
if [ -f "$MAP_DIR/${MAP_NAME_LOWER}_zone_weather_data.json" ]; then
    echo "   ✓ ${MAP_NAME_LOWER}_zone_weather_data.json (Zone weather data)"
fi
if [ -f "$MAP_DIR/${MAP_NAME_LOWER}-visualization.png" ]; then
    echo "   ✓ ${MAP_NAME_LOWER}-visualization.png (Map visualization)"
fi
if [ -f "$MAP_DIR/${MAP_NAME_LOWER}-analysis.md" ]; then
    echo "   ✓ ${MAP_NAME_LOWER}-analysis.md (Map analysis)"
fi
if [ -f "$MAP_DIR/${MAP_NAME_LOWER}-map.json" ]; then
    echo "   ✓ ${MAP_NAME_LOWER}-map.json (Full map data)"
fi
if [ -f "$MAP_DIR/${MAP_NAME_LOWER}-map-config.json" ]; then
    echo "   ✓ ${MAP_NAME_LOWER}-map-config.json (Map configuration)"
fi

echo ""
echo "🎯 Next steps:"
echo "   1. Review the map summary: cat $MAP_DIR/${MAP_NAME_LOWER}-summary.json | jq ."
echo "   2. View visualization: open $MAP_DIR/${MAP_NAME_LOWER}-visualization.png"
echo "   3. Run optimization: ./optimize-strategy-params.sh $MAP_NAME 50"
echo "   4. Test strategy: python/venv/bin/python python/strategies/automated_persona_strategy.py --map-name $MAP_NAME --mode iterative"
echo ""
