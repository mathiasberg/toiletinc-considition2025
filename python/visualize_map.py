"""
Turbohill Map Visualizer
Creates an interactive visualization of the Considition 2025 map
"""

import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import LineCollection
import numpy as np

def load_map_data(map_file):
    """Load map data from JSON file"""
    with open(map_file, 'r') as f:
        return json.load(f)

def visualize_map(map_data, output_file=None):
    """
    Create a comprehensive visualization of the map
    """
    # Create figure with subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 10))
    
    # Extract data
    nodes = {node['id']: node for node in map_data['nodes']}
    edges = map_data['edges']
    zones = map_data['zones']
    
    # --- PLOT 1: Full Map with Roads and Stations ---
    ax1.set_title('Turbohill Map - Road Network & Charging Stations', fontsize=16, fontweight='bold')
    ax1.set_xlabel('X Coordinate')
    ax1.set_ylabel('Y Coordinate')
    ax1.grid(True, alpha=0.3)
    ax1.set_aspect('equal')
    
    # Draw zones as colored rectangles
    zone_colors = {
        '0.0<-->4.4': '#FFE5E5',  # Light red - Nuclear+NaturalGas
        '0.5<-->4.9': '#E5E5E5',  # Gray - Coal
        '5.0<-->9.4': '#E5FFE5',  # Light green - Hydro
        '5.5<-->9.9': '#E5F5FF'   # Light blue - Nuclear+Hydro
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
        
        # Add zone label
        center_x = x_start + width / 2
        center_y = y_start + height / 2
        sources = ' + '.join([s['type'] for s in zone['energySources']])
        ax1.text(center_x, center_y, f"{zone['id']}\n{sources}", 
                ha='center', va='center', fontsize=8, alpha=0.6, fontweight='bold')
    
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
            
            # Color by length (shorter = green, longer = red)
            length_normalized = min(edge['length'] / 50, 1.0)
            edge_colors.append((length_normalized, 1-length_normalized, 0, 0.3))
    
    lc = LineCollection(edge_segments, colors=edge_colors, linewidths=1, zorder=1)
    ax1.add_collection(lc)
    
    # Draw nodes
    node_x = []
    node_y = []
    node_colors = []
    node_sizes = []
    
    charging_x = []
    charging_y = []
    
    customer_x = []
    customer_y = []
    
    for node_id, node in nodes.items():
        node_x.append(node['posX'])
        node_y.append(node['posY'])
        
        # Check if node has charging station
        if node.get('target', {}).get('Type') == 'ChargingStation':
            charging_x.append(node['posX'])
            charging_y.append(node['posY'])
            node_colors.append('gold')
            node_sizes.append(200)
        # Check if node has customers
        elif len(node.get('customers', [])) > 0:
            customer_x.append(node['posX'])
            customer_y.append(node['posY'])
            node_colors.append('blue')
            node_sizes.append(100)
        else:
            node_colors.append('lightgray')
            node_sizes.append(30)
    
    # Draw regular nodes
    ax1.scatter(node_x, node_y, c=node_colors, s=node_sizes, 
               alpha=0.6, edgecolors='black', linewidth=0.5, zorder=2)
    
    # Highlight charging stations
    ax1.scatter(charging_x, charging_y, c='gold', s=300, marker='s',
               alpha=0.8, edgecolors='orange', linewidth=2, zorder=3, label='Charging Station')
    
    # Highlight customer locations
    ax1.scatter(customer_x, customer_y, c='blue', s=150, marker='o',
               alpha=0.8, edgecolors='darkblue', linewidth=2, zorder=3, label='Customer Home')
    
    ax1.legend(loc='upper right')
    
    # --- PLOT 2: Zone Analysis ---
    ax2.set_title('Zone Energy Mix & Infrastructure', fontsize=16, fontweight='bold')
    ax2.axis('off')
    
    # Create zone info text
    info_text = []
    info_text.append("TURBOHILL MAP ANALYSIS\n" + "="*50 + "\n")
    info_text.append(f"Grid: {map_data['dimX']}x{map_data['dimY']}")
    info_text.append(f"Total Nodes: {len(nodes)}")
    info_text.append(f"Total Edges: {len(edges)}")
    info_text.append(f"Charging Stations: {len(charging_x)}")
    info_text.append(f"Customer Start Points: {len(customer_x)}\n")
    
    info_text.append("ZONE BREAKDOWN\n" + "="*50)
    
    for zone in zones:
        info_text.append(f"\n📍 {zone['id']}")
        info_text.append(f"   Bounds: ({zone['topLeftX']},{zone['topLeftY']}) to ({zone['bottomRightX']},{zone['bottomRightY']})")
        
        sources = [f"   • {s['type']} ({s['generationCapacity']} capacity)" 
                  for s in zone['energySources']]
        info_text.append("   Energy Sources:")
        info_text.extend(sources)
        
        if zone['energyStorages']:
            info_text.append("   Energy Storage:")
            for storage in zone['energyStorages']:
                info_text.append(f"   • {storage['capacityMWh']} MWh (±{storage['maxChargePowerMw']} MW)")
        else:
            info_text.append("   Energy Storage: None")
        
        # Count charging stations in zone
        stations_in_zone = sum(1 for node in nodes.values() 
                             if node['zoneId'] == zone['id'] and 
                             node.get('target', {}).get('Type') == 'ChargingStation')
        info_text.append(f"   Charging Stations: {stations_in_zone}")
    
    info_text.append("\n" + "="*50)
    info_text.append("LEGEND")
    info_text.append("="*50)
    info_text.append("🟨 Yellow Square = Charging Station")
    info_text.append("🔵 Blue Circle = Customer Home")
    info_text.append("⚪ Gray Dot = Regular Node")
    info_text.append("\nEdge Colors:")
    info_text.append("  Green = Short roads")
    info_text.append("  Red = Long roads")
    
    # Display info text
    ax2.text(0.05, 0.95, '\n'.join(info_text), 
            transform=ax2.transAxes,
            fontsize=9,
            verticalalignment='top',
            fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✅ Map visualization saved to: {output_file}")
    
    plt.show()

def create_heatmap(map_data, output_file=None):
    """
    Create a heatmap showing customer density and charging station coverage
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
    
    nodes = {node['id']: node for node in map_data['nodes']}
    dim_x = map_data['dimX']
    dim_y = map_data['dimY']
    
    # Create grids for heatmaps
    customer_grid = np.zeros((dim_y, dim_x))
    station_grid = np.zeros((dim_y, dim_x))
    
    for node in nodes.values():
        x, y = int(node['posX']), int(node['posY'])
        
        # Customer count
        customer_grid[y][x] = len(node.get('customers', []))
        
        # Charging station
        if node.get('target', {}).get('Type') == 'ChargingStation':
            station_grid[y][x] = 1
    
    # Plot customer density
    im1 = ax1.imshow(customer_grid, cmap='YlOrRd', interpolation='nearest', origin='lower')
    ax1.set_title('Customer Home Locations', fontsize=14, fontweight='bold')
    ax1.set_xlabel('X Coordinate')
    ax1.set_ylabel('Y Coordinate')
    plt.colorbar(im1, ax=ax1, label='Number of Customers')
    
    # Plot charging stations
    im2 = ax2.imshow(station_grid, cmap='YlGn', interpolation='nearest', origin='lower')
    ax2.set_title('Charging Station Distribution', fontsize=14, fontweight='bold')
    ax2.set_xlabel('X Coordinate')
    ax2.set_ylabel('Y Coordinate')
    plt.colorbar(im2, ax=ax2, label='Has Station (1=Yes, 0=No)')
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✅ Heatmap saved to: {output_file}")
    
    plt.show()

if __name__ == "__main__":
    # Load map data
    map_file = '../turbohill-map.json'
    
    print("🗺️  Loading Turbohill map data...")
    map_data = load_map_data(map_file)
    
    print("📊 Creating visualizations...")
    print("\n1. Creating main map visualization...")
    visualize_map(map_data, output_file='turbohill-map-visualization.png')
    
    print("\n2. Creating heatmap analysis...")
    create_heatmap(map_data, output_file='turbohill-heatmap.png')
    
    print("\n✅ All visualizations complete!")
    print("   - turbohill-map-visualization.png")
    print("   - turbohill-heatmap.png")
