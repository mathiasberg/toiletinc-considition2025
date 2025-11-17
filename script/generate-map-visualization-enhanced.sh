#!/bin/bash

# Enhanced Map Visualization Script for Considition 2025
# Features:
# - Customer start/end points with matching IDs and persona colors
# - Charging stations with capacity numbers and health-based colors
# - Zones with energy source information
# Usage: ./generate-map-visualization-enhanced.sh <mapName>

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

# Create map directory if it doesn't exist
mkdir -p "$MAP_DIR"

echo "🗺️  Enhanced Map Visualization Generator"
echo "========================================="
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

echo ""

# Step 2: Check if Python environment is set up
if [ ! -d "$PYTHON_DIR/venv" ]; then
    echo "📦 Python environment not found. Setting up..."
    cd "$PYTHON_DIR"
    ./setup.sh
    cd "$SCRIPT_DIR"
    echo ""
fi

# Step 3: Create enhanced Python visualization script
TEMP_SCRIPT="$PYTHON_DIR/visualize_enhanced_${MAP_NAME_LOWER}.py"

cat > "$TEMP_SCRIPT" << 'PYTHON_SCRIPT_EOF'
"""
Enhanced Map Visualizer
- Customer start/end points with matching IDs and persona-based colors
- Charging stations with capacity numbers and health-based colors
- Zones with energy source information
"""

import json
import sys
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import LineCollection
import numpy as np

# Persona color mapping
PERSONA_COLORS = {
    'Neutral': '#808080',           # Gray
    'CostSensitive': '#FFD700',     # Gold
    'DislikesDriving': '#FF6B6B',   # Red
    'EcoConscious': '#4CAF50',      # Green
    'Stressed': '#FF1493'           # Deep Pink
}

# Energy source colors
ENERGY_SOURCE_COLORS = {
    'Nuclear': '#9C27B0',    # Purple
    'Hydro': '#2196F3',      # Blue
    'Coal': '#424242',       # Dark gray
    'NaturalGas': '#FF9800', # Orange
    'Wind': '#00BCD4',       # Cyan
    'Solar': '#FFEB3B'       # Yellow
}

def get_station_health_color(available, broken):
    """Get color based on station health (availability ratio)"""
    total = available + broken
    if total == 0:
        return '#CCCCCC'  # Gray for no chargers
    
    availability_ratio = available / total
    
    if availability_ratio >= 0.8:
        return '#4CAF50'  # Green - Healthy
    elif availability_ratio >= 0.5:
        return '#FFC107'  # Amber - Warning
    elif availability_ratio >= 0.2:
        return '#FF9800'  # Orange - Poor
    else:
        return '#F44336'  # Red - Critical

def load_map_data(map_file):
    """Load map data from JSON file"""
    with open(map_file, 'r') as f:
        return json.load(f)

