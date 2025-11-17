#!/bin/bash
# Compare different strategy configurations
# Usage: ./compare-strategy-configs.sh <map-name> [end-tick]

MAP_NAME="${1:-turbohill}"
END_TICK="${2:-50}"

echo "🔬 STRATEGY CONFIGURATION COMPARISON"
echo "===================================="
echo "Map:      $MAP_NAME"
echo "End Tick: $END_TICK"
echo ""

# Array of configurations to test
CONFIGS=("default" "conservative" "aggressive" "experimental")

# Create comparison log directory
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
COMPARE_DIR="maps/$MAP_NAME/logs/comparison_$TIMESTAMP"
mkdir -p "$COMPARE_DIR"

echo "📁 Results will be saved to: $COMPARE_DIR"
echo ""

# Test each configuration
for config in "${CONFIGS[@]}"; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🧪 Testing: $config"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    LOG_FILE="$COMPARE_DIR/${config}_test.log"
    
    # Run the strategy
    python/venv/bin/python python/strategies/automated_persona_strategy.py \
        --map-name "$MAP_NAME" \
        --mode iterative \
        --strategy-config "$config" \
        --end-tick "$END_TICK" \
        2>&1 | tee "$LOG_FILE"
    
    # Extract final results (remove commas from numbers for CSV compatibility)
    SCORE=$(grep "Total Score:" "$LOG_FILE" | tail -1 | awk '{print $3}' | tr -d ',')
    KWH=$(grep "kWh Revenue:" "$LOG_FILE" | tail -1 | awk '{print $3}' | tr -d ',')
    COMPLETION=$(grep "Customer Completion:" "$LOG_FILE" | tail -1 | awk '{print $3}' | tr -d ',')
    DYNAMIC_RECS=$(grep "Dynamic Recs Added:" "$LOG_FILE" | tail -1 | awk '{print $4}' | tr -d ',')
    
    # Extract customer states (remove commas)
    HOME=$(grep -A 10 "Customer States:" "$LOG_FILE" | grep "Home" | awk '{print $3}' | tr -d ',')
    TRAVELING=$(grep -A 10 "Customer States:" "$LOG_FILE" | grep "Traveling" | awk '{print $3}' | tr -d ',')
    CHARGING=$(grep -A 10 "Customer States:" "$LOG_FILE" | grep "Charging" | awk '{print $3}' | tr -d ',')
    DONE=$(grep -A 10 "Customer States:" "$LOG_FILE" | grep "DestinationReached" | awk '{print $3}' | tr -d ',')
    RAN_OUT=$(grep -A 10 "Customer States:" "$LOG_FILE" | grep "RanOutOfJuice" | awk '{print $3}' | tr -d ',')
    
    # Extract log directory path for this config
    LOG_DIR=$(grep "Log directory:" "$LOG_FILE" | head -1 | awk '{print $3}')
    
    # Save summary (including log directory)
    echo "$config,$SCORE,$KWH,$COMPLETION,$DYNAMIC_RECS,$HOME,$TRAVELING,$CHARGING,$DONE,$RAN_OUT,$LOG_DIR" >> "$COMPARE_DIR/summary.csv"
    
    echo ""
    echo "✅ $config complete"
    echo "   Score: $SCORE | kWh: $KWH | Completion: $COMPLETION"
    echo "   Dynamic Recs: $DYNAMIC_RECS"
    echo "   States - Home: $HOME, Traveling: $TRAVELING, Charging: $CHARGING, Done: $DONE, RanOut: $RAN_OUT"
    echo ""
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 COMPARISON RESULTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Add header to CSV
sed -i '' '1s/^/config,score,kwh_revenue,completion,dynamic_recs,home,traveling,charging,done,ran_out,log_dir\n/' "$COMPARE_DIR/summary.csv"

# Display results table (without log_dir column for readability)
echo "Configuration Summary:"
echo ""
cut -d',' -f1-10 "$COMPARE_DIR/summary.csv" | column -t -s,
echo ""

# Find the best strategy (highest score)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🏆 BEST STRATEGY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Skip header and find max score
BEST_LINE=$(tail -n +2 "$COMPARE_DIR/summary.csv" | sort -t',' -k2 -nr | head -1)
BEST_CONFIG=$(echo "$BEST_LINE" | cut -d',' -f1)
BEST_SCORE=$(echo "$BEST_LINE" | cut -d',' -f2)
BEST_KWH=$(echo "$BEST_LINE" | cut -d',' -f3)
BEST_COMPLETION=$(echo "$BEST_LINE" | cut -d',' -f4)
BEST_LOG_DIR=$(echo "$BEST_LINE" | cut -d',' -f11)

echo "Best Configuration: $BEST_CONFIG"
echo "   Score:              $BEST_SCORE"
echo "   kWh Revenue:        $BEST_KWH"
echo "   Customer Completion: $BEST_COMPLETION"
echo "   Log Directory:      $BEST_LOG_DIR"
echo ""

# Find the input file from the winning config's log directory
BEST_INPUT_FILE=""
if [ -n "$BEST_LOG_DIR" ] && [ -d "$BEST_LOG_DIR" ]; then
    # Look for final_input.json or the tick_288 input file
    if [ -f "$BEST_LOG_DIR/${MAP_NAME}_final_input.json" ]; then
        BEST_INPUT_FILE="$BEST_LOG_DIR/${MAP_NAME}_final_input.json"
    elif [ -f "$BEST_LOG_DIR/tick_$END_TICK/${MAP_NAME}_tick_${END_TICK}_input.json" ]; then
        BEST_INPUT_FILE="$BEST_LOG_DIR/tick_$END_TICK/${MAP_NAME}_tick_${END_TICK}_input.json"
    else
        # Fallback: search for any input file in the directory
        BEST_INPUT_FILE=$(find "$BEST_LOG_DIR" -name "*_input.json" | grep -E "final_input|tick_${END_TICK}_input" | head -1)
    fi
fi

if [ -n "$BEST_INPUT_FILE" ] && [ -f "$BEST_INPUT_FILE" ]; then
    echo "📄 Input file for cloud submission:"
    echo "   $BEST_INPUT_FILE"
    echo ""
    echo "💡 To submit to cloud, run:"
    echo "   ./submit-to-cloud.sh $BEST_INPUT_FILE"
    echo ""
    echo "   Or manually with curl:"
    echo "   curl -X POST https://api.considition.com/api/game \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -H 'x-api-key: YOUR_API_KEY' \\"
    echo "     -d @$BEST_INPUT_FILE"
else
    echo "⚠️  Input file not found in: $BEST_LOG_DIR"
    echo "   Expected: $BEST_LOG_DIR/tick_$END_TICK/${MAP_NAME}_tick_${END_TICK}_input.json"
fi
echo ""

echo "📁 Detailed logs saved to: $COMPARE_DIR"
echo "✅ Comparison complete!"
