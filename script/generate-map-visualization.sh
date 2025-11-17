#!/bin/bash

# Script to generate map visualizations for any Considition 2025 map
# Usage: ./generate-map-visualization.sh <mapName>

if [ -z "$1" ]; then
    echo "Usage: $0 <mapName>"
    echo "Example: $0 Turbohill"
    exit 1
fi

MAP_NAME="$1"
BASE_URL="${BASE_URL:-http://localhost:8080}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_DIR="$SCRIPT_DIR/python"
MAP_NAME_LOWER=$(echo "$MAP_NAME" | tr '[:upper:]' '[:lower:]')
MAP_DIR="$SCRIPT_DIR/maps/$MAP_NAME_LOWER"
DATA_FILE="$MAP_DIR/${MAP_NAME_LOWER}-map.json"
CONFIG_FILE="$MAP_DIR/${MAP_NAME_LOWER}-map-config.json"

# Create map directory if it doesn't exist
mkdir -p "$MAP_DIR"

echo "🗺️  Map Visualization Generator"
echo "================================="
echo ""
echo "Map: $MAP_NAME"
echo ""

# Step 1: Check if map data exists, if not fetch it
if [ ! -f "$DATA_FILE" ]; then
    echo "📥 Fetching map data from API..."
    MAP_DATA=$(curl -s "${BASE_URL}/api/map?mapName=${MAP_NAME}")
    
    if echo "$MAP_DATA" | grep -q "Not Found"; then
        echo "❌ Error: Map '$MAP_NAME' not found in API"
        exit 1
    fi
    
    echo "$MAP_DATA" > "$DATA_FILE"
    echo "✅ Map data saved to: $DATA_FILE"
else
    echo "✅ Using existing map data: $DATA_FILE"
fi

# Check if config exists, if not fetch it
if [ ! -f "$CONFIG_FILE" ]; then
    echo "📥 Fetching map config from API..."
    CONFIG_DATA=$(curl -s "${BASE_URL}/api/map-config?mapName=${MAP_NAME}")
    
    if echo "$CONFIG_DATA" | grep -q "Not Found"; then
        echo "⚠️  Warning: Map config not found in API, continuing without it"
    else
        echo "$CONFIG_DATA" > "$CONFIG_FILE"
        echo "✅ Map config saved to: $CONFIG_FILE"
    fi
else
    echo "✅ Using existing map config: $CONFIG_FILE"
fi

echo ""

# Step 2: Check if Python environment is set up
if [ ! -d "$PYTHON_DIR/venv" ]; then
    echo "📦 Python environment not found. Setting up..."
    cd "$PYTHON_DIR"
    ./setup.sh
    cd "$SCRIPT_DIR"
    echo ""
fi

# Step 3: Create Python script for this specific map
MAP_NAME_LOWER=$(echo "$MAP_NAME" | tr '[:upper:]' '[:lower:]')
TEMP_SCRIPT="$PYTHON_DIR/visualize_${MAP_NAME_LOWER}.py"

cat > "$TEMP_SCRIPT" << 'PYTHON_SCRIPT_EOF'
"""
Map Visualizer - Generated script
"""

import json
import sys
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import LineCollection
import numpy as np

def load_map_data(map_file):
    """Load map data from JSON file"""
    with open(map_file, 'r') as f:
        return json.load(f)

