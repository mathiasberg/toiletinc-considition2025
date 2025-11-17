#!/bin/bash

# Script to generate a summary JSON file for any Considition 2025 map
# Usage: ./generate-map-summary.sh <mapName>

if [ -z "$1" ]; then
    echo "Usage: $0 <mapName>"
    echo "Example: $0 Turbohill"
    exit 1
fi

MAP_NAME="$1"
BASE_URL="${BASE_URL:-http://localhost:8080}"
MAP_DIR="maps/$(echo "$MAP_NAME" | tr '[:upper:]' '[:lower:]')"
OUTPUT_FILE="${MAP_DIR}/$(echo "$MAP_NAME" | tr '[:upper:]' '[:lower:]')-summary.json"

# Create map directory if it doesn't exist
mkdir -p "$MAP_DIR"

echo "🗺️  Generating summary for map: $MAP_NAME"
echo "================================================"

# Fetch map config
echo "📋 Fetching map configuration..."
MAP_CONFIG=$(curl -s "${BASE_URL}/api/map-config?mapName=${MAP_NAME}")

if echo "$MAP_CONFIG" | grep -q "not found"; then
    echo "❌ Error: Map '$MAP_NAME' not found"
    exit 1
fi

# Fetch full map data
echo "📥 Fetching full map data..."
MAP_DATA=$(curl -s "${BASE_URL}/api/map?mapName=${MAP_NAME}")

if echo "$MAP_DATA" | grep -q "Not Found"; then
    echo "❌ Error: Could not fetch map data"
    exit 1
fi

# Run a single tick to get initial game state
echo "🎮 Running initial game state check..."
GAME_STATE=$(curl -s -X POST "${BASE_URL}/api/game" \
  -H "Content-Type: application/json" \
  -d "{
    \"mapName\": \"${MAP_NAME}\",
    \"playToTick\": 1,
    \"ticks\": []
  }")

echo "📊 Processing data..."

# Generate summary using jq
cat > "$OUTPUT_FILE" << 'EOF_TEMPLATE'
{
  "mapName": null,
  "description": null,
  "grid": {
    "dimensions": {
      "x": null,
      "y": null
    },
    "nodes": null,
    "edges": null
  },
  "simulation": {
    "ticks": null,
    "tickDuration": "5 minutes",
    "totalDuration": "24 hours (1 day)"
  },
  "customers": {
    "total": null,
    "personas": {},
    "vehicleTypes": {}
  },
  "zones": {
    "total": null,
    "layout": null,
    "details": []
  },
  "chargingStations": {
    "total": null,
    "maxChargersPerStation": null,
    "chargerSpeedRange": {
      "min": null,
      "max": null
    }
  },
  "vehicles": {
    "cars": {
      "baseSpeedRange": null,
      "batteryCapacity": null,
      "consumptionPerKm": null
    },
    "trucks": {
      "baseSpeedRange": null,
      "batteryCapacity": null,
      "consumptionPerKm": null
    }
  },
  "weather": {
    "cloudVolatility": null,
    "windVolatility": null,
    "affectsGreenEnergy": true
  },
  "initialGameState": {
    "score": null,
    "kwhRevenue": null,
    "customerCompletionScore": null
  },
  "seed": null,
  "events": null,
  "percentageHoles": null,
  "percentageBridges": null,
  "minimumIslandSize": null,
  "personaDifficulty": null
}
EOF_TEMPLATE