def visualize_enhanced_map(map_data, map_name, output_file):
    """Create enhanced map visualization"""
    
    # Create figure with larger size for better visibility
    fig = plt.figure(figsize=(24, 14))
    
    # Main map plot
    ax_main = plt.subplot(2, 2, (1, 3))  # Spans 2 rows, left side
    ax_legend = plt.subplot(2, 2, 2)     # Top right
    ax_stats = plt.subplot(2, 2, 4)      # Bottom right
    
    # Extract data
    nodes = {node['id']: node for node in map_data['nodes']}
    edges = map_data['edges']
    zones = map_data.get('zones', [])
    
    # --- MAIN MAP PLOT ---
    ax_main.set_title(f'{map_name} - Enhanced Map View', 
                      fontsize=18, fontweight='bold', pad=20)
    ax_main.set_xlabel('X Coordinate', fontsize=12)
    ax_main.set_ylabel('Y Coordinate', fontsize=12)
    ax_main.grid(True, alpha=0.2, linestyle='--')
    ax_main.set_aspect('equal')
    
    # Draw zones with energy source colors
    zone_patches = []
    for i, zone in enumerate(zones):
        x_start = zone['topLeftX']
        y_start = zone['topLeftY']
        width = zone['bottomRightX'] - zone['topLeftX']
        height = zone['bottomRightY'] - zone['topLeftY']
        
        # Get primary energy source
        sources = zone.get('energySources', [])
        if sources:
            primary_source = sources[0]['type']
            zone_color = ENERGY_SOURCE_COLORS.get(primary_source, '#F0F0F0')
        else:
            zone_color = '#F0F0F0'
        
        rect = mpatches.Rectangle(
            (x_start, y_start), width, height,
            linewidth=3, edgecolor='black', 
            facecolor=zone_color,
            alpha=0.15, zorder=0
        )
        ax_main.add_patch(rect)
        
        # Zone label with energy sources
        center_x = x_start + width / 2
        center_y = y_start + height / 2
        source_text = '\n'.join([s['type'] for s in sources])
        ax_main.text(center_x, center_y, f"{zone['id']}\n{source_text}", 
                    ha='center', va='center', fontsize=10, alpha=0.7, 
                    fontweight='bold', bbox=dict(boxstyle='round', 
                    facecolor='white', alpha=0.7, edgecolor='black'))
    
    # Draw edges (roads)
    edge_segments = []
    edge_colors = []
    
    for edge in edges:
        from_node = nodes.get(edge['fromNode'])
        to_node = nodes.get(edge['toNode'])
        
        if from_node and to_node:
            segment = [(from_node['posX'], from_node['posY']), 
                      (to_node['posX'], to_node['posY'])]
            edge_segments.append(segment)
            
            # Color by length
            length_normalized = min(edge['length'] / 50, 1.0)
            edge_colors.append((length_normalized, 1-length_normalized, 0, 0.2))
    
    lc = LineCollection(edge_segments, colors=edge_colors, linewidths=1.5, zorder=1)
    ax_main.add_collection(lc)
    
    # Draw regular nodes (small gray dots)
    regular_nodes = [node for node in nodes.values() 
                    if node.get('target', {}).get('Type') not in ['ChargingStation'] 
                    and len(node.get('customers', [])) == 0]
    
    if regular_nodes:
        regular_x = [n['posX'] for n in regular_nodes]
        regular_y = [n['posY'] for n in regular_nodes]
        ax_main.scatter(regular_x, regular_y, c='lightgray', s=20, 
                       alpha=0.4, edgecolors='gray', linewidth=0.5, zorder=2)
    
    # Draw charging stations with capacity numbers and health colors
    station_stats = {'healthy': 0, 'warning': 0, 'poor': 0, 'critical': 0}
    
    for node in nodes.values():
        target = node.get('target', {})
        if target.get('Type') == 'ChargingStation':
            x, y = node['posX'], node['posY']
            available = target.get('amountOfAvailableChargers', 0)
            broken = target.get('totalAmountOfBrokenChargers', 0)
            total = target.get('totalAmountOfChargers', available + broken)
            
            # Get health-based color
            color = get_station_health_color(available, broken)
            
            # Track stats
            ratio = available / total if total > 0 else 0
            if ratio >= 0.8:
                station_stats['healthy'] += 1
            elif ratio >= 0.5:
                station_stats['warning'] += 1
            elif ratio >= 0.2:
                station_stats['poor'] += 1
            else:
                station_stats['critical'] += 1
            
            # Draw station
            ax_main.scatter(x, y, c=color, s=600, marker='s',
                           alpha=0.9, edgecolors='black', linewidth=2.5, zorder=4)
            
            # Add capacity number
            ax_main.text(x, y, f'{total}', ha='center', va='center',
                        fontsize=10, fontweight='bold', color='white',
                        zorder=5)
            
            # Add node ID below
            ax_main.text(x, y-0.3, node['id'], ha='center', va='top',
                        fontsize=7, fontweight='bold', color='black',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='white', 
                                alpha=0.8, edgecolor='none'), zorder=5)
    
    # Draw customers with persona colors and matching IDs
    customer_data = []
    customer_id_counter = 1
    
    for node in nodes.values():
        customers = node.get('customers', [])
        for customer in customers:
            customer_data.append({
                'id': customer_id_counter,
                'customer_id': customer.get('id', f'C{customer_id_counter}'),
                'persona': customer.get('persona', 'Neutral'),
                'from': node['id'],
                'from_x': node['posX'],
                'from_y': node['posY'],
                'to': customer.get('toNode', 'Unknown'),
                'type': customer.get('type', 'Unknown')
            })
            customer_id_counter += 1
    
    # Add destination coordinates
    for cust in customer_data:
        dest_node = nodes.get(cust['to'])
        if dest_node:
            cust['to_x'] = dest_node['posX']
            cust['to_y'] = dest_node['posY']
        else:
            cust['to_x'] = cust['from_x']
            cust['to_y'] = cust['from_y']
    
    # Draw customer start and end points
    for cust in customer_data:
        persona = cust['persona']
        color = PERSONA_COLORS.get(persona, '#808080')
        cust_id = cust['id']
        
        # Draw line from start to end
        ax_main.plot([cust['from_x'], cust['to_x']], 
                    [cust['from_y'], cust['to_y']],
                    color=color, linewidth=2, alpha=0.5, 
                    linestyle='--', zorder=3)
        
        # Start point (circle)
        ax_main.scatter(cust['from_x'], cust['from_y'], 
                       c=color, s=250, marker='o',
                       alpha=0.9, edgecolors='black', linewidth=2, zorder=6)
        ax_main.text(cust['from_x'], cust['from_y'], str(cust_id),
                    ha='center', va='center', fontsize=9, 
                    fontweight='bold', color='white', zorder=7)
        
        # End point (triangle)
        ax_main.scatter(cust['to_x'], cust['to_y'], 
                       c=color, s=250, marker='^',
                       alpha=0.9, edgecolors='black', linewidth=2, zorder=6)
        ax_main.text(cust['to_x'], cust['to_y'], str(cust_id),
                    ha='center', va='center', fontsize=9, 
                    fontweight='bold', color='white', zorder=7)
    
    # --- LEGEND PANEL ---
    ax_legend.axis('off')
    ax_legend.set_title('Legend', fontsize=14, fontweight='bold', pad=10)
    
    legend_elements = []
    
    # Persona colors
    legend_elements.append(mpatches.Patch(color='none', label='Customer Personas:'))
    for persona, color in PERSONA_COLORS.items():
        legend_elements.append(mpatches.Patch(color=color, label=f'  {persona}'))
    
    legend_elements.append(mpatches.Patch(color='none', label=''))  # Spacer
    
    # Customer markers
    legend_elements.append(mpatches.Patch(color='none', label='Customer Markers:'))
    legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', 
                          markerfacecolor='gray', markersize=10, 
                          label='  ● Start Point'))
    legend_elements.append(plt.Line2D([0], [0], marker='^', color='w', 
                          markerfacecolor='gray', markersize=10, 
                          label='  ▲ End Point'))
    legend_elements.append(plt.Line2D([0], [0], linestyle='--', color='gray', 
                          linewidth=2, label='  -- Travel Path'))
    
    legend_elements.append(mpatches.Patch(color='none', label=''))  # Spacer
    
    # Station health
    legend_elements.append(mpatches.Patch(color='none', label='Station Health:'))
    legend_elements.append(mpatches.Patch(color='#4CAF50', label='  Healthy (≥80%)'))
    legend_elements.append(mpatches.Patch(color='#FFC107', label='  Warning (50-79%)'))
    legend_elements.append(mpatches.Patch(color='#FF9800', label='  Poor (20-49%)'))
    legend_elements.append(mpatches.Patch(color='#F44336', label='  Critical (<20%)'))
    
    legend_elements.append(mpatches.Patch(color='none', label=''))  # Spacer
    
    # Energy sources
    legend_elements.append(mpatches.Patch(color='none', label='Energy Sources:'))
    for source, color in ENERGY_SOURCE_COLORS.items():
        legend_elements.append(mpatches.Patch(color=color, alpha=0.5, label=f'  {source}'))
    
    ax_legend.legend(handles=legend_elements, loc='upper left', 
                    frameon=True, fontsize=9, ncol=1)
    
    # --- STATISTICS PANEL ---
    ax_stats.axis('off')
    ax_stats.set_title('Map Statistics', fontsize=14, fontweight='bold', pad=10)
    
    # Compile statistics
    stats_lines = []
    stats_lines.append(f"MAP: {map_name.upper()}")
    stats_lines.append("="*50)
    stats_lines.append(f"Grid Size: {map_data.get('dimX', 'N/A')}x{map_data.get('dimY', 'N/A')}")
    stats_lines.append(f"Total Nodes: {len(nodes)}")
    stats_lines.append(f"Total Edges: {len(edges)}")
    stats_lines.append(f"Zones: {len(zones)}")
    stats_lines.append("")
    
    stats_lines.append("CHARGING STATIONS")
    stats_lines.append("-"*50)
    total_stations = sum(1 for n in nodes.values() 
                        if n.get('target', {}).get('Type') == 'ChargingStation')
    stats_lines.append(f"Total Stations: {total_stations}")
    stats_lines.append(f"  Healthy: {station_stats['healthy']} (≥80%)")
    stats_lines.append(f"  Warning: {station_stats['warning']} (50-79%)")
    stats_lines.append(f"  Poor: {station_stats['poor']} (20-49%)")
    stats_lines.append(f"  Critical: {station_stats['critical']} (<20%)")
    
    # Calculate total capacity
    total_chargers = 0
    available_chargers = 0
    broken_chargers = 0
    
    for node in nodes.values():
        target = node.get('target', {})
        if target.get('Type') == 'ChargingStation':
            total_chargers += target.get('totalAmountOfChargers', 0)
            available_chargers += target.get('amountOfAvailableChargers', 0)
            broken_chargers += target.get('totalAmountOfBrokenChargers', 0)
    
    stats_lines.append("")
    stats_lines.append(f"Total Chargers: {total_chargers}")
    stats_lines.append(f"  Available: {available_chargers} ({available_chargers/total_chargers*100:.1f}%)")
    stats_lines.append(f"  Broken: {broken_chargers} ({broken_chargers/total_chargers*100:.1f}%)")
    stats_lines.append("")
    
    stats_lines.append("CUSTOMERS")
    stats_lines.append("-"*50)
    stats_lines.append(f"Total Customers: {len(customer_data)}")
    
    # Group by persona
    persona_counts = {}
    for cust in customer_data:
        persona = cust['persona']
        persona_counts[persona] = persona_counts.get(persona, 0) + 1
    
    for persona, count in sorted(persona_counts.items()):
        stats_lines.append(f"  {persona}: {count}")
    
    # Group by vehicle type
    vehicle_counts = {}
    for cust in customer_data:
        vtype = cust['type']
        vehicle_counts[vtype] = vehicle_counts.get(vtype, 0) + 1
    
    stats_lines.append("")
    for vtype, count in sorted(vehicle_counts.items()):
        stats_lines.append(f"  {vtype}: {count}")
    
    stats_lines.append("")
    stats_lines.append("ZONES")
    stats_lines.append("-"*50)
    for zone in zones:
        sources = [s['type'] for s in zone.get('energySources', [])]
        storages = zone.get('energyStorages', [])
        stats_lines.append(f"{zone['id']}")
        stats_lines.append(f"  Sources: {', '.join(sources) if sources else 'None'}")
        if storages:
            total_storage = sum(s.get('capacityMWh', 0) for s in storages)
            stats_lines.append(f"  Storage: {total_storage} MWh")
        else:
            stats_lines.append(f"  Storage: None")
    
    ax_stats.text(0.05, 0.95, '\n'.join(stats_lines), 
                 transform=ax_stats.transAxes,
                 fontsize=8,
                 verticalalignment='top',
                 fontfamily='monospace',
                 bbox={'boxstyle': 'round', 'facecolor': 'lightyellow', 
                       'alpha': 0.8, 'edgecolor': 'black'})
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Enhanced visualization saved to: {output_file}")
    
    # Print customer ID mapping
    print(f"\n📋 Customer ID Mapping:")
    print("-" * 80)
    for cust in customer_data[:20]:  # Show first 20
        print(f"ID {cust['id']:2d}: {cust['persona']:15s} | "
              f"{cust['from']} → {cust['to']} | {cust['type']}")
    if len(customer_data) > 20:
        print(f"... and {len(customer_data) - 20} more customers")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python script.py <map_file> <map_name> <output_file>")
        sys.exit(1)
    
    map_file = sys.argv[1]
    map_name = sys.argv[2]
    output_file = sys.argv[3]
    
    print(f"🗺️  Loading {map_name} map data...")
    map_data = load_map_data(map_file)
    
    print("🎨 Creating enhanced visualization...")
    visualize_enhanced_map(map_data, map_name, output_file)
    
    print("\n✅ Visualization complete!")

PYTHON_SCRIPT_EOF

# Step 4: Run the enhanced visualization
echo "🎨 Generating enhanced visualization..."
cd "$PYTHON_DIR"
source venv/bin/activate

# Create images directory if it doesn't exist
mkdir -p "$MAP_DIR/images"

OUTPUT_FILE="$MAP_DIR/images/${MAP_NAME_LOWER}-visualization-enhanced.png"
python "$TEMP_SCRIPT" "$DATA_FILE" "$MAP_NAME" "$OUTPUT_FILE"

# Cleanup temp script
rm "$TEMP_SCRIPT"

echo ""
echo "✅ Enhanced visualization complete!"
echo ""
echo "Generated file:"
echo "  📊 $OUTPUT_FILE"
echo ""
echo "View with:"
echo "  open $OUTPUT_FILE"
