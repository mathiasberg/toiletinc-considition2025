#!/usr/bin/env python3
"""
Collect zone and weather data by running a strategy and aggregating zoneLogs.

This script:
1. Runs automated_persona_strategy.py to generate tick-by-tick results
2. Reads zoneLogs from each tick's result file
3. Aggregates all zoneLogs into a single file for later use
4. Preserves the exact structure for easy lookup by tick

Usage:
    python collect_zone_weather_data.py <map_name>
    
Example:
    python collect_zone_weather_data.py Turbohill
"""

import json
import sys
import subprocess
import math
from pathlib import Path


def run_strategy(map_name):
    """
    Run the automated persona strategy directly to generate tick-by-tick results.
    Always runs to max ticks for the map.
    Returns True if successful, False otherwise.
    """
    print(f"🚀 Running automated_persona strategy for {map_name}...")
    print("=" * 80)
    
    # Determine the Python executable (use venv if available)
    python_dir = Path(__file__).parent
    venv_python = python_dir / "venv" / "bin" / "python"
    python_exe = str(venv_python) if venv_python.exists() else "python3"
    
    # Use the python directory as the working directory
    python_cwd = str(python_dir)
    
    try:
        # Run the strategy directly with iterative mode (no end-tick, will use max from map config)
        result = subprocess.run(
            [python_exe, "strategies/automated_persona_strategy.py",
             "--map-name", map_name,
             "--mode", "iterative",
             "--strategy-config", "default"],
            cwd=python_cwd,
            capture_output=True,
            text=True,
            check=True
        )
        
        print(result.stdout)
        if result.stderr:
            print("Warnings/Errors:", result.stderr)
        
        print("=" * 80)
        print("✅ Strategy execution complete")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Strategy execution failed with exit code {e.returncode}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False
    except Exception as e:
        print(f"❌ Error running strategy: {e}")
        return False


