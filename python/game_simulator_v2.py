#!/usr/bin/env python3
"""
Considition 2025 - Game Simulator V2
Uses CORRECT API structure with charging recommendations
"""

import json
import os
import sys
import requests
import networkx as nx
from typing import Dict, List, Tuple, Optional
from pathlib import Path


def load_map_config(map_name: str) -> Dict:
    """
    Load map configuration file
    
    Args:
        map_name: Name of the map (e.g., 'Turbohill')
    
    Returns:
        Dictionary containing map configuration including ticks
    """
    script_dir = Path(__file__).parent
    config_file = script_dir / '..' / '..' / 'maps' / map_name.lower() / f'{map_name.lower()}-map-config.json'
    
    if not config_file.exists():
        raise FileNotFoundError(f"Map config not found: {config_file}")
    
    with open(config_file, 'r') as f:
        return json.load(f)


class MapData:
    """Loads and processes map data"""
    
    def __init__(self, map_file: str, map_name: Optional[str] = None):
        """
        Args:
            map_file: Path to the map JSON file
            map_name: Name of the map (e.g., 'Turbohill'). If provided, will load config to get ticks.
        """
        with open(map_file, 'r') as f:
            self.data = json.load(f)
        
        # Load map config to get ticks if map_name provided
        self.ticks = 288  # Default fallback
        self.name = map_name
        if map_name:
            try:
                config = load_map_config(map_name)
                self.ticks = config.get('ticks', 288)
                self.name = config.get('name', map_name)
            except FileNotFoundError:
                print(f"⚠️  Warning: Could not load config for {map_name}, using default ticks=288")
        
        self.graph = self._build_graph()
        self.charging_stations = self._extract_charging_stations()
        self.customers = self._extract_customers()
        self.nodes = {node['id']: node for node in self.data.get('nodes', [])}
        
    def _build_graph(self) -> nx.DiGraph:
        """Build directed graph from map data"""
        G = nx.DiGraph()
        
        for node in self.data.get('nodes', []):
            G.add_node(node['id'], 
                      x=node['posX'], 
                      y=node['posY'],
                      zone_id=node.get('zoneId'))
        
        for edge in self.data.get('edges', []):
            G.add_edge(edge['fromNode'], 
                      edge['toNode'],
                      distance=edge.get('length', 1))
        
        return G
    
    def _extract_customers(self) -> List[Dict]:
        """Extract all customers from nodes"""
        customers = []
        for node in self.data.get('nodes', []):
            for customer in node.get('customers', []):
                # Add aliases for backward compatibility (some old code uses these names)
                # Actual JSON fields are fromNode/toNode
                customer['startNodeId'] = customer.get('fromNode')
                customer['destinationNodeId'] = customer.get('toNode')
                customers.append(customer)
        return customers
    
    def _extract_charging_stations(self) -> Dict[str, Dict]:
        """Extract all charging stations with their properties"""
        stations = {}
        
        for node in self.data.get('nodes', []):
            target = node.get('target', {})
            if target.get('Type') == 'ChargingStation':
                station_data = target.get('ChargingStation', {})
                stations[node['id']] = {
                    'id': node['id'],
                    'x': node['posX'],
                    'y': node['posY'],
                    'capacity': station_data.get('capacity', 0),
                    'working_chargers': len([c for c in station_data.get('chargers', []) 
                                            if c.get('charge', 0) > 0]),
                    'is_green': station_data.get('isGreen', False),
                    'zone_id': node.get('zoneId', '')
                }
        
        return stations
    
    def find_path(self, start: str, end: str) -> Optional[List[str]]:
        """Find shortest path between two nodes"""
        try:
            return nx.shortest_path(self.graph, start, end, weight='distance')
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
    
    def get_path_distance(self, path: List[str]) -> float:
        """Calculate total distance of a path"""
        distance = 0
        for i in range(len(path) - 1):
            distance += self.graph[path[i]][path[i+1]]['distance']
        return distance
    
    def get_customer_by_id(self, customer_id: str) -> Optional[Dict]:
        """Get customer data by ID"""
        for customer in self.customers:
            if customer['id'] == customer_id:
                return customer
        return None


