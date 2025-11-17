#!/usr/bin/env python3
"""
Visualize single customer journey
Usage: python visualize_customer_0_16.py <customer_id> [result_file]
"""

import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import sys
import os
import argparse
from pathlib import Path

def visualize_customer_journey(map_file: str, result_file: str, customer_id: str, output_file: str):
    """Visualize a single customer's journey"""
    
    # Load map data
    with open(map_file, 'r') as f:
        map_data = json.load(f)
    
    # Load game results
    with open(result_file, 'r') as f:
        results = json.load(f)
    
    # Build node positions lookup
    node_positions = {}
    for node in map_data['nodes']:
        node_positions[node['id']] = (node['posX'], node['posY'])
    
    # Find customer in results
    customer_log = None
    for log in results.get('customerLogs', []):
        if log['customerId'] == customer_id:
            customer_log = log
            break
    
    if not customer_log:
        print(f"❌ Customer {customer_id} not found in results")
        return
    
    # Get customer details from map data (initial customers)
    customer_info = None
    for node in map_data['nodes']:
        for customer in node.get('customers', []):
            if customer['id'] == customer_id:
                customer_info = customer
                break
        if customer_info:
            break
    
    # If not found in map (bonus customer), extract info from customer_log
    if not customer_info:
        first_log = customer_log['logs'][0] if customer_log['logs'] else {}
        customer_info = {
            'id': customer_id,
            'persona': customer_log.get('persona', 'Unknown'),
            'type': customer_log.get('vehicleType', 'Unknown'),
            'chargeRemaining': first_log.get('chargeRemaining', 0),
            'maxCharge': customer_log.get('maxCharge', 0),
            'energyConsumptionPerKm': 0,  # Not available for bonus customers
            'fromNode': first_log.get('node', '?'),
            'toNode': first_log.get('path', ['?'])[-1] if first_log.get('path') else '?',
            'departureTick': first_log.get('tick', 0)
        }
    
    # Create visualization
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))
    
    # ===== LEFT PLOT: Route Map =====
    dim_x = map_data['dimX']
    dim_y = map_data['dimY']
    
    ax1.set_xlim(-0.5, dim_x - 0.5)
    ax1.set_ylim(-0.5, dim_y - 0.5)
    ax1.set_aspect('equal')
    ax1.grid(True, alpha=0.3)
    ax1.set_xlabel('X Position', fontsize=12)
    ax1.set_ylabel('Y Position', fontsize=12)
    ax1.set_title(f'Customer {customer_id} Journey - {map_data["name"]}', 
                  fontsize=14, fontweight='bold')
    
    # Plot all edges (roads) in light gray
    for edge in map_data['edges']:
        from_pos = node_positions.get(edge['fromNode'])
        to_pos = node_positions.get(edge['toNode'])
        if from_pos and to_pos:
            ax1.plot([from_pos[0], to_pos[0]], 
                    [from_pos[1], to_pos[1]], 
                    'gray', alpha=0.15, linewidth=0.5, zorder=1)
    
    # Plot charging stations
    for node in map_data['nodes']:
        if node['target']['Type'] == 'ChargingStation':
            pos = node_positions[node['id']]
            ax1.scatter(pos[0], pos[1], c='orange', s=150, marker='s', 
                       edgecolors='black', linewidth=1.5, zorder=3, alpha=0.6)
            ax1.text(pos[0], pos[1] - 0.3, node['id'], 
                    ha='center', va='top', fontsize=8, color='black')
    
    # Extract customer's actual path from logs
    path_nodes = []
    charging_nodes = []
    original_path = []  # Original path from tick 0
    
    for log_entry in customer_log['logs']:
        node = log_entry.get('node')
        state = log_entry.get('state')
        tick = log_entry.get('tick', 0)
        
        # Capture original path from tick 0
        if tick == 0:
            path_from_log = log_entry.get('path', [])
            if path_from_log:
                original_path = path_from_log
        
        if node and node not in path_nodes:
            path_nodes.append(node)
        
        if state == 'Charging' and node:
            charging_nodes.append(node)
    
    # Plot original path from engine (tick 0) as dotted line
    if original_path and len(original_path) > 1:
        for i in range(len(original_path) - 1):
            from_node = original_path[i]
            to_node = original_path[i + 1]
            from_pos = node_positions.get(from_node)
            to_pos = node_positions.get(to_node)
            
            if from_pos and to_pos:
                ax1.plot([from_pos[0], to_pos[0]], 
                        [from_pos[1], to_pos[1]], 
                        'purple', linewidth=2, linestyle='--', alpha=0.5, zorder=1.5)
    
    # Plot customer's actual path (solid line on top)
    for i in range(len(path_nodes) - 1):
        from_node = path_nodes[i]
        to_node = path_nodes[i + 1]
        from_pos = node_positions.get(from_node)
        to_pos = node_positions.get(to_node)
        
        if from_pos and to_pos:
            ax1.plot([from_pos[0], to_pos[0]], 
                    [from_pos[1], to_pos[1]], 
                    'blue', linewidth=3, alpha=0.7, zorder=2)
            ax1.arrow(from_pos[0], from_pos[1],
                     (to_pos[0] - from_pos[0]) * 0.5,
                     (to_pos[1] - from_pos[1]) * 0.5,
                     head_width=0.15, head_length=0.1, 
                     fc='blue', ec='blue', alpha=0.7, zorder=2)
    
    # Highlight charging stations used
    for charging_node in set(charging_nodes):
        pos = node_positions.get(charging_node)
        if pos:
            ax1.scatter(pos[0], pos[1], c='green', s=300, marker='s',
                       edgecolors='black', linewidth=3, zorder=4, alpha=0.9)
            ax1.text(pos[0], pos[1] + 0.3, '⚡ CHARGED', 
                    ha='center', va='bottom', fontsize=9, 
                    fontweight='bold', color='green',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    # Mark start and end
    if customer_info:
        start_node = customer_info['fromNode']
        end_node = customer_info['toNode']
        
        start_pos = node_positions.get(start_node)
        end_pos = node_positions.get(end_node)
        
        if start_pos:
            ax1.scatter(start_pos[0], start_pos[1], c='green', s=400, 
                       marker='o', edgecolors='black', linewidth=3, zorder=5)
            ax1.text(start_pos[0], start_pos[1] - 0.5, 'START', 
                    ha='center', va='top', fontsize=10, fontweight='bold')
        
        if end_pos:
            ax1.scatter(end_pos[0], end_pos[1], c='red', s=500, 
                       marker='*', edgecolors='black', linewidth=3, zorder=5)
            ax1.text(end_pos[0], end_pos[1] + 0.5, 'END', 
                    ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # Add legend
    legend_elements = [
        plt.Line2D([0], [0], color='purple', linewidth=2, linestyle='--', 
                  label='Original Path (Tick 0)'),
        plt.Line2D([0], [0], color='blue', linewidth=3, label='Actual Path Traveled'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='green', 
                  markersize=12, label='Start Location'),
        plt.Line2D([0], [0], marker='*', color='w', markerfacecolor='red', 
                  markersize=15, label='Destination'),
        plt.Line2D([0], [0], marker='s', color='w', markerfacecolor='orange', 
                  markersize=10, label='Charging Station'),
        plt.Line2D([0], [0], marker='s', color='w', markerfacecolor='green', 
                  markersize=12, label='Used Charging Station')
    ]
    ax1.legend(handles=legend_elements, loc='upper left', fontsize=9)
    
    # ===== RIGHT PLOT: Battery & State Timeline =====
    ax2.set_xlabel('Tick', fontsize=12)
    ax2.set_ylabel('Battery Charge (%)', fontsize=12)
    ax2.set_title(f'Battery Level Over Time', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    
    # Extract timeline data
    ticks = []
    charges = []
    states = []
    
    for log_entry in customer_log['logs']:
        tick = log_entry.get('tick', 0)
        charge = log_entry.get('chargeRemaining', 0) * 100  # Convert to percentage
        state = log_entry.get('state', '')
        
        ticks.append(tick)
        charges.append(charge)
        states.append(state)
    
    # Plot battery level
    ax2.plot(ticks, charges, 'b-', linewidth=2, label='Battery Level')
    
    # Highlight charging periods
    charging_ticks = []
    charging_charges = []
    
    for i, state in enumerate(states):
        if state == 'Charging':
            charging_ticks.append(ticks[i])
            charging_charges.append(charges[i])
    
    if charging_ticks:
        ax2.scatter(charging_ticks, charging_charges, c='green', s=100, 
                   marker='o', edgecolors='black', linewidth=2, 
                   label='Charging', zorder=5)
    
    # Add horizontal lines for reference
    ax2.axhline(y=100, color='g', linestyle='--', alpha=0.3, label='Full (100%)')
    ax2.axhline(y=50, color='orange', linestyle='--', alpha=0.3, label='Half (50%)')
    ax2.axhline(y=20, color='r', linestyle='--', alpha=0.3, label='Low (20%)')
    
    ax2.set_ylim(0, 105)
    ax2.legend(loc='best', fontsize=9)
    
    # Add customer info text box
    if customer_info:
        info_text = f"Customer: {customer_id}\n"
        info_text += f"Persona: {customer_info.get('persona', 'Unknown')}\n"
        info_text += f"Vehicle: {customer_info.get('type', 'Unknown')}\n"
        info_text += f"Initial Charge: {customer_info.get('chargeRemaining', 0)*100:.1f}%\n"
        info_text += f"Max Battery: {customer_info.get('maxCharge', 0):.1f} kWh\n"
        info_text += f"Consumption: {customer_info.get('energyConsumptionPerKm', 0):.2f} kWh/km\n"
        info_text += f"Route: {customer_info.get('fromNode', '?')} → {customer_info.get('toNode', '?')}\n"
        info_text += f"Departure: Tick {customer_info.get('departureTick', 0)}\n"
        info_text += f"Final Charge: {charges[-1]:.1f}%"
        
        ax2.text(0.02, 0.98, info_text, transform=ax2.transAxes,
                fontsize=9, verticalalignment='top', family='monospace',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✅ Customer visualization saved to: {output_file}")
    
    # Print summary
    print(f"\n📊 Customer {customer_id} Summary:")
    print(f"   Persona: {customer_info.get('persona', 'Unknown')}")
    print(f"   Initial charge: {customer_info.get('chargeRemaining', 0)*100:.1f}%")
    print(f"   Final charge: {charges[-1]:.1f}%")
    print(f"   Charged at: {len(set(charging_nodes))} station(s)")
    print(f"   Total ticks: {len(ticks)}")
    print(f"   Path nodes: {len(path_nodes)}")
    
    plt.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Visualize a customer journey')
    parser.add_argument('customer_id', type=str, help='Customer ID (e.g., 0.16, 0.0)')
    parser.add_argument('--map-name', type=str, default='turbohill', help='Map name (default: turbohill)')
    parser.add_argument('--result-file', type=str, default=None, 
                       help='Path to result file (default: latest result from logs)')
    parser.add_argument('--output-file', type=str, default=None,
                       help='Output PNG file path (default: maps/<mapname>/customer_<id>.png)')
    
    args = parser.parse_args()
    
    map_name = args.map_name.lower()
    customer_id = args.customer_id
    
    # Construct paths
    base_dir = Path(__file__).parent.parent / 'maps' / map_name
    map_file = base_dir / f'{map_name}-map.json'
    
    # Determine result file
    if args.result_file:
        result_file = args.result_file
    else:
        # Use latest result from logs
        latest_dir = base_dir / 'logs' / 'latest'
        if latest_dir.exists():
            # Find the highest tick result file
            tick_dirs = sorted(latest_dir.glob('tick_*'), key=lambda x: int(x.name.split('_')[1]), reverse=True)
            if tick_dirs:
                result_file = tick_dirs[0] / f'{map_name}_tick_{tick_dirs[0].name.split("_")[1]}_result.json'
            else:
                print("❌ No tick results found in latest logs")
                sys.exit(1)
        else:
            print(f"❌ Latest logs directory not found: {latest_dir}")
            sys.exit(1)
    
    # Determine output file
    if args.output_file:
        output_file = args.output_file
    else:
        safe_customer_id = customer_id.replace('.', '_')
        output_file = base_dir / f'customer_{safe_customer_id}.png'
    
    # Validate files exist
    if not os.path.exists(map_file):
        print(f"❌ Map file not found: {map_file}")
        sys.exit(1)
    
    if not os.path.exists(result_file):
        print(f"❌ Result file not found: {result_file}")
        sys.exit(1)
    
    print(f"🎨 Visualizing customer {customer_id} journey...")
    print(f"   Map file:    {map_file}")
    print(f"   Result file: {result_file}")
    print(f"   Output file: {output_file}")
    
    visualize_customer_journey(str(map_file), str(result_file), customer_id, str(output_file))
    print(f"\n✅ Done!")