# Build the summary JSON
jq -n \
  --argjson config "$MAP_CONFIG" \
  --argjson mapdata "$MAP_DATA" \
  --argjson gamestate "$GAME_STATE" \
  '{
    mapName: $config.name,
    description: $config.description,
    grid: {
      dimensions: {
        x: $config.dimX,
        y: $config.dimY
      },
      nodes: ($mapdata.nodes | length),
      edges: ($mapdata.edges | length)
    },
    simulation: {
      ticks: $config.ticks,
      tickDuration: "5 minutes",
      totalDuration: "24 hours (1 day)"
    },
    customers: {
      total: $config.customers,
      personas: (
        $config.personas | 
        map(select(.percentage > 0) | {key: (.persona | tostring), value: .percentage}) | 
        from_entries
      ),
      personaDetails: (
        $config.personas | 
        map({
          persona: (.persona | 
            if . == 0 then "Neutral"
            elif . == 1 then "CostSensitive"
            elif . == 2 then "DislikesDriving"
            elif . == 3 then "EcoConscious"
            elif . == 4 then "Stressed"
            else "Unknown"
            end),
          percentage: .percentage
        })
      ),
      vehicleTypes: {
        percentageTrucks: $config.percentageTrucks,
        percentageCars: (1 - $config.percentageTrucks)
      }
    },
    zones: {
      total: ($mapdata.zones | length),
      layout: "\($config.zoneCountX)x\($config.zoneCountY) grid",
      details: [
        $mapdata.zones[] | {
          id: .id,
          bounds: {
            topLeft: {x: .topLeftX, y: .topLeftY},
            bottomRight: {x: .bottomRightX, y: .bottomRightY}
          },
          energySources: [.energySources[] | .type],
          energyStorages: (.energyStorages | length),
          storageCapacity: (
            if (.energyStorages | length) > 0 
            then "\([.energyStorages[].capacityMWh] | add) MWh total"
            else "0 MWh"
            end
          )
        }
      ]
    },
    chargingStations: {
      total: $config.chargingStations,
      maxChargersPerStation: $config.maxChargersPerStation,
      chargerSpeedRange: {
        min: $config.minChargerSpeed,
        max: $config.maxChargerSpeed
      },
      brokenChargerRange: {
        min: $config.minBrokenChargerPercentage,
        max: $config.maxBrokenChargerPercentage
      }
    },
    vehicles: {
      cars: {
        baseSpeedRange: "\($config.cars.minBaseSpeed)-\($config.cars.maxBaseSpeed) km/h",
        batteryCapacity: "\($config.cars.minBatteryCapacity)-\($config.cars.maxBatteryCapacity) kWh",
        consumptionPerKm: "\($config.cars.minConsumptionPerKm) kWh/km"
      },
      trucks: {
        baseSpeedRange: "\($config.trucks.minBaseSpeed)-\($config.trucks.maxBaseSpeed) km/h",
        batteryCapacity: "\($config.trucks.minBatteryCapacity)-\($config.trucks.maxBatteryCapacity) kWh",
        consumptionPerKm: "\($config.trucks.minConsumptionPerKm) kWh/km"
      }
    },
    weather: {
      cloudVolatility: $config.cloudVolatility,
      cloudOffset: $config.cloudOffset,
      windVolatility: $config.windVolatility,
      windOffset: $config.windOffset,
      affectsGreenEnergy: true
    },
    initialGameState: {
      score: $gamestate.score,
      kwhRevenue: $gamestate.kwhRevenue,
      customerCompletionScore: $gamestate.customerCompletionScore,
      totalCustomers: ($gamestate.customerLogs | length)
    },
    roadNetwork: {
      averageEdgeLength: ([$mapdata.edges[].length] | add / length | floor * 100 / 100),
      minEdgeLength: ([$mapdata.edges[].length] | min),
      maxEdgeLength: ([$mapdata.edges[].length] | max)
    },
    seed: $config.seed,
    events: $config.events,
    percentageHoles: $config.percentageHoles,
    percentageBridges: $config.percentageBridges,
    minimumIslandSize: $config.minimumIslandSize,
    personaDifficulty: $config.personaDifficulty,
    edgeLengthModifier: $config.edgeLengthModifier,
    newCustomerWaitRange: {
      min: $config.newCustomerMinWait,
      max: $config.newCustomerMaxWait
    },
    newCustomerMinChargeRemaining: $config.newCustomerMinChargeRemaining
  }' > "$OUTPUT_FILE"

echo ""
echo "✅ Summary generated successfully!"
echo "📄 File: $OUTPUT_FILE"
echo ""
echo "Quick overview:"
jq '{
  map: .mapName,
  description: .description,
  grid: "\(.grid.dimensions.x)x\(.grid.dimensions.y)",
  nodes: .grid.nodes,
  edges: .grid.edges,
  customers: .customers.total,
  chargingStations: .chargingStations.total,
  zones: .zones.total,
  ticks: .simulation.ticks
}' "$OUTPUT_FILE"

echo ""
echo "Full summary available in: $OUTPUT_FILE"