class ChargingStrategy:
    """Strategy for recommending charging stations to customers"""
    
    def __init__(self, map_data: MapData):
        self.map_data = map_data
        # Energy consumption rate (approximate, adjust based on testing)
        self.kwh_per_km = 0.2
    
    def calculate_energy_needed(self, distance_km: float) -> float:
        """Calculate energy needed for a distance (as fraction 0-1)"""
        kwh_needed = distance_km * self.kwh_per_km
        # Assume max battery is ~50 kWh (typical EV)
        max_battery = 50.0
        return min(kwh_needed / max_battery, 1.0)
    
    def find_stations_on_path(self, path: List[str]) -> List[str]:
        """Find all charging stations along a path"""
        stations = []
        for node_id in path:
            if node_id in self.map_data.charging_stations:
                stations.append(node_id)
        return stations
    
    def find_nearest_station_to_node(self, node_id: str) -> Optional[str]:
        """Find nearest charging station to a given node"""
        if not self.map_data.charging_stations:
            return None
        
        best_station = None
        best_distance = float('inf')
        
        for station_id in self.map_data.charging_stations.keys():
            try:
                path = self.map_data.find_path(node_id, station_id)
                if path:
                    distance = self.map_data.get_path_distance(path)
                    if distance < best_distance:
                        best_distance = distance
                        best_station = station_id
            except:
                continue
        
        return best_station
    
    def recommend_charging_for_customer(self, customer: Dict) -> List[Dict]:
        """Generate charging recommendations for a customer"""
        customer_id = customer['id']
        start_node = customer['startNodeId']
        dest_node = customer['destinationNodeId']
        initial_charge = customer['chargeRemaining']
        persona = customer.get('persona', 'Neutral')
        
        # Find path from start to destination
        path = self.map_data.find_path(start_node, dest_node)
        if not path:
            print(f"⚠️  No path found for customer {customer_id}")
            return []
        
        # Calculate energy needed for full journey
        total_distance = self.map_data.get_path_distance(path)
        energy_needed = self.calculate_energy_needed(total_distance)
        
        print(f"👤 Customer {customer_id} ({persona}):")
        print(f"   Route: {start_node} → {dest_node} ({total_distance:.1f} km)")
        print(f"   Initial charge: {initial_charge:.2%}, Needs: {energy_needed:.2%}")
        
        # If customer has enough charge, maybe no charging needed
        if initial_charge >= energy_needed * 1.1:  # 10% buffer
            print(f"   ✅ Sufficient charge - no charging needed")
            return []
        
        # Find charging stations along the route
        stations_on_path = self.find_stations_on_path(path)
        
        if not stations_on_path:
            # Find nearest station to start node
            print(f"   ⚠️  No stations on direct path, finding nearest...")
            nearest = self.find_nearest_station_to_node(start_node)
            if nearest:
                stations_on_path = [nearest]
        
        if not stations_on_path:
            print(f"   ❌ No charging stations available!")
            return []
        
        # Select best station based on persona
        recommendations = []
        selected_station = self.select_station_by_persona(stations_on_path, persona)
        
        if selected_station:
            # Calculate target charge level
            # Charge enough to reach destination + some buffer
            target_charge = min(energy_needed * 1.2, 0.95)  # 20% buffer, max 95%
            
            recommendations.append({
                "nodeId": selected_station,
                "chargeTo": target_charge
            })
            
            station_info = self.map_data.charging_stations[selected_station]
            print(f"   🔌 Recommend: Station {selected_station} " +
                  f"({'GREEN ⚡' if station_info['is_green'] else 'regular'}) " +
                  f"→ charge to {target_charge:.0%}")
        
        return recommendations
    
    def select_station_by_persona(self, stations: List[str], persona: str) -> Optional[str]:
        """Select best station based on customer persona"""
        if not stations:
            return None
        
        # Persona-based selection
        if persona == "EcoConscious":
            # Prefer green stations
            for station_id in stations:
                if self.map_data.charging_stations[station_id]['is_green']:
                    return station_id
        
        elif persona == "CostSensitive":
            # Prefer green stations (cheaper during good weather)
            for station_id in stations:
                if self.map_data.charging_stations[station_id]['is_green']:
                    return station_id
        
        elif persona == "Stressed" or persona == "DislikesDriving":
            # Prefer first available station (fastest)
            return stations[0]
        
        # Default: pick first station or best one
        # Could add logic to prefer stations with more capacity
        best_station = stations[0]
        best_capacity = 0
        
        for station_id in stations:
            capacity = self.map_data.charging_stations[station_id]['working_chargers']
            if capacity > best_capacity:
                best_capacity = capacity
                best_station = station_id
        
        return best_station
    
    def generate_tick_recommendations(self, tick: int) -> List[Dict]:
        """Generate recommendations for a specific tick"""
        recommendations = []
        
        # For tick 0, recommend for all customers
        if tick == 0:
            print(f"\n⏰ Generating recommendations for tick {tick}:")
            for customer in self.map_data.customers:
                charging_recs = self.recommend_charging_for_customer(customer)
                if charging_recs or True:  # Include even if empty
                    recommendations.append({
                        "customerId": customer['id'],
                        "chargingRecommendations": charging_recs
                    })
        
        return recommendations