def load_map_summary(map_name):
    """
    Load the map summary JSON to get vehicle types.
    Returns the summary dict or None if not found.
    """
    map_name_lower = map_name.lower()
    python_dir = Path(__file__).parent
    workspace_root = python_dir.parent
    
    summary_file = workspace_root / "maps" / map_name_lower / f"{map_name_lower}-summary.json"
    
    if not summary_file.exists():
        print(f"⚠️  Summary file not found: {summary_file}")
        return None
    
    try:
        with open(summary_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading summary: {e}")
        return None


def load_final_result(map_name):
    """
    Load the final result JSON to get customer logs and map data.
    Returns the result dict or None if not found.
    """
    map_name_lower = map_name.lower()
    python_dir = Path(__file__).parent
    
    logs_dir = python_dir.parent / "maps" / map_name_lower / "logs" / "latest"
    
    if not logs_dir.exists():
        print(f"❌ Logs directory not found: {logs_dir}")
        return None
    
    # Find the final tick directory
    tick_dirs = [d for d in logs_dir.iterdir() if d.is_dir() and d.name.startswith("tick_")]
    if not tick_dirs:
        print("❌ No tick directories found")
        return None
    
    tick_dirs_sorted = sorted(tick_dirs, key=lambda d: int(d.name.split("_")[1]))
    final_tick_dir = tick_dirs_sorted[-1]
    
    result_files = list(final_tick_dir.glob("*_result.json"))
    if not result_files:
        print(f"❌ No result file found in {final_tick_dir.name}")
        return None
    
    try:
        with open(result_files[0], 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading result: {e}")
        return None


def calculate_edge_distance(edge_name, nodes_dict):
    """
    Calculate the distance of an edge in km using node coordinates.
    Edge format: "x1.y1-->x2.y2"
    """
    try:
        parts = edge_name.split("-->")
        if len(parts) != 2:
            return None
        
        node1_id, node2_id = parts[0], parts[1]
        
        if node1_id not in nodes_dict or node2_id not in nodes_dict:
            return None
        
        node1 = nodes_dict[node1_id]
        node2 = nodes_dict[node2_id]
        
        x1, y1 = node1['x'], node1['y']
        x2, y2 = node2['x'], node2['y']
        
        # Calculate Euclidean distance
        distance_km = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        return distance_km
        
    except Exception as e:
        print(f"⚠️  Error calculating distance for edge {edge_name}: {e}")
        return None


def analyze_vehicle_speeds(result_data, summary_data):
    """
    Analyze customer travel logs to determine speed for each vehicle type.
    Returns dict: {vehicle_type: {speed_km_per_tick, sample_count, persona_speeds}}
    """
    print("\n🚗 Analyzing vehicle speeds from customer travel logs...")
    
    # Extract vehicle types from summary
    customers_section = summary_data.get('customers', {})
    vehicle_types_config = customers_section.get('vehicleTypes', {})
    vehicle_types = []
    for key, value in vehicle_types_config.items():
        # Convert percentageTrucks -> Truck, percentageCars -> Car
        if key.startswith('percentage'):
            vehicle_type = key.replace('percentage', '').rstrip('s')  # Trucks -> Truck, Cars -> Car
            vehicle_types.append(vehicle_type)
    
    print(f"   Vehicle types from summary: {vehicle_types}")
    
    # Build nodes dictionary for distance calculation
    nodes_dict = {}
    map_data = result_data.get('map', {})
    
    # Nodes are directly under map.nodes, not under zones
    for node in map_data.get('nodes', []):
        node_id = node.get('id')
        if node_id:
            nodes_dict[node_id] = {
                'x': node.get('posX'),
                'y': node.get('posY')
            }
    
    print(f"   Loaded {len(nodes_dict)} nodes for distance calculation")
    
    # Analyze customers
    customer_logs = result_data.get('customerLogs', [])
    vehicle_speed_data = {}
    
    for customer_log in customer_logs:
        customer_id = customer_log.get('customerId', '')
        
        # Only analyze non-bonus customers (ID starts with '0.')
        if not customer_id.startswith('0.'):
            continue
        
        vehicle_type = customer_log.get('vehicleType', 'None')
        persona = customer_log.get('persona', 'Unknown')
        
        if vehicle_type == 'None' or vehicle_type not in vehicle_types:
            continue
        
        logs = customer_log.get('logs', [])
        
        # Find first traveling sequence: Home -> TransitioningToEdge -> Traveling -> ... -> TransitioningToNode
        traveling_started = False
        start_tick = None
        end_tick = None
        edge_name = None
        
        for i, log_entry in enumerate(logs):
            state = log_entry.get('state')
            
            if state == 'TransitioningToEdge' and not traveling_started:
                start_tick = log_entry.get('tick')
                traveling_started = True
            
            elif state == 'Traveling' and traveling_started and edge_name is None:
                edge_name = log_entry.get('edge')
            
            elif state == 'TransitioningToNode' and traveling_started:
                end_tick = log_entry.get('tick')
                break
        
        # Calculate speed if we have valid data
        if start_tick is not None and end_tick is not None and edge_name is not None:
            ticks_traveled = end_tick - start_tick
            distance_km = calculate_edge_distance(edge_name, nodes_dict)
            
            if distance_km and ticks_traveled > 0:
                speed_km_per_tick = distance_km / ticks_traveled
                
                # Initialize vehicle type data if needed
                if vehicle_type not in vehicle_speed_data:
                    vehicle_speed_data[vehicle_type] = {
                        'speeds': [],
                        'persona_speeds': {}  # Track by persona to detect differences
                    }
                
                vehicle_speed_data[vehicle_type]['speeds'].append(speed_km_per_tick)
                
                # Track persona-specific speeds
                if persona not in vehicle_speed_data[vehicle_type]['persona_speeds']:
                    vehicle_speed_data[vehicle_type]['persona_speeds'][persona] = []
                
                vehicle_speed_data[vehicle_type]['persona_speeds'][persona].append(speed_km_per_tick)
    
    # Calculate averages and analyze
    speed_summary = {}
    
    for vehicle_type, data in vehicle_speed_data.items():
        speeds = data['speeds']
        if not speeds:
            continue
        
        avg_speed = sum(speeds) / len(speeds)
        min_speed = min(speeds)
        max_speed = max(speeds)
        
        # Analyze persona differences
        persona_analysis = {}
        all_same = True
        first_avg = None
        
        for persona, persona_speeds in data['persona_speeds'].items():
            persona_avg = sum(persona_speeds) / len(persona_speeds)
            persona_analysis[persona] = {
                'avg_speed': persona_avg,
                'sample_count': len(persona_speeds)
            }
            
            if first_avg is None:
                first_avg = persona_avg
            elif abs(persona_avg - first_avg) > 0.001:  # Allow tiny float differences
                all_same = False
        
        speed_summary[vehicle_type] = {
            'speed_km_per_tick': avg_speed,
            'min_speed': min_speed,
            'max_speed': max_speed,
            'sample_count': len(speeds),
            'persona_independent': all_same,
            'persona_speeds': persona_analysis
        }
        
        print(f"\n   ✅ {vehicle_type}:")
        print(f"      Average speed: {avg_speed:.4f} km/tick")
        print(f"      Range: {min_speed:.4f} - {max_speed:.4f} km/tick")
        print(f"      Samples: {len(speeds)}")
        print(f"      Persona-independent: {'Yes' if all_same else 'No'}")
        
        if not all_same:
            print(f"      Persona speeds:")
            for persona, pdata in persona_analysis.items():
                print(f"        {persona}: {pdata['avg_speed']:.4f} km/tick ({pdata['sample_count']} samples)")
    
    return speed_summary


def collect_zone_logs(map_name):
    """
    Collect zoneLogs from the final tick result file.
    The final tick result contains the complete zoneLogs history.
    Returns aggregated zoneLogs structure and the max tick number.
    """
    map_name_lower = map_name.lower()
    
    # Get the workspace root (parent of python directory)
    python_dir = Path(__file__).parent
    
    # Try both possible paths (relative from python/ and absolute from workspace root)
    possible_paths = [
        python_dir.parent / "maps" / map_name_lower / "logs" / "latest",  # ../maps/...
        Path(f"../maps/{map_name_lower}/logs/latest"),  # Relative fallback
    ]
    
    logs_dir = None
    for path in possible_paths:
        if path.exists():
            logs_dir = path
            break
    
    if not logs_dir:
        print("❌ Logs directory not found in any of:")
        for path in possible_paths:
            print(f"   {path}")
        return None
    
    print(f"\n📂 Collecting zone logs from: {logs_dir}")
    
    # Find the final tick directory (highest tick number)
    tick_dirs = [d for d in logs_dir.iterdir() if d.is_dir() and d.name.startswith("tick_")]
    
    if not tick_dirs:
        print("❌ No tick directories found")
        return None
    
    # Sort numerically by extracting tick number
    tick_dirs_sorted = sorted(tick_dirs, key=lambda d: int(d.name.split("_")[1]))
    final_tick_dir = tick_dirs_sorted[-1]  # Get the last (highest) tick
    final_tick_num = int(final_tick_dir.name.split("_")[1])
    
    print(f"📊 Reading final tick result: tick_{final_tick_num}")
    
    # Look for result file in final tick directory
    result_files = list(final_tick_dir.glob("*_result.json"))
    
    if not result_files:
        print(f"❌ No result file found in {final_tick_dir.name}")
        return None
    
    result_file = result_files[0]
    print(f"📄 Result file: {result_file.name}")
    
    try:
        with open(result_file, 'r') as f:
            result_data = json.load(f)
        
        # Extract zoneLogs - this contains the complete history
        zone_logs = result_data.get('zoneLogs', [])
        
        if not zone_logs:
            print("❌ No zoneLogs found in result file")
            return None
        
        print(f"✅ Collected complete zone logs history: {len(zone_logs)} tick entries")
        
        # Show some statistics
        total_zones = sum(len(entry.get('zones', [])) for entry in zone_logs)
        print(f"   Total zone data points: {total_zones}")
        print(f"   Ticks range: {zone_logs[0].get('tick')} to {zone_logs[-1].get('tick')}")
        
        return zone_logs
    
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing {result_file}: {e}")
        return None
    except Exception as e:
        print(f"❌ Error reading {result_file}: {e}")
        return None


def save_zone_weather_data(map_name, zone_logs, vehicle_speeds=None):
    """
    Save the aggregated zone logs to a file.
    Removes empty/unnecessary fields to reduce file size.
    Optionally includes vehicle speed data.
    """
    map_name_lower = map_name.lower()
    
    # Get the workspace root (parent of python directory)
    python_dir = Path(__file__).parent
    workspace_root = python_dir.parent
    
    # Use workspace-relative path
    output_dir = workspace_root / "maps" / map_name_lower
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Clean up zone logs - remove empty fields and customer-dependent data
    cleaned_zone_logs = []
    for tick_entry in zone_logs:
        cleaned_zones = []
        for zone in tick_entry.get('zones', []):
            # Create cleaned zone with only static/environmental data
            # Removed: totalDemand, totalRevenue (customer-dependent)
            # Removed: topRight, topLeft, bottomRight, bottomLeft (always empty)
            cleaned_zone = {
                'zoneId': zone.get('zoneId'),
                'totalProduction': zone.get('totalProduction'),
                'weatherType': zone.get('weatherType'),
                'sourceinfo': zone.get('sourceinfo'),  # Keep as-is (can be None)
                'storageInfo': zone.get('storageInfo', [])
            }
            cleaned_zones.append(cleaned_zone)
        
        cleaned_zone_logs.append({
            'tick': tick_entry.get('tick'),
            'zones': cleaned_zones
        })
    
    # Prepare the output structure
    zone_weather_data = {
        "metadata": {
            "map_name": map_name,
            "description": "Static zone and weather data (customer-independent)",
            "total_ticks": len(zone_logs),
            "purpose": "Use this data to predict weather and energy production patterns across strategies",
            "note": "Removed fields: totalDemand, totalRevenue (customer-dependent), topRight/topLeft/bottomRight/bottomLeft (always empty)"
        },
        "zoneLogs": cleaned_zone_logs
    }
    
    # Add vehicle speed data if available
    if vehicle_speeds:
        zone_weather_data["vehicleSpeeds"] = vehicle_speeds
    
    # Save the data file
    output_file = output_dir / f"{map_name_lower}_zone_weather_data.json"
    
    print(f"\n💾 Saving zone weather data to: {output_file}")
    
    with open(output_file, 'w') as f:
        json.dump(zone_weather_data, f, indent=2)
    
    print(f"✅ Zone weather data saved: {output_file.absolute()}")
    
    # Generate a summary
    summary_file = output_dir / f"{map_name_lower}_zone_weather_summary.txt"
    
    with open(summary_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write(f"ZONE WEATHER DATA SUMMARY - {map_name}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Total Ticks: {len(zone_logs)}\n")
        f.write(f"Data File: {output_file.name}\n\n")
        
        # Analyze zones
        if zone_logs:
            first_tick = zone_logs[0]
            zones_in_first_tick = first_tick.get('zones', [])
            
            f.write(f"Zones in Map: {len(zones_in_first_tick)}\n\n")
            
            for zone_data in zones_in_first_tick:
                zone_id = zone_data.get('zoneId')
                source_info = zone_data.get('sourceinfo')
                storage_info = zone_data.get('storageInfo', [])
                
                f.write(f"Zone {zone_id}:\n")
                
                if source_info and isinstance(source_info, dict):
                    f.write(f"  Energy Sources: {len(source_info)}\n")
                    
                    for source_type, info in sorted(source_info.items()):
                        if isinstance(info, dict):
                            green = "🌱" if info.get('isGreen') else "⚫"
                            f.write(f"    {green} {source_type}: ${info.get('pricePerMWh', 0):.2f}/MWh\n")
                else:
                    f.write(f"  Energy Sources: 0 (sourceinfo is null)\n")
                
                total_storage = sum(s.get('capacityMWh', 0) for s in storage_info) if storage_info else 0
                f.write(f"  Storage Capacity: {total_storage:.2f} MWh\n\n")
            
            # Weather type distribution analysis
            f.write("\nWeather Distribution Across All Ticks:\n")
            weather_counts = {}
            
            for tick_entry in zone_logs:
                for zone_data in tick_entry.get('zones', []):
                    weather_type = zone_data.get('weatherType', 0)
                    weather_counts[weather_type] = weather_counts.get(weather_type, 0) + 1
            
            total_observations = sum(weather_counts.values())
            for weather_type in sorted(weather_counts.keys()):
                count = weather_counts[weather_type]
                pct = (count / total_observations * 100) if total_observations > 0 else 0
                f.write(f"  Type {weather_type}: {count} observations ({pct:.1f}%)\n")
        
        # Add vehicle speed information if available
        if vehicle_speeds:
            f.write("\n" + "=" * 80 + "\n")
            f.write("VEHICLE SPEED ANALYSIS\n")
            f.write("=" * 80 + "\n\n")
            
            for vehicle_type, speed_data in vehicle_speeds.items():
                f.write(f"{vehicle_type}:\n")
                f.write(f"  Speed: {speed_data['speed_km_per_tick']:.4f} km/tick\n")
                f.write(f"  Range: {speed_data['min_speed']:.4f} - {speed_data['max_speed']:.4f} km/tick\n")
                f.write(f"  Sample Count: {speed_data['sample_count']}\n")
                f.write(f"  Persona Independent: {'Yes' if speed_data['persona_independent'] else 'No'}\n")
                
                if not speed_data['persona_independent']:
                    f.write("  Persona Speeds:\n")
                    for persona, pdata in speed_data['persona_speeds'].items():
                        f.write(f"    {persona}: {pdata['avg_speed']:.4f} km/tick ({pdata['sample_count']} samples)\n")
                
                f.write("\n")
    
    print(f"✅ Summary saved: {summary_file.absolute()}")
    
    return output_file


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python collect_zone_weather_data.py <map_name>")
        print("\nExample:")
        print("  python collect_zone_weather_data.py Turbohill")
        print("\nThis script will:")
        print("  1. Run automated_persona_strategy.py to max ticks")
        print("  2. Collect zoneLogs from final tick result file")
        print("  3. Analyze vehicle speeds from customer travel logs")
        print("  4. Aggregate into a single zone_weather_data.json file with vehicle speeds")
        sys.exit(1)
    
    map_name = sys.argv[1]
    
    print("=" * 80)
    print(f"ZONE WEATHER DATA COLLECTION - {map_name}")
    print("=" * 80)
    print("Running to max ticks for this map")
    print()
    
    # Step 1: Run strategy to generate results
    if not run_strategy(map_name):
        print("\n❌ Failed to run strategy. Exiting.")
        sys.exit(1)
    
    # Step 2: Collect zone logs from all tick results
    zone_logs = collect_zone_logs(map_name)
    
    if not zone_logs:
        print("\n❌ Failed to collect zone logs. Exiting.")
        sys.exit(1)
    
    # Step 3: Load map summary and final result for vehicle speed analysis
    print("\n📊 Loading map data for vehicle speed analysis...")
    summary_data = load_map_summary(map_name)
    result_data = load_final_result(map_name)
    
    vehicle_speeds = None
    if summary_data and result_data:
        vehicle_speeds = analyze_vehicle_speeds(result_data, summary_data)
        if vehicle_speeds:
            print(f"\n✅ Analyzed speeds for {len(vehicle_speeds)} vehicle types")
        else:
            print("\n⚠️  No vehicle speed data could be calculated")
    else:
        print("\n⚠️  Could not load required data for vehicle speed analysis")
    
    # Step 4: Save aggregated data with vehicle speeds
    output_file = save_zone_weather_data(map_name, zone_logs, vehicle_speeds)
    
    if output_file:
        print("\n" + "=" * 80)
        print("🎉 Zone weather data collection complete!")
        print("=" * 80)
        print(f"\n📄 Data file: {output_file}")
        print("\n💡 Usage:")
        print("   Load this file in your strategy to predict weather and energy patterns")
        print("   Structure: zoneLogs[tick_index]['zones'][zone_index]")
        print("   Access: weather_data['zoneLogs'][tick]['zones']")
        if vehicle_speeds:
            print("   Vehicle speeds: weather_data['vehicleSpeeds'][vehicle_type]['speed_km_per_tick']")
    else:
        print("\n❌ Failed to save zone weather data")
        sys.exit(1)


if __name__ == "__main__":
    main()
