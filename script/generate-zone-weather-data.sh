#!/bin/bash
# Generate zone and weather data by running strategy and collecting zoneLogs
# Usage: ./generate-zone-weather-data.sh <map-name>

MAP_NAME="${1:-Turbohill}"

echo "🌦️  ZONE WEATHER DATA GENERATION"
echo "=================================="
echo "Map:      $MAP_NAME"
echo "Running to max ticks for this map"
echo ""

# Create log file for this run
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="maps/$(echo $MAP_NAME | tr '[:upper:]' '[:lower:]')/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/zone_weather_generation_$TIMESTAMP.log"

echo "📁 Log file: $LOG_FILE"
echo ""

# Run the Python script
echo "🚀 Running zone weather data collection..."
echo ""

python/venv/bin/python python/collect_zone_weather_data.py "$MAP_NAME" 2>&1 | tee "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ ZONE WEATHER DATA GENERATION COMPLETE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Find the generated files
    MAP_LOWER=$(echo $MAP_NAME | tr '[:upper:]' '[:lower:]')
    DATA_FILE="maps/$MAP_LOWER/${MAP_LOWER}_zone_weather_data.json"
    SUMMARY_FILE="maps/$MAP_LOWER/${MAP_LOWER}_zone_weather_summary.txt"
    
    if [ -f "$DATA_FILE" ]; then
        echo "📄 Generated files:"
        echo "   Data:    $DATA_FILE"
        if [ -f "$SUMMARY_FILE" ]; then
            echo "   Summary: $SUMMARY_FILE"
        fi
        echo ""
        
        # Show file size
        DATA_SIZE=$(du -h "$DATA_FILE" | cut -f1)
        echo "   Data file size: $DATA_SIZE"
        echo ""
        
        # Show summary if available
        if [ -f "$SUMMARY_FILE" ]; then
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "📊 SUMMARY"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            cat "$SUMMARY_FILE"
            echo ""
        fi
        
        echo "💡 Usage in strategy:"
        echo "   Load this file to predict weather and energy patterns:"
        echo ""
        echo "   import json"
        echo "   with open('$DATA_FILE', 'r') as f:"
        echo "       weather_data = json.load(f)"
        echo "   "
        echo "   # Access zone data for a specific tick:"
        echo "   tick_zones = weather_data['zoneLogs'][tick_index]['zones']"
        echo "   for zone in tick_zones:"
        echo "       zone_id = zone['zoneId']"
        echo "       weather_type = zone['weatherType']"
        echo "       is_green = zone['sourceinfo']['Nuclear']['isGreen']"
        echo ""
    else
        echo "⚠️  Data file not found: $DATA_FILE"
    fi
    
    echo "📝 Full log saved to: $LOG_FILE"
else
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "❌ ZONE WEATHER DATA GENERATION FAILED"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📝 Check log file for details: $LOG_FILE"
    exit 1
fi