def load_config_data(config_file):
    """Load config data from JSON file"""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def visualize_map(map_data, map_name, output_file, config_data=None):
    """Create map visualization"""
    
    # Create figure with larger size and better proportions
    fig = plt.figure(figsize=(28, 14))
    ax1 = plt.subplot(1, 2, 1)
    ax2 = plt.subplot(1, 2, 2)
    
    # Give more space to the map (left plot)
    plt.subplots_adjust(left=0.05, right=0.95, wspace=0.15)
    
    # Extract data
    nodes = {node['id']: node for node in map_data['nodes']}
    edges = map_data['edges']
    zones = map_data.get('zones', [])
    
    # --- PLOT 1: Full Map ---
    ax1.set_title(f'{map_name} Map - Road Network & Charging Stations', 
                  fontsize=16, fontweight='bold')
    ax1.set_xlabel('X Coordinate')
    ax1.set_ylabel('Y Coordinate')
    ax1.grid(True, alpha=0.3)
    ax1.set_aspect('equal')
    
    # Draw zones
    zone_colors = {
        '0.0<-->4.4': '#FFE5E5',
        '0.5<-->4.9': '#E5E5E5',
        '5.0<-->9.4': '#E5FFE5',
        '5.5<-->9.9': '#E5F5FF'
    }
    
    for zone in zones:
        x_start = zone['topLeftX']
        y_start = zone['topLeftY']
        width = zone['bottomRightX'] - zone['topLeftX']
        height = zone['bottomRightY'] - zone['topLeftY']
        
        rect = mpatches.Rectangle(
            (x_start, y_start), width, height,
            linewidth=2, edgecolor='black', 
            facecolor=zone_colors.get(zone['id'], '#FFFFFF'),
            alpha=0.3, zorder=0
        )
        ax1.add_patch(rect)
        
        # Zone label
        center_x = x_start + width / 2
        center_y = y_start + height / 2
        sources = ' + '.join([s['type'] for s in zone.get('energySources', [])])
        ax1.text(center_x, center_y, f"{zone['id']}\n{sources}", 
                ha='center', va='center', fontsize=8, alpha=0.6, fontweight='bold')
    
    # Draw edges
    edge_segments = []
    edge_colors = []
    
    for edge in edges:
        from_node = nodes.get(edge['fromNode'])
        to_node = nodes.get(edge['toNode'])
        
        if from_node and to_node:
            segment = [(from_node['posX'], from_node['posY']), 
                      (to_node['posX'], to_node['posY'])]
            edge_segments.append(segment)
            
            length_normalized = min(edge['length'] / 50, 1.0)
            edge_colors.append((length_normalized, 1-length_normalized, 0, 0.3))
    
    lc = LineCollection(edge_segments, colors=edge_colors, linewidths=1, zorder=1)
    ax1.add_collection(lc)
    
    # Draw nodes
    charging_x = []
    charging_y = []
    customer_x = []
    customer_y = []
    regular_x = []
    regular_y = []
    
    for node in nodes.values():
        if node.get('target', {}).get('Type') == 'ChargingStation':
            charging_x.append(node['posX'])
            charging_y.append(node['posY'])
        elif len(node.get('customers', [])) > 0:
            customer_x.append(node['posX'])
            customer_y.append(node['posY'])
        else:
            regular_x.append(node['posX'])
            regular_y.append(node['posY'])
    
    # Draw different node types
    ax1.scatter(regular_x, regular_y, c='lightgray', s=30, 
               alpha=0.6, edgecolors='black', linewidth=0.5, zorder=2)
    ax1.scatter(customer_x, customer_y, c='blue', s=150, marker='o',
               alpha=0.8, edgecolors='darkblue', linewidth=2, zorder=3, label='Customer Home')
    ax1.scatter(charging_x, charging_y, c='gold', s=300, marker='s',
               alpha=0.8, edgecolors='orange', linewidth=2, zorder=3, label='Charging Station')
    
    # Label charging stations with capacity
    for node in nodes.values():
        if node.get('target', {}).get('Type') == 'ChargingStation':
            station = node.get('chargingStation', {})
            available = station.get('available', 0)
            broken = station.get('broken', 0)
            total = available + broken
            node_id = node['id']
            
            # Show capacity number above station
            ax1.text(node['posX'], node['posY'] + 0.3, str(total), 
                    ha='center', va='bottom', fontsize=8, fontweight='bold',
                    color='darkred', zorder=4)
            # Show node ID below station
            ax1.text(node['posX'], node['posY'] - 0.3, node_id, 
                    ha='center', va='top', fontsize=7, 
                    color='black', alpha=0.7, zorder=4)
    
    ax1.legend(loc='upper right')
    
    # --- PLOT 2: Statistics ---
    ax2.set_title(f'{map_name} Statistics', fontsize=16, fontweight='bold')
    ax2.axis('off')
    
    # Create info text
    info_lines = []
    info_lines.append(f"{map_name.upper()} MAP ANALYSIS")
    info_lines.append("="*50)
    
    # Add config info if available
    if config_data:
        info_lines.append(f"Simulation Duration: {config_data.get('ticks', 'N/A')} ticks")
        info_lines.append(f"Initial Customers: {config_data.get('customers', 'N/A')}")
        info_lines.append(f"New Customer Wait: {config_data.get('newCustomerMinWait', 'N/A')}-{config_data.get('newCustomerMaxWait', 'N/A')} ticks")
        info_lines.append("")
        
        # Vehicle info
        cars = config_data.get('cars', {})
        trucks = config_data.get('trucks', {})
        info_lines.append("VEHICLE SPECIFICATIONS")
        info_lines.append("-"*50)
        info_lines.append(f"Cars:")
        info_lines.append(f"  Speed: {cars.get('minBaseSpeed', 'N/A')}-{cars.get('maxBaseSpeed', 'N/A')} km/h")
        info_lines.append(f"  Battery: {cars.get('minBatteryCapacity', 'N/A')}-{cars.get('maxBatteryCapacity', 'N/A')} kWh")
        info_lines.append(f"  Consumption: {cars.get('minConsumptionPerKm', 'N/A')}-{cars.get('maxConsumptionPerKm', 'N/A')} kWh/km")
        info_lines.append(f"Trucks ({int(config_data.get('percentageTrucks', 0)*100)}% of fleet):")
        info_lines.append(f"  Speed: {trucks.get('minBaseSpeed', 'N/A')}-{trucks.get('maxBaseSpeed', 'N/A')} km/h")
        info_lines.append(f"  Battery: {trucks.get('minBatteryCapacity', 'N/A')}-{trucks.get('maxBatteryCapacity', 'N/A')} kWh")
        info_lines.append(f"  Consumption: {trucks.get('minConsumptionPerKm', 'N/A')}-{trucks.get('maxConsumptionPerKm', 'N/A')} kWh/km")
        info_lines.append("")
        
        # Persona distribution
        personas_map = {0: "Neutral", 1: "EcoConscious", 2: "CostSensitive", 3: "Stressed", 4: "DislikesDriving"}
        personas = config_data.get('personas', [])
        if personas:
            info_lines.append("CUSTOMER PERSONAS")
            info_lines.append("-"*50)
            for p in personas:
                persona_name = personas_map.get(p.get('persona'), f"Unknown({p.get('persona')})")
                pct = p.get('percentage', 0)
                if pct == -1:
                    info_lines.append(f"  {persona_name}: Remaining %")
                else:
                    info_lines.append(f"  {persona_name}: {pct}%")
            info_lines.append("")
        
        # Charging station info
        info_lines.append("CHARGING INFRASTRUCTURE")
        info_lines.append("-"*50)
        info_lines.append(f"Stations: {config_data.get('chargingStations', 'N/A')}")
        info_lines.append(f"Max Chargers/Station: {config_data.get('maxChargersPerStation', 'N/A')}")
        info_lines.append(f"Charger Speed: {config_data.get('minChargerSpeed', 'N/A')}-{config_data.get('maxChargerSpeed', 'N/A')} kW")
        info_lines.append(f"Broken Chargers: {config_data.get('minBrokenChargerPercentage', 0)*100:.0f}%-{config_data.get('maxBrokenChargerPercentage', 0)*100:.0f}%")
        info_lines.append("")
    
    info_lines.append(f"Grid: {map_data.get('dimX', 'N/A')}x{map_data.get('dimY', 'N/A')}")
    info_lines.append(f"Total Nodes: {len(nodes)}")
    info_lines.append(f"Total Edges: {len(edges)}")
    info_lines.append(f"Charging Stations: {len(charging_x)}")
    info_lines.append(f"Customer Start Points: {len(customer_x)}")
    info_lines.append("")
    
    # Add charging station details
    info_lines.append("CHARGING STATIONS")
    info_lines.append("="*50)
    charging_stations = [(node['id'], node.get('chargingStation', {})) 
                         for node in nodes.values() 
                         if node.get('target', {}).get('Type') == 'ChargingStation']
    
    total_capacity = 0
    total_available = 0
    total_broken = 0
    
    for node_id, station in sorted(charging_stations):
        available = station.get('available', 0)
        broken = station.get('broken', 0)
        total = available + broken
        total_capacity += total
        total_available += available
        total_broken += broken
        
        status = "OK" if broken == 0 else f"{broken} broken"
        info_lines.append(f"{node_id}: {total} chargers ({available} avail, {status})")
    
    info_lines.append("")
    info_lines.append(f"TOTAL: {total_capacity} chargers")
    info_lines.append(f"  Available: {total_available}")
    info_lines.append(f"  Broken: {total_broken}")
    info_lines.append("")
    
    if zones:
        info_lines.append("ZONE BREAKDOWN")
        info_lines.append("="*50)
        
        for zone in zones:
            info_lines.append(f"\n{zone['id']}")
            info_lines.append(f"  Bounds: ({zone['topLeftX']},{zone['topLeftY']}) to ({zone['bottomRightX']},{zone['bottomRightY']})")
            
            sources = zone.get('energySources', [])
            if sources:
                info_lines.append("  Energy Sources:")
                for s in sources:
                    info_lines.append(f"    - {s['type']} ({s.get('generationCapacity', 'N/A')} capacity)")
            
            storages = zone.get('energyStorages', [])
            if storages:
                info_lines.append("  Energy Storage:")
                for storage in storages:
                    info_lines.append(f"    - {storage['capacityMWh']} MWh (charge: {storage.get('maxChargePower', 'N/A')}MW, discharge: {storage.get('maxDischargePower', 'N/A')}MW)")
            else:
                info_lines.append("  Energy Storage: None")
            
            stations_in_zone = sum(1 for node in nodes.values() 
                                 if node.get('zoneId') == zone['id'] and 
                                 node.get('target', {}).get('Type') == 'ChargingStation')
            info_lines.append(f"  Charging Stations: {stations_in_zone}")
    
    info_lines.append("")
    info_lines.append("="*50)
    info_lines.append("LEGEND")
    info_lines.append("="*50)
    info_lines.append("Yellow Square = Charging Station")
    info_lines.append("Blue Circle = Customer Home")
    info_lines.append("Gray Dot = Regular Node")
    info_lines.append("")
    info_lines.append("Edge Colors:")
    info_lines.append("  Green = Short roads")
    info_lines.append("  Red = Long roads")
    
    ax2.text(0.05, 0.95, '\n'.join(info_lines), 
            transform=ax2.transAxes,
            fontsize=7,
            verticalalignment='top',
            fontfamily='monospace',
            bbox={'boxstyle': 'round', 'facecolor': 'wheat', 'alpha': 0.3})
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Visualization saved to: {output_file}")

