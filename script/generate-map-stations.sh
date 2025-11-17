#!/bin/bash

# Script to generate detailed charging station information JSON for any Considition 2025 map
# Usage: ./generate-map-stations.sh <mapName>

if [ -z "$1" ]; then
    echo "Usage: $0 <mapName>"
    echo "Example: $0 Turbohill"
    exit 1
fi

MAP_NAME="$1"
MAP_DIR="maps/$(echo "$MAP_NAME" | tr '[:upper:]' '[:lower:]')"
MAP_FILE="${MAP_DIR}/$(echo "$MAP_NAME" | tr '[:upper:]' '[:lower:]')-map.json"
MAP_CONFIG_FILE="${MAP_DIR}/$(echo "$MAP_NAME" | tr '[:upper:]' '[:lower:]')-map-config.json"
OUTPUT_FILE="${MAP_DIR}/$(echo "$MAP_NAME" | tr '[:upper:]' '[:lower:]')-stations.json"

echo "⚡ Generating charging station information for map: $MAP_NAME"
echo "================================================"

# Check if map file exists
if [ ! -f "$MAP_FILE" ]; then
    echo "❌ Error: Map file not found: $MAP_FILE"
    echo "💡 Tip: Run './fetch-map.sh $MAP_NAME' first to download the map"
    exit 1
fi

# Check if map config file exists
if [ ! -f "$MAP_CONFIG_FILE" ]; then
    echo "⚠️  Warning: Map config file not found: $MAP_CONFIG_FILE"
    echo "   Energy type classification will be limited"
fi

# Read map data from file
echo "📥 Reading map data from: $MAP_FILE"
MAP_DATA=$(cat "$MAP_FILE")

# Read map config if available
if [ -f "$MAP_CONFIG_FILE" ]; then
    MAP_CONFIG=$(cat "$MAP_CONFIG_FILE")
else
    MAP_CONFIG='{}'
fi

# Check if map has charging stations
STATION_COUNT=$(echo "$MAP_DATA" | jq '[.nodes[] | select(.target.Type == "ChargingStation")] | length' 2>/dev/null || echo "0")

if [ "$STATION_COUNT" -eq "0" ]; then
    echo "❌ Error: No charging stations found in map data"
    exit 1
fi

echo "📊 Processing $STATION_COUNT charging stations..."

# Create a combined JSON with both map and config data
COMBINED_DATA=$(jq -n \
  --argjson map "$MAP_DATA" \
  --argjson config "$MAP_CONFIG" \
  '{map: $map, config: $config}')

# Generate charging station information using jq
echo "$COMBINED_DATA" | jq --arg station_count "$STATION_COUNT" '
# Helper function to determine if energy type is green/renewable
def isGreenEnergy:
  . as $type |
  (["Solar", "Wind", "Hydro", "Geothermal", "Biomass"] | any(. == $type));

# Helper function to classify energy source
def classifyEnergySource:
  if isGreenEnergy then "renewable"
  elif . == "Nuclear" then "low-carbon"
  else "fossil-fuel" end;

