#!/bin/bash

# Script to generate detailed customer information JSON for any Considition 2025 map
# Usage: ./generate-map-customers.sh <mapName>

if [ -z "$1" ]; then
    echo "Usage: $0 <mapName>"
    echo "Example: $0 Turbohill"
    exit 1
fi

MAP_NAME="$1"
MAP_DIR="maps/$(echo "$MAP_NAME" | tr '[:upper:]' '[:lower:]')"
MAP_FILE="${MAP_DIR}/$(echo "$MAP_NAME" | tr '[:upper:]' '[:lower:]')-map.json"
OUTPUT_FILE="${MAP_DIR}/$(echo "$MAP_NAME" | tr '[:upper:]' '[:lower:]')-customers.json"

echo "👥 Generating customer information for map: $MAP_NAME"
echo "================================================"

# Check if map file exists
if [ ! -f "$MAP_FILE" ]; then
    echo "❌ Error: Map file not found: $MAP_FILE"
    echo "💡 Tip: Run './fetch-map.sh $MAP_NAME' first to download the map"
    exit 1
fi

# Read map data from file
echo "📥 Reading map data from: $MAP_FILE"
MAP_DATA=$(cat "$MAP_FILE")

# Check if map has customers
CUSTOMER_COUNT=$(echo "$MAP_DATA" | jq '[.nodes[] | .customers[]] | length' 2>/dev/null || echo "0")

if [ "$CUSTOMER_COUNT" -eq "0" ]; then
    echo "❌ Error: No customers found in map data"
    exit 1
fi

echo "📊 Processing $CUSTOMER_COUNT customers..."

