#!/bin/bash

# Generate comprehensive map analysis
# Usage: ./generate-map-analysis.sh <MapName>

if [ -z "$1" ]; then
    echo "Usage: $0 <MapName>"
    echo "Example: $0 Turbohill"
    exit 1
fi

MAP_NAME="$1"
MAP_NAME_LOWER=$(echo "$MAP_NAME" | tr '[:upper:]' '[:lower:]')
MAP_DIR="maps/${MAP_NAME_LOWER}"
MAP_FILE="${MAP_DIR}/${MAP_NAME_LOWER}-map.json"
OUTPUT_FILE="${MAP_DIR}/${MAP_NAME_LOWER}-analysis.md"

# Check if map file exists
if [ ! -f "$MAP_FILE" ]; then
    echo "Error: Map file not found at $MAP_FILE"
    echo "Please run: curl -s http://localhost:8080/api/map?mapName=${MAP_NAME} > $MAP_FILE"
    exit 1
fi

echo "Analyzing map: $MAP_NAME"
echo "Generating analysis..."

# Extract data using jq
DIM_X=$(jq -r '.dimX' "$MAP_FILE")
DIM_Y=$(jq -r '.dimY' "$MAP_FILE")
TICKS=$(jq -r '.ticks' "$MAP_FILE")
TOTAL_NODES=$(jq '.nodes | length' "$MAP_FILE")
TOTAL_EDGES=$(jq '.edges | length' "$MAP_FILE")
TOTAL_CUSTOMERS=$(jq '[.nodes[] | .customers[]] | length' "$MAP_FILE")
CHARGING_STATIONS=$(jq '[.nodes[] | select(.target.Type == "ChargingStation")] | length' "$MAP_FILE")

# Customer analysis
PERSONAS=$(jq -r '[.nodes[] | .customers[] | .persona] | group_by(.) | map({persona: .[0], count: length}) | .[] | "\(.persona): \(.count)"' "$MAP_FILE")
MIN_DEPARTURE=$(jq '[.nodes[] | .customers[] | .departureTick] | min' "$MAP_FILE")
MAX_DEPARTURE=$(jq '[.nodes[] | .customers[] | .departureTick] | max' "$MAP_FILE")
AVG_CHARGE=$(jq '[.nodes[] | .customers[] | .chargeRemaining] | add / length' "$MAP_FILE")
MIN_CHARGE=$(jq '[.nodes[] | .customers[] | .chargeRemaining] | min' "$MAP_FILE")
MAX_CHARGE=$(jq '[.nodes[] | .customers[] | .chargeRemaining] | max' "$MAP_FILE")

# Charging station analysis
TOTAL_CHARGERS=$(jq '[.nodes[] | select(.target.Type == "ChargingStation") | .target.totalAmountOfChargers] | add' "$MAP_FILE")
AVAILABLE_CHARGERS=$(jq '[.nodes[] | select(.target.Type == "ChargingStation") | .target.amountOfAvailableChargers] | add' "$MAP_FILE")
BROKEN_CHARGERS=$(jq '[.nodes[] | select(.target.Type == "ChargingStation") | .target.totalAmountOfBrokenChargers] | add' "$MAP_FILE")
MIN_SPEED=$(jq '[.nodes[] | select(.target.Type == "ChargingStation") | .target.chargeSpeedPerCharger] | min' "$MAP_FILE")
MAX_SPEED=$(jq '[.nodes[] | select(.target.Type == "ChargingStation") | .target.chargeSpeedPerCharger] | max' "$MAP_FILE")
AVG_SPEED=$(jq '[.nodes[] | select(.target.Type == "ChargingStation") | .target.chargeSpeedPerCharger] | add / length' "$MAP_FILE")

# Edge analysis
AVG_EDGE_LENGTH=$(jq '[.edges[] | .length] | add / length' "$MAP_FILE")
MIN_EDGE_LENGTH=$(jq '[.edges[] | .length] | min' "$MAP_FILE")
MAX_EDGE_LENGTH=$(jq '[.edges[] | .length] | max' "$MAP_FILE")