def run_game(api_url: str, game_input: Dict, save_game: bool = False, api_key: str = "", strategy_name: str = "") -> Dict:
    """Submit game to API and get results
    
    Args:
        api_url: Base API URL (local or cloud)
        game_input: Game input dictionary
        save_game: If True, saves to cloud (only if score beats high score)
        api_key: API key for cloud submissions
        strategy_name: Optional strategy name for file naming
    """
    mode = "☁️ CLOUD (SAVE)" if save_game else "🏠 LOCAL (TEST)"
    print(f"\n🎮 Running game [{mode}] for map: {game_input['mapName']}")
    print(f"   PlayToTick: {game_input.get('playToTick', 'full game')}")
    print(f"   Ticks with recommendations: {len(game_input['ticks'])}")
    
    # Debug: Save the game input with strategy name in req-local subfolder
    map_name = game_input['mapName'].lower()
    req_local_dir = f"../maps/{map_name}/req-local"
    Path(req_local_dir).mkdir(parents=True, exist_ok=True)
    
    if strategy_name:
        debug_file = f"{req_local_dir}/{map_name}-game-input-{strategy_name}.json"
    else:
        debug_file = f"{req_local_dir}/{map_name}-game-input-v2.json"
    
    with open(debug_file, 'w') as f:
        json.dump(game_input, f, indent=2)
    print(f"   📄 Game input saved to: req-local/{os.path.basename(debug_file)}")
    
    try:
        # Build URL with saveGame parameter
        endpoint_url = f"{api_url}/api/game"
        if save_game:
            endpoint_url += "?saveGame=true"
        
        # Add API key header for cloud requests
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['x-api-key'] = api_key
        
        response = requests.post(endpoint_url, json=game_input, headers=headers)
        response.raise_for_status()
        result = response.json()
        
        print("\n✅ Game completed!")
        print(f"   Score: {result.get('score', 0):.2f}")
        print(f"   kWh Revenue: {result.get('kwhRevenue', 0):.2f}")
        print(f"   Customer Completion Score: {result.get('customerCompletionScore', 0):.2f}")
        
        if save_game:
            game_id = result.get('gameId')
            if game_id:
                print(f"   🎉 NEW HIGH SCORE SAVED! Game ID: {game_id}")
            else:
                print(f"   ℹ️  Score not saved (didn't beat high score)")
        
        # Save result with strategy name in req-local subfolder
        if strategy_name:
            result_file = f"{req_local_dir}/{map_name}-game-result-{strategy_name}.json"
        else:
            result_file = f"{req_local_dir}/{map_name}-game-result-v2.json"
        with open(result_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"   📄 Game result saved to: req-local/{os.path.basename(result_file)}")
        
        return result
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Error running game: {e}")
        if hasattr(e.response, 'text'):
            print(f"   Response: {e.response.text}")
        return {}