# Generate customer information using jq
echo "$MAP_DATA" | jq '{
  mapName: .name,
  generatedAt: (now | strftime("%Y-%m-%d %H:%M:%S")),
  customerCount: ([.nodes[] | .customers[]] | length),
  customers: [
    .nodes[] | .customers[] | {
      customerId: .id,
      persona: .persona,
      vehicleType: .type,
      fromNode: .fromNode,
      toNode: .toNode,
      departureTick: .departureTick,
      chargeRemaining: .chargeRemaining,
      maxCharge: .maxCharge,
      energyConsumptionPerKm: .energyConsumptionPerKm,
      state: .state,
      route: {
        from: .fromNode,
        to: .toNode,
        fromCoordinates: {
          x: (if .fromNode then (.fromNode | tostring | split(".")[0]) else null end),
          y: (if .fromNode then (.fromNode | tostring | split(".")[1]) else null end)
        },
        toCoordinates: {
          x: (if .toNode then (.toNode | tostring | split(".")[0]) else null end),
          y: (if .toNode then (.toNode | tostring | split(".")[1]) else null end)
        }
      },
      departure: {
        tick: .departureTick,
        timeOfDay: (
          if .departureTick then
            ((.departureTick * 5 / 60) | floor | tostring) + ":" + 
            (((.departureTick * 5) % 60) | tostring | if length == 1 then "0" + . else . end)
          else "unknown" end
        )
      },
      battery: {
        maxCharge: .maxCharge,
        initialCharge: .chargeRemaining,
        chargePercentage: (
          if .maxCharge > 0 then
            (.chargeRemaining / .maxCharge * 100 | round)
          else 0 end
        ),
        consumptionRate: .energyConsumptionPerKm
      },
      capabilities: {
        range_km: (
          if .energyConsumptionPerKm > 0 then
            (.chargeRemaining / .energyConsumptionPerKm)
          else 0
          end
        ),
        maxRange_km: (
          if .energyConsumptionPerKm > 0 then
            (.maxCharge / .energyConsumptionPerKm)
          else 0
          end
        )
      }
    }
  ],
  statistics: {
    personas: (
      [.nodes[] | .customers[]] | group_by(.persona) | map({
        persona: .[0].persona,
        count: length,
        percentage: ((length / ($customer_count | tonumber)) * 100 | round)
      }) | sort_by(-.count)
    ),
    vehicleTypes: (
      [.nodes[] | .customers[]] | group_by(.type) | map({
        type: .[0].type,
        count: length,
        percentage: ((length / ($customer_count | tonumber)) * 100 | round)
      }) | sort_by(-.count)
    ),
    batteryStats: {
      cars: {
        avgMaxCharge: (
          [.nodes[] | .customers[] | select(.type == "Car") | .maxCharge] | 
          if length > 0 then (add / length | round) else 0 end
        ),
        avgInitialCharge: (
          [.nodes[] | .customers[] | select(.type == "Car") | .chargeRemaining] | 
          if length > 0 then (add / length | round) else 0 end
        ),
        avgChargePercentage: (
          [.nodes[] | .customers[] | select(.type == "Car") | 
           if .maxCharge > 0 then (.chargeRemaining / .maxCharge * 100) else 0 end] | 
          if length > 0 then (add / length | round) else 0 end
        )
      },
      trucks: {
        avgMaxCharge: (
          [.nodes[] | .customers[] | select(.type == "Truck") | .maxCharge] | 
          if length > 0 then (add / length | round) else 0 end
        ),
        avgInitialCharge: (
          [.nodes[] | .customers[] | select(.type == "Truck") | .chargeRemaining] | 
          if length > 0 then (add / length | round) else 0 end
        ),
        avgChargePercentage: (
          [.nodes[] | .customers[] | select(.type == "Truck") | 
           if .maxCharge > 0 then (.chargeRemaining / .maxCharge * 100) else 0 end] | 
          if length > 0 then (add / length | round) else 0 end
        )
      }
    },
    departureStats: {
      earliest: ([.nodes[] | .customers[] | .departureTick] | min),
      latest: ([.nodes[] | .customers[] | .departureTick] | max),
      average: (
        [.nodes[] | .customers[] | .departureTick] | 
        if length > 0 then (add / length | round) else 0 end
      ),
      distribution: {
        "00:00-01:00": ([.nodes[] | .customers[] | select(.departureTick >= 0 and .departureTick < 12)] | length),
        "01:00-02:00": ([.nodes[] | .customers[] | select(.departureTick >= 12 and .departureTick < 24)] | length),
        "02:00-03:00": ([.nodes[] | .customers[] | select(.departureTick >= 24 and .departureTick < 36)] | length),
        "03:00-04:00": ([.nodes[] | .customers[] | select(.departureTick >= 36 and .departureTick < 48)] | length),
        "04:00+": ([.nodes[] | .customers[] | select(.departureTick >= 48)] | length)
      }
    },
    chargeCategories: {
      critical: {
        label: "< 20%",
        count: ([.nodes[] | .customers[] | select(.maxCharge > 0 and (.chargeRemaining / .maxCharge) < 0.20)] | length)
      },
      low: {
        label: "20-40%",
        count: ([.nodes[] | .customers[] | select(.maxCharge > 0 and (.chargeRemaining / .maxCharge) >= 0.20 and (.chargeRemaining / .maxCharge) < 0.40)] | length)
      },
      medium: {
        label: "40-60%",
        count: ([.nodes[] | .customers[] | select(.maxCharge > 0 and (.chargeRemaining / .maxCharge) >= 0.40 and (.chargeRemaining / .maxCharge) < 0.60)] | length)
      },
      high: {
        label: "60-80%",
        count: ([.nodes[] | .customers[] | select(.maxCharge > 0 and (.chargeRemaining / .maxCharge) >= 0.60 and (.chargeRemaining / .maxCharge) < 0.80)] | length)
      },
      full: {
        label: "80-100%",
        count: ([.nodes[] | .customers[] | select(.maxCharge > 0 and (.chargeRemaining / .maxCharge) >= 0.80)] | length)
      }
    }
  },
  recommendations: {
    mustChargeBefore: [
      .nodes[] | .customers[] | 
      select(.maxCharge > 0 and (.chargeRemaining / .maxCharge) < 0.20) |
      {
        customerId: .id,
        persona,
        vehicleType: .type,
        chargePercentage: ((.chargeRemaining / .maxCharge * 100) | round),
        departureTick,
        urgency: "CRITICAL"
      }
    ],
    shouldChargeBefore: [
      .nodes[] | .customers[] | 
      select(.maxCharge > 0 and (.chargeRemaining / .maxCharge) >= 0.20 and (.chargeRemaining / .maxCharge) < 0.40) |
      {
        customerId: .id,
        persona,
        vehicleType: .type,
        chargePercentage: ((.chargeRemaining / .maxCharge * 100) | round),
        departureTick,
        urgency: "HIGH"
      }
    ],
    monitorClosely: [
      .nodes[] | .customers[] | 
      select(.type == "Truck" and .maxCharge > 0 and (.chargeRemaining / .maxCharge) < 0.90) |
      {
        customerId: .id,
        persona,
        chargePercentage: ((.chargeRemaining / .maxCharge * 100) | round),
        departureTick,
        reason: "Truck with consumption 5x higher than cars"
      }
    ]
  }
}' --arg customer_count "$CUSTOMER_COUNT" > "$OUTPUT_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Customer information saved to: $OUTPUT_FILE"
    echo ""
    echo "📈 Quick Stats:"
    jq -r '"   Total customers: \(.customerCount)
   Personas: \(.statistics.personas | map("\(.persona): \(.count)") | join(", "))
   Vehicles: \(.statistics.vehicleTypes | map("\(.type): \(.count)") | join(", "))
   Critical charge (<20%): \(.statistics.chargeCategories.critical.count)
   High charge (>80%): \(.statistics.chargeCategories.full.count)"' "$OUTPUT_FILE"
    echo ""
    echo "🔍 View full details: cat $OUTPUT_FILE | jq ."
else
    echo "❌ Error generating customer information"
    exit 1
fi