# Zone analysis
TOTAL_ZONES=$(jq '.zones | length' "$MAP_FILE")
ZONES_WITH_STORAGE=$(jq '[.zones[] | select(.energyStorages | length > 0)] | length' "$MAP_FILE")

# Top charging stations by capacity
TOP_STATIONS=$(jq -r '[.nodes[] | select(.target.Type == "ChargingStation") | {id: .id, available: .target.amountOfAvailableChargers, total: .target.totalAmountOfChargers, speed: .target.chargeSpeedPerCharger, zone: .zoneId}] | sort_by(-.available) | .[:5] | .[] | "  - **\(.id)**: \(.available)/\(.total) chargers, \(.speed) kW, Zone: \(.zone)"' "$MAP_FILE")

# Worst charging stations (most broken)
WORST_STATIONS=$(jq -r '[.nodes[] | select(.target.Type == "ChargingStation") | {id: .id, broken: .target.totalAmountOfBrokenChargers, available: .target.amountOfAvailableChargers, total: .target.totalAmountOfChargers, zone: .zoneId}] | sort_by(-.broken) | .[:5] | .[] | "  - **\(.id)**: \(.broken) broken, \(.available) available, Zone: \(.zone)"' "$MAP_FILE")

# Customers by starting charge level
LOW_CHARGE_CUSTOMERS=$(jq -r '[.nodes[] | .customers[] | select(.chargeRemaining < 0.3) | {id: .id, from: .fromNode, to: .toNode, charge: (.chargeRemaining * 100 | floor), persona: .persona, tick: .departureTick}] | .[] | "  - **\(.id)**: \(.charge)% charge, \(.from)→\(.toNode), \(.persona), departs tick \(.tick)"' "$MAP_FILE")

# Zone details
ZONE_DETAILS=$(jq -r '.zones[] | "### Zone: \(.id)\n**Location**: (\(.topLeftX),\(.topLeftY)) to (\(.bottomRightX),\(.bottomRightY))\n\n**Energy Sources**:\n\([.energySources[] | "- \(.type): \(.generationCapacity * 100)%"] | join("\n"))\n\n**Energy Storage**:\n\(if .energyStorages | length > 0 then ([.energyStorages[] | "- Capacity: \(.capacityMWh) MWh, Efficiency: \(.efficiency * 100)%, Max Charge: \(.maxChargePowerMw) MW, Max Discharge: \(.maxDischargePowerMw) MW"] | join("\n")) else "- No storage available" end)\n"' "$MAP_FILE")

# Generate markdown report
cat > "$OUTPUT_FILE" << EOF
# Map Analysis: $MAP_NAME

**Generated**: $(date)

## 🗺️ Map Overview

**Dimensions**: ${DIM_X}x${DIM_Y} grid  
**Total Ticks**: $TICKS (24 hours simulated day)  
**Total Nodes**: $TOTAL_NODES  
**Total Edges**: $TOTAL_EDGES (directed roads)  
**Total Customers**: $TOTAL_CUSTOMERS  
**Charging Stations**: $CHARGING_STATIONS  

---

## 👥 Customer Analysis

### Distribution by Persona
$PERSONAS

### Departure Times
- **Earliest**: Tick $MIN_DEPARTURE
- **Latest**: Tick $MAX_DEPARTURE
- **Range**: $(($MAX_DEPARTURE - $MIN_DEPARTURE)) ticks

### Battery Levels
- **Average Starting Charge**: $(printf "%.1f%%" $(echo "$AVG_CHARGE * 100" | bc))
- **Minimum**: $(printf "%.1f%%" $(echo "$MIN_CHARGE * 100" | bc))
- **Maximum**: $(printf "%.1f%%" $(echo "$MAX_CHARGE * 100" | bc))

### ⚠️ Low Battery Customers (< 30%)
$LOW_CHARGE_CUSTOMERS

---

## ⚡ Charging Station Network

### Overall Statistics
- **Total Chargers**: $TOTAL_CHARGERS
- **Available (Working)**: $AVAILABLE_CHARGERS ($(echo "scale=1; $AVAILABLE_CHARGERS * 100 / $TOTAL_CHARGERS" | bc)%)
- **Broken**: $BROKEN_CHARGERS ($(echo "scale=1; $BROKEN_CHARGERS * 100 / $TOTAL_CHARGERS" | bc)%)