def create_heatmap(map_data, map_name, output_file):
    """Create heatmap visualization"""
    
    fig = plt.figure(figsize=(16, 8))
    ax1 = plt.subplot(1, 2, 1)
    ax2 = plt.subplot(1, 2, 2)
    
    nodes = {node['id']: node for node in map_data['nodes']}
    dim_x = map_data.get('dimX', 10)
    dim_y = map_data.get('dimY', 10)
    
    # Create grids
    customer_grid = np.zeros((dim_y, dim_x))
    station_grid = np.zeros((dim_y, dim_x))
    
    for node in nodes.values():
        x, y = int(node['posX']), int(node['posY'])
        if 0 <= x < dim_x and 0 <= y < dim_y:
            customer_grid[y][x] = len(node.get('customers', []))
            if node.get('target', {}).get('Type') == 'ChargingStation':
                station_grid[y][x] = 1
    
    # Plot customer density
    im1 = ax1.imshow(customer_grid, cmap='YlOrRd', interpolation='nearest', origin='lower')
    ax1.set_title(f'{map_name} - Customer Home Locations', fontsize=14, fontweight='bold')
    ax1.set_xlabel('X Coordinate')
    ax1.set_ylabel('Y Coordinate')
    plt.colorbar(im1, ax=ax1, label='Number of Customers')
    
    # Plot charging stations
    im2 = ax2.imshow(station_grid, cmap='YlGn', interpolation='nearest', origin='lower')
    ax2.set_title(f'{map_name} - Charging Station Distribution', fontsize=14, fontweight='bold')
    ax2.set_xlabel('X Coordinate')
    ax2.set_ylabel('Y Coordinate')
    plt.colorbar(im2, ax=ax2, label='Has Station (1=Yes, 0=No)')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Heatmap saved to: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python script.py <map_file> <map_name> <output_prefix> [config_file]")
        sys.exit(1)
    
    map_file = sys.argv[1]
    map_name = sys.argv[2]
    output_prefix = sys.argv[3]
    config_file = sys.argv[4] if len(sys.argv) > 4 else None
    
    print(f"🗺️  Loading {map_name} map data...")
    map_data = load_map_data(map_file)
    
    config_data = None
    if config_file:
        print(f"� Loading {map_name} config data...")
        config_data = load_config_data(config_file)
    
    print("�📊 Creating visualizations...")
    visualize_map(map_data, map_name, f"{output_prefix}-visualization.png", config_data)
    create_heatmap(map_data, map_name, f"{output_prefix}-heatmap.png")
    
    print("\n✅ All visualizations complete!")

PYTHON_SCRIPT_EOF

# Step 4: Run the visualization
echo "🎨 Generating visualizations..."
cd "$PYTHON_DIR"
source venv/bin/activate

python "$TEMP_SCRIPT" "$DATA_FILE" "$MAP_NAME" "$MAP_DIR/${MAP_NAME_LOWER}" "$CONFIG_FILE"

# Cleanup temp script
rm "$TEMP_SCRIPT"

echo ""
echo "✅ Visualization complete!"
echo ""
echo "Generated files in maps/${MAP_NAME_LOWER}/:"
echo "  📊 ${MAP_NAME_LOWER}-visualization.png"
echo "  📈 ${MAP_NAME_LOWER}-heatmap.png"
echo ""
echo "View them with:"
echo "  open maps/${MAP_NAME_LOWER}/${MAP_NAME_LOWER}-visualization.png"
echo "  open maps/${MAP_NAME_LOWER}/${MAP_NAME_LOWER}-heatmap.png"