. as $root |
{
  mapName: .map.name,
  generatedAt: (now | strftime("%Y-%m-%d %H:%M:%S")),
  stationCount: ([.map.nodes[] | select(.target.Type == "ChargingStation")] | length),
  chargingStations: [
    .map.nodes[] | select(.target.Type == "ChargingStation") | 
    . as $station |
    # Find the zone for this station
    (.zoneId) as $zoneId |
    ($root.map.zones[] | select(.id == $zoneId)) as $zone |
    {
      nodeId: .id,
      stationType: .target.Type,
      location: {
        x: .posX,
        y: .posY,
        nodeId: .id,
        zoneId: .zoneId
      },
      capacity: {
        totalChargers: .target.totalAmountOfChargers,
        availableChargers: .target.amountOfAvailableChargers,
        brokenChargers: .target.totalAmountOfBrokenChargers,
        utilizationRate: (
          if .target.totalAmountOfChargers > 0 then
            ((.target.totalAmountOfChargers - .target.amountOfAvailableChargers) / .target.totalAmountOfChargers * 100 | round)
          else 0 end
        )
      },
      performance: {
        chargeSpeedPerCharger: .target.chargeSpeedPerCharger,
        totalPossibleSpeed: (.target.amountOfAvailableChargers * .target.chargeSpeedPerCharger),
        totalCapacity: (.target.totalAmountOfChargers * .target.chargeSpeedPerCharger)
      },
      status: {
        operational: (.target.amountOfAvailableChargers > 0),
        degraded: (.target.totalAmountOfBrokenChargers > 0),
        healthPercentage: (
          if .target.totalAmountOfChargers > 0 then
            ((.target.totalAmountOfChargers - .target.totalAmountOfBrokenChargers) / .target.totalAmountOfChargers * 100 | round)
          else 0 end
        )
      },
      zoneEnergy: {
        zoneId: $zone.id,
        energySources: [
          $zone.energySources[] | 
          . as $source |
          # Look up energy type info from config
          ($root.config.energyMix.energySources[]? | select(.type == $source.type)) as $configSource |
          {
            type: .type,
            generationCapacity: .generationCapacity,
            isGreen: (.type | isGreenEnergy),
            classification: (.type | classifyEnergySource),
            producedEnergy: ($configSource.producedEnergy // null)
          }
        ],
        energyStorages: [
          $zone.energyStorages[] | {
            capacityMWh: .capacityMWh,
            efficiency: .efficiency,
            maxChargePowerMw: .maxChargePowerMw,
            maxDischargePowerMw: .maxDischargePowerMw
          }
        ],
        totalStorageCapacity: ([$zone.energyStorages[]?.capacityMWh] | add // 0),
        totalGenerationCapacity: ([$zone.energySources[]?.generationCapacity] | add // 0),
        greenEnergyPercentage: (
          if ([$zone.energySources[]?.generationCapacity] | add // 0) > 0 then
            (([$zone.energySources[] | select(.type | isGreenEnergy) | .generationCapacity] | add // 0) / 
             ([$zone.energySources[]?.generationCapacity] | add) * 100 | round)
          else 0 end
        ),
        hasGreenEnergy: ([$zone.energySources[] | select(.type | isGreenEnergy)] | length > 0),
        hasStorage: ([$zone.energyStorages[]] | length > 0)
      }
    }
  ],
  statistics: {
    byEnergyType: {
      renewable: {
        count: 0,
        stationNodeIds: []
      },
      lowCarbon: {
        count: 0,
        stationNodeIds: []
      },
      fossilFuel: {
        count: 0,
        stationNodeIds: []
      }
    },
    overall: {
      totalStations: $station_count,
      totalChargers: ([.map.nodes[] | select(.target.Type == "ChargingStation") | .target.totalAmountOfChargers] | add),
      totalAvailable: ([.map.nodes[] | select(.target.Type == "ChargingStation") | .target.amountOfAvailableChargers] | add),
      totalBroken: ([.map.nodes[] | select(.target.Type == "ChargingStation") | .target.totalAmountOfBrokenChargers] | add),
      avgChargeSpeed: (
        [.map.nodes[] | select(.target.Type == "ChargingStation") | .target.chargeSpeedPerCharger] |
        if length > 0 then (add / length | round) else 0 end
      ),
      totalPossibleThroughput: (
        [.map.nodes[] | select(.target.Type == "ChargingStation") | 
         (.target.amountOfAvailableChargers * .target.chargeSpeedPerCharger)] | add
      ),
      healthPercentage: (
        ([.map.nodes[] | select(.target.Type == "ChargingStation") | .target.totalAmountOfChargers] | add) as $total |
        ([.map.nodes[] | select(.target.Type == "ChargingStation") | .target.totalAmountOfBrokenChargers] | add) as $broken |
        if $total > 0 then ((($total - $broken) / $total) * 100 | round) else 0 end
      )
    },
    byZone: (
      [.map.nodes[] | select(.target.Type == "ChargingStation")] |
      group_by(.zoneId) | map(
        . as $stations |
        (.[] | .zoneId) as $zoneId |
        ($root.map.zones[] | select(.id == $zoneId)) as $zone |
        {
          zoneId: .[0].zoneId,
          stationCount: length,
          totalChargers: ([.[].target.totalAmountOfChargers] | add),
          availableChargers: ([.[].target.amountOfAvailableChargers] | add),
          totalStorageCapacity: ([$zone.energyStorages[]?.capacityMWh] | add // 0),
          greenEnergyPercentage: (
            if ([$zone.energySources[]?.generationCapacity] | add // 0) > 0 then
              (([$zone.energySources[] | select(.type | isGreenEnergy) | .generationCapacity] | add // 0) / 
               ([$zone.energySources[]?.generationCapacity] | add) * 100 | round)
            else 0 end
          ),
          energySourceTypes: ([$zone.energySources[].type] | unique)
        }
      ) | sort_by(-.stationCount)
    ),
    energySources: {
      totalGreenGeneration: (
        [.map.zones[].energySources[] | select(.type | isGreenEnergy) | .generationCapacity] | add // 0
      ),
      totalFossilGeneration: (
        [.map.zones[].energySources[] | select(.type | isGreenEnergy | not) | select(.type != "Nuclear") | .generationCapacity] | add // 0
      ),
      totalNuclearGeneration: (
        [.map.zones[].energySources[] | select(.type == "Nuclear") | .generationCapacity] | add // 0
      ),
      totalStorageCapacity: (
        [.map.zones[].energyStorages[]?.capacityMWh] | add // 0
      ),
      sourceTypes: (
        [.map.zones[].energySources[]] | group_by(.type) | map({
          type: .[0].type,
          totalCapacity: ([.[].generationCapacity] | add),
          count: length,
          isGreen: (.[0].type | isGreenEnergy),
          classification: (.[0].type | classifyEnergySource)
        }) | sort_by(-.totalCapacity)
      )
    },
    capacityDistribution: {
      small: {
        label: "1-2 chargers",
        count: ([.map.nodes[] | select(.target.Type == "ChargingStation") | select(.target.totalAmountOfChargers <= 2)] | length)
      },
      medium: {
        label: "3-4 chargers",
        count: ([.map.nodes[] | select(.target.Type == "ChargingStation") | select(.target.totalAmountOfChargers >= 3 and .target.totalAmountOfChargers <= 4)] | length)
      },
      large: {
        label: "5+ chargers",
        count: ([.map.nodes[] | select(.target.Type == "ChargingStation") | select(.target.totalAmountOfChargers >= 5)] | length)
      }
    },
    speedDistribution: {
      slow: {
        label: "< 150 kW",
        count: ([.map.nodes[] | select(.target.Type == "ChargingStation") | select(.target.chargeSpeedPerCharger < 150)] | length)
      },
      medium: {
        label: "150-250 kW",
        count: ([.map.nodes[] | select(.target.Type == "ChargingStation") | select(.target.chargeSpeedPerCharger >= 150 and .target.chargeSpeedPerCharger <= 250)] | length)
      },
      fast: {
        label: "> 250 kW",
        count: ([.map.nodes[] | select(.target.Type == "ChargingStation") | select(.target.chargeSpeedPerCharger > 250)] | length)
      }
    }
  },
  recommendations: {
    highCapacity: [
      .map.nodes[] | select(.target.Type == "ChargingStation") |
      select(.target.amountOfAvailableChargers >= 4) |
      . as $station |
      (.zoneId) as $zoneId |
      ($root.map.zones[] | select(.id == $zoneId)) as $zone |
      {
        nodeId: .id,
        availableChargers: .target.amountOfAvailableChargers,
        chargeSpeed: .target.chargeSpeedPerCharger,
        totalThroughput: (.target.amountOfAvailableChargers * .target.chargeSpeedPerCharger),
        zoneId: .zoneId,
        greenEnergyPercentage: (
          if ([$zone.energySources[]?.generationCapacity] | add // 0) > 0 then
            (([$zone.energySources[] | select(.type | isGreenEnergy) | .generationCapacity] | add // 0) / 
             ([$zone.energySources[]?.generationCapacity] | add) * 100 | round)
          else 0 end
        ),
        hasStorage: ([$zone.energyStorages[]] | length > 0),
        reason: "High capacity station with 4+ available chargers"
      }
    ] | sort_by(-.totalThroughput),
    fastCharging: [
      .map.nodes[] | select(.target.Type == "ChargingStation") |
      select(.target.chargeSpeedPerCharger >= 250 and .target.amountOfAvailableChargers > 0) |
      . as $station |
      (.zoneId) as $zoneId |
      ($root.map.zones[] | select(.id == $zoneId)) as $zone |
      {
        nodeId: .id,
        chargeSpeed: .target.chargeSpeedPerCharger,
        availableChargers: .target.amountOfAvailableChargers,
        zoneId: .zoneId,
        greenEnergyPercentage: (
          if ([$zone.energySources[]?.generationCapacity] | add // 0) > 0 then
            (([$zone.energySources[] | select(.type | isGreenEnergy) | .generationCapacity] | add // 0) / 
             ([$zone.energySources[]?.generationCapacity] | add) * 100 | round)
          else 0 end
        ),
        reason: "Fast charging (250+ kW) with available chargers"
      }
    ] | sort_by(-.chargeSpeed),
    greenEnergy: [
      .map.nodes[] | select(.target.Type == "ChargingStation") |
      . as $station |
      (.zoneId) as $zoneId |
      ($root.map.zones[] | select(.id == $zoneId)) as $zone |
      select(([$zone.energySources[] | select(.type | isGreenEnergy)] | length) > 0) |
      select(.target.amountOfAvailableChargers > 0) |
      {
        nodeId: .id,
        availableChargers: .target.amountOfAvailableChargers,
        chargeSpeed: .target.chargeSpeedPerCharger,
        totalThroughput: (.target.amountOfAvailableChargers * .target.chargeSpeedPerCharger),
        zoneId: .zoneId,
        greenEnergyPercentage: (
          if ([$zone.energySources[]?.generationCapacity] | add // 0) > 0 then
            (([$zone.energySources[] | select(.type | isGreenEnergy) | .generationCapacity] | add // 0) / 
             ([$zone.energySources[]?.generationCapacity] | add) * 100 | round)
          else 0 end
        ),
        energySourceTypes: ([$zone.energySources[] | select(.type | isGreenEnergy) | .type] | unique),
        storageCapacity: ([$zone.energyStorages[]?.capacityMWh] | add // 0),
        reason: "Station in zone with renewable energy sources"
      }
    ] | sort_by(-.greenEnergyPercentage),
    needsMaintenance: [
      .map.nodes[] | select(.target.Type == "ChargingStation") |
      select(.target.totalAmountOfBrokenChargers > 0) |
      {
        nodeId: .id,
        brokenChargers: .target.totalAmountOfBrokenChargers,
        totalChargers: .target.totalAmountOfChargers,
        healthPercentage: (
          if .target.totalAmountOfChargers > 0 then
            ((.target.totalAmountOfChargers - .target.totalAmountOfBrokenChargers) / .target.totalAmountOfChargers * 100 | round)
          else 0 end
        ),
        zoneId: .zoneId,
        urgency: (
          if .target.totalAmountOfBrokenChargers >= 3 then "HIGH"
          elif .target.totalAmountOfBrokenChargers >= 2 then "MEDIUM"
          else "LOW" end
        )
      }
    ] | sort_by(-.brokenChargers),
    lowAvailability: [
      .map.nodes[] | select(.target.Type == "ChargingStation") |
      select(.target.amountOfAvailableChargers <= 1 and .target.amountOfAvailableChargers > 0) |
      {
        nodeId: .id,
        availableChargers: .target.amountOfAvailableChargers,
        totalChargers: .target.totalAmountOfChargers,
        zoneId: .zoneId,
        reason: "Low availability - may experience queuing"
      }
    ]
  }
}' > "$OUTPUT_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Charging station information saved to: $OUTPUT_FILE"
    echo ""
    echo "📈 Quick Stats:"
    jq -r '"   Total stations: \(.stationCount)
   Total chargers: \(.statistics.overall.totalChargers)
   Available chargers: \(.statistics.overall.totalAvailable)
   Broken chargers: \(.statistics.overall.totalBroken)
   Average charge speed: \(.statistics.overall.avgChargeSpeed) kW
   Network health: \(.statistics.overall.healthPercentage)%
   Renewable energy sources: \(.statistics.energySources.sourceTypes | map(select(.isGreen == true)) | length)
   Total storage capacity: \(.statistics.energySources.totalStorageCapacity) MWh"' "$OUTPUT_FILE"
    echo ""
    echo "🔍 View full details: cat $OUTPUT_FILE | jq ."
else
    echo "❌ Error generating charging station information"
    exit 1
fi