### Charging Speed
- **Minimum**: $MIN_SPEED kW
- **Maximum**: $MAX_SPEED kW
- **Average**: $(printf "%.0f" "$AVG_SPEED") kW

### 🏆 Top 5 Stations (by capacity)
$TOP_STATIONS

### ⚠️ Most Problematic Stations (broken chargers)
$WORST_STATIONS

---

## 🛣️ Road Network

### Edge Statistics
- **Total Edges**: $TOTAL_EDGES
- **Average Length**: $(printf "%.2f km" "$AVG_EDGE_LENGTH")
- **Shortest Edge**: $(printf "%.2f km" "$MIN_EDGE_LENGTH")
- **Longest Edge**: $(printf "%.2f km" "$MAX_EDGE_LENGTH")

**Note**: Roads are directional - distance A→B may differ from B→A

---

## 🔋 Energy Zones

**Total Zones**: $TOTAL_ZONES  
**Zones with Storage**: $ZONES_WITH_STORAGE  
**Zones without Storage**: $(($TOTAL_ZONES - $ZONES_WITH_STORAGE)) (⚠️ higher brownout risk)

$ZONE_DETAILS

---

## 🎯 Strategic Insights

### Key Challenges

1. **Reliability Issues**
   - $(echo "scale=1; $BROKEN_CHARGERS * 100 / $TOTAL_CHARGERS" | bc)% of chargers are broken
   - Capacity planning critical for high-demand periods

2. **Energy Grid Risks**
   - $(($TOTAL_ZONES - $ZONES_WITH_STORAGE)) zones lack storage backup
   - Brownouts will reduce revenue and charging capacity

3. **Customer Battery Management**
   - $(jq '[.nodes[] | .customers[] | select(.chargeRemaining < 0.3)] | length' "$MAP_FILE") customers start with <30% charge
   - Early charging required to prevent stranding

### Optimization Opportunities

1. **Route Planning**
   - Build directed graph from $TOTAL_EDGES edges
   - Use Dijkstra/A* for shortest paths
   - Account for asymmetric edge lengths

2. **Charging Strategy**
   - Prioritize stations in zones with storage
   - Avoid overcrowded stations
   - Balance speed vs. availability

3. **Persona-Based Scoring**
   - Tailor routes to customer preferences
   - Eco-conscious → cleaner zones
   - Cost-sensitive → avoid brownout zones
   - Stressed/DislikesDriving → minimize travel time

4. **Demand Forecasting**
   - Peak departure: ticks $MIN_DEPARTURE-$MAX_DEPARTURE
   - Zone-based capacity planning
   - Storage zones can handle higher demand

---

## 📊 Algorithm Development Checklist

- [ ] Parse map data and build directed graph
- [ ] Index charging stations by zone, capacity, and speed
- [ ] Calculate shortest paths between all nodes
- [ ] Implement persona-based scoring logic
- [ ] Add brownout risk assessment
- [ ] Create zone-aware routing
- [ ] Handle low-battery customers first
- [ ] Test against local API
- [ ] Optimize for final scoring metrics

---

## 🔗 Related Files

- Map Data: \`${MAP_NAME_LOWER}-map.json\`
- Summary: \`${MAP_NAME_LOWER}-summary.json\`
- Visualization: \`${MAP_NAME_LOWER}-visualization.png\`
- Strategy: \`${MAP_NAME_LOWER}-strategy.md\`

EOF

echo "✅ Analysis saved to: $OUTPUT_FILE"
echo ""
echo "Key Metrics:"
echo "  Customers: $TOTAL_CUSTOMERS"
echo "  Charging Stations: $CHARGING_STATIONS"
echo "  Available Chargers: $AVAILABLE_CHARGERS/$TOTAL_CHARGERS"
echo "  Energy Zones: $TOTAL_ZONES ($ZONES_WITH_STORAGE with storage)"
echo "  Road Network: $TOTAL_EDGES edges"