def main():
    """Main execution"""
    import sys
    
    # Parse command line arguments
    save_to_cloud = "--save" in sys.argv or "--cloud" in sys.argv
    
    print("=" * 70)
    print("Considition 2025 - Game Simulator V2 (Correct API)")
    if save_to_cloud:
        print("MODE: ☁️  CLOUD SUBMISSION (Will save if high score)")
    else:
        print("MODE: 🏠 LOCAL TESTING (Not saved)")
    print("=" * 70)
    
    # Configuration
    if save_to_cloud:
        # Cloud API - API key set here or via environment variable
        API_KEY = os.environ.get('CONSIDITION_API_KEY', 'xxx')
        if not API_KEY:
            print("\n❌ ERROR: CONSIDITION_API_KEY not set!")
            sys.exit(1)
        API_URL = "https://api.considition.com"  # TODO: Update with actual cloud URL
        print(f"\n🔑 Using API key: {API_KEY[:8]}...")
    else:
        # Local Docker
        API_URL = "http://localhost:8080"
        API_KEY = ""
    
    MAP_NAME = "Turbohill"
    MAP_FILE = f"../maps/{MAP_NAME.lower()}/{MAP_NAME.lower()}-map.json"
    
    # Load map data with config
    print(f"\n📂 Loading map: {MAP_NAME}")
    map_data = MapData(MAP_FILE, map_name=MAP_NAME)
    max_ticks = map_data.ticks
    print(f"   Nodes: {map_data.graph.number_of_nodes()}")
    print(f"   Edges: {map_data.graph.number_of_edges()}")
    print(f"   Customers: {len(map_data.customers)}")
    print(f"   Charging Stations: {len(map_data.charging_stations)}")
    print(f"   Max Ticks: {max_ticks}")
    
    # Create strategy
    strategy = ChargingStrategy(map_data)
    
    # Generate recommendations for tick 0
    tick_0_recommendations = strategy.generate_tick_recommendations(0)
    
    # Build game input
    game_input = {
        "mapName": MAP_NAME,
        "playToTick": max_ticks,  # Use max ticks from config
        "ticks": [
            {
                "tick": 0,
                "customerRecommendations": tick_0_recommendations
            }
        ]
    }
    
    print(f"\n📊 Game Input Summary:")
    print(f"   Total recommendations: {len(tick_0_recommendations)}")
    customers_with_charging = sum(1 for r in tick_0_recommendations 
                                  if r.get('chargingRecommendations'))
    print(f"   Customers with charging recommendations: {customers_with_charging}")
    
    # Run the game
    result = run_game(API_URL, game_input, save_game=save_to_cloud)
    
    if result:
        # Analyze results
        print("\n" + "=" * 70)
        print("📈 RESULTS ANALYSIS")
        print("=" * 70)
        
        customer_logs = result.get('customerLogs', [])
        print(f"\nTotal customers tracked: {len(customer_logs)}")
        
        for i, log in enumerate(customer_logs[:5]):  # Show first 5
            customer_id = log.get('customerId', 'unknown')
            logs = log.get('logs', [])
            if logs:
                final_state = logs[-1].get('state', 'unknown')
                final_charge = logs[-1].get('chargeRemaining', 0)
                print(f"\n👤 Customer {customer_id}:")
                print(f"   Final state: {final_state}")
                print(f"   Final charge: {final_charge:.2%}")
                
                # Check if they charged
                charged = any(l.get('state') == 'Charging' for l in logs)
                if charged:
                    print(f"   🔌 Did charge during journey")
        
        if len(customer_logs) > 5:
            print(f"\n... and {len(customer_logs) - 5} more customers")
    
    print("\n" + "=" * 70)
    print("✨ Simulation complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
