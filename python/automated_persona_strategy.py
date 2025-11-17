"""
Automated Persona-Based Strategy for Considition 2025

This strategy implements a fully automated approach that:
1. Loops through all customers from the map
2. Calculates shortest paths using Dijkstra's algorithm
3. Determines charging needs based on range vs distance
4. Selects optimal charging stations based on persona preferences
5. Generates complete tick-by-tick recommendations

Persona-specific charging selection:
- EcoConscious: Prioritize high greenEnergyPercentage stations
- CostSensitive: Select stations in zones with lowest energy prices
- Stressed/DislikesDriving: Find closest operational charger
- Neutral: Simple closest charger logic
"""

import json
import heapq
from typing import Dict, List, Tuple, Optional, Set
from pathlib import Path


class AutomatedPersonaStrategy:
    """Automated strategy that handles all customers with persona-aware logic"""
    
    def __init__(self, map_file: str, customers_file: str, stations_file: str, config_file: str, 
                 strategy_config_file: Optional[str] = None):
        """
        Initialize strategy with map data
        
        Args:
            map_file: Path to turbohill-map.json
            customers_file: Path to turbohill-customers.json
            stations_file: Path to turbohill-stations.json
            config_file: Path to turbohill-map-config.json
            strategy_config_file: Optional path to strategy configuration JSON file
        """
        self.map_data = self._load_json(map_file)
        self.customers_data = self._load_json(customers_file)
        self.stations_data = self._load_json(stations_file)
        self.config_data = self._load_json(config_file)
        
        # Load strategy configuration (thresholds, persona targets, etc.)
        self.strategy_config = self._load_strategy_config(strategy_config_file)
        
        # Build graph from edges
        self.graph = self._build_graph()
        
        # Index stations by node
        self.station_by_node = self._index_stations()
        
        # Index zones for pricing
        self.zone_data = self._index_zones()
        
        # Track customer visit history for loop detection
        # Structure: {customer_id: [list of visited nodes in order]}
        self.customer_visit_history = {}
        
        # Store engine path for each customer (tick 0 path)
        self.customer_paths = {}
        
        # Track pending charging recommendations to avoid duplicates
        # Structure: {customer_id: {'station': 'node_id', 'tick': tick_number}}
        self.pending_recommendations = {}

        map_name = self.map_data.get('name', self.map_data.get('mapName', 'Unknown'))
        print(f"✓ Loaded map: {map_name}")
        print(f"✓ Found {len(self.customers_data['customers'])} customers")
        print(f"✓ Found {len(self.stations_data['chargingStations'])} charging stations")
        print(f"✓ Built graph with {len(self.graph)} nodes")
        print(f"✓ Strategy config: {self.strategy_config['name']} - {self.strategy_config['description']}")
        
        # Initialize dynamic zone weather data collection
        self.map_name = map_name
        # Load pre-generated zone weather data if available
        self.zone_weather_data = self._load_zone_weather_data(map_name)
        self.zone_logs_collection = []  # Will collect zoneLogs from each game result
        print("✓ Initialized zone logs collection (will collect dynamically from game results)")
    
    def save_engine_paths(self, customer_logs):
        """Save engine path for each customer (including bonus customers that appear mid-game)."""
        for customer_log in customer_logs:
            customer_id = customer_log.get('customerId')
            
            # Skip if we already have this customer's path
            if customer_id in self.customer_paths:
                continue
            
            logs = customer_log.get('logs', [])
            if logs:
                # Get the first log entry which contains the initial path
                first_log = logs[0]
                initial_path = first_log.get('path', [])
                if initial_path:
                    self.customer_paths[customer_id] = initial_path
                    # Log bonus customers (those appearing after tick 0)
                    first_tick = first_log.get('tick', 0)
                    if first_tick > 0:
                        print(f"   🎁 Bonus customer {customer_id} appeared at tick {first_tick}")
    
    def collect_zone_logs_from_result(self, game_result: dict):
        """
        Collect zone logs from a game result and add to the collection.
        This builds up historical zone data as the game progresses.
        
        Args:
            game_result: Game result dictionary containing zoneLogs
        """
        zone_logs = game_result.get('zoneLogs', [])
        
        if not zone_logs:
            return
        
        # Add new zone logs to collection, avoiding duplicates by tick
        existing_ticks = {log['tick'] for log in self.zone_logs_collection}
        
        new_logs_added = 0
        for zone_log in zone_logs:
            tick = zone_log.get('tick')
            if tick not in existing_ticks:
                self.zone_logs_collection.append(zone_log)
                existing_ticks.add(tick)
                new_logs_added += 1
        
        # Keep collection sorted by tick
        self.zone_logs_collection.sort(key=lambda x: x['tick'])
        
        if new_logs_added > 0:
            print(f"   📊 Collected {new_logs_added} new zone logs (total: {len(self.zone_logs_collection)} ticks)")
        
        map_name = self.map_data.get('name', self.map_data.get('mapName', 'Unknown'))
        print(f"✓ Loaded map: {map_name}")
        print(f"✓ Found {len(self.customers_data['customers'])} customers")
        print(f"✓ Found {len(self.stations_data['chargingStations'])} charging stations")
        print(f"✓ Built graph with {len(self.graph)} nodes")
        print(f"✓ Strategy config: {self.strategy_config['name']} - {self.strategy_config['description']}")

    def _load_json(self, filepath: str) -> dict:
        """Load JSON file"""
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def _load_zone_weather_data(self, map_name: str) -> Optional[dict]:
        """
        Load pre-generated zone weather data for the map if available.
        This includes zone logs and vehicle speeds.
        
        Args:
            map_name: Name of the map
            
        Returns:
            Zone weather data dict or None if not found
        """
        try:
            map_name_lower = map_name.lower()
            
            # Try to find the zone weather data file
            # Script is in python/strategies/, so go up 2 levels to workspace root
            script_dir = Path(__file__).parent.resolve()
            workspace_root = script_dir.parent.parent
            
            weather_data_file = workspace_root / "maps" / map_name_lower / f"{map_name_lower}_zone_weather_data.json"
            
            if not weather_data_file.exists():
                print(f"ℹ️  No pre-generated zone weather data found for {map_name}")
                return None
            
            with open(weather_data_file, 'r') as f:
                data = json.load(f)
            
            print(f"✓ Loaded zone weather data: {len(data.get('zoneLogs', []))} ticks")
            
            # Log vehicle speeds if available
            vehicle_speeds = data.get('vehicleSpeeds', {})
            if vehicle_speeds:
                print(f"✓ Vehicle speeds loaded: {', '.join(vehicle_speeds.keys())}")
                for vtype, speed_data in vehicle_speeds.items():
                    persona_independent = speed_data.get('persona_independent', True)
                    status = "persona-independent" if persona_independent else "persona-dependent"
                    print(f"   {vtype}: {speed_data['speed_km_per_tick']:.4f} km/tick ({status})")
            
            return data
            
        except Exception as e:
            print(f"⚠️  Error loading zone weather data: {e}")
            return None
    
    def get_vehicle_speed(self, customer: dict) -> float:
        """
        Get the travel speed for a customer's vehicle type.
        Uses pre-loaded zone weather data if available, otherwise falls back to default.
        
        Args:
            customer: Customer dictionary with 'type' and 'persona' fields
            
        Returns:
            Speed in km/tick
        """
        # Default fallback speed (approximately 1 km per tick)
        default_speed = 1.0
        
        if not self.zone_weather_data:
            return default_speed
        
        vehicle_speeds = self.zone_weather_data.get('vehicleSpeeds', {})
        if not vehicle_speeds:
            return default_speed
        
        vehicle_type = customer.get('type', 'Car')
        
        # Get speed data for this vehicle type
        speed_data = vehicle_speeds.get(vehicle_type)
        if not speed_data:
            return default_speed
        
        # Check if speed is persona-dependent
        persona_independent = speed_data.get('persona_independent', True)
        
        if persona_independent:
            # Use average speed for vehicle type
            return speed_data.get('speed_km_per_tick', default_speed)
        else:
            # Use persona-specific speed if available
            persona = customer.get('persona', 'Neutral')
            persona_speeds = speed_data.get('persona_speeds', {})
            
            if persona in persona_speeds:
                return persona_speeds[persona].get('avg_speed', default_speed)
            else:
                # Fall back to vehicle type average
                return speed_data.get('speed_km_per_tick', default_speed)

    def _load_strategy_config(self, config_file: Optional[str] = None) -> dict:
        """
        Load strategy configuration file with thresholds and parameters
        
        Args:
            config_file: Path to strategy config JSON, or None for default
            
        Returns:
            Strategy configuration dictionary
        """
        if config_file is None:
            # Use default config
            config_dir = Path(__file__).parent / 'config'
            config_file = config_dir / 'automated_persona_strategy_default.json'
        
        config_path = Path(config_file)
        if not config_path.exists():
            print(f"⚠️  Config file not found: {config_file}")
            print("   Using hardcoded defaults")
            return self._get_default_strategy_config()
        
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading config: {e}")
            print("   Using hardcoded defaults")
            return self._get_default_strategy_config()
    
    def _get_default_strategy_config(self) -> dict:
        """Return hardcoded default configuration as fallback"""
        return {
            "name": "hardcoded_default",
            "description": "Fallback default configuration",
            "charging_thresholds": {
                "proactive_threshold": 0.50,
                "emergency_threshold": 0.30,
                "safety_margin": 1.1,
                "energy_buffer_multiplier": 1.2,
                "reachability_margin": 1.05
            },
            "persona_charge_targets": {
                "Stressed": 1.0,
                "CostSensitive": 0.80,
                "DislikesDriving": 1.0,
                "EcoConscious": 1.0,
                "Neutral": 0.90
            },
            "loop_detection": {
                "enabled": True,
                "lookback_ticks": 20,
                "two_node_loop_min_visits": 6,
                "three_node_loop_min_visits": 9
            },
            "station_selection": {
                "eco_conscious": {
                    "green_energy_weight": 1000,
                    "distance_penalty": 1.0
                },
                "cost_sensitive": {
                    "price_weight": 1.0,
                    "distance_penalty": 0.1
                }
            },
            "dynamic_intervention": {
                "enabled": True
            }
        }
    
    def _build_graph(self) -> Dict[str, List[Tuple[str, float]]]:
        """Build adjacency list graph from map edges"""
        graph = {}
        
        for edge in self.map_data['edges']:
            from_node = edge['fromNode']
            to_node = edge['toNode']
            length = edge['length']
            
            # Add bidirectional edges (edges are already bidirectional in map)
            if from_node not in graph:
                graph[from_node] = []
            if to_node not in graph:
                graph[to_node] = []
            
            graph[from_node].append((to_node, length))
        
        return graph
    
    def _index_stations(self) -> Dict[str, dict]:
        """Index stations by node ID"""
        stations = {}
        for station in self.stations_data['chargingStations']:
            node_id = station['nodeId']
            stations[node_id] = station
        return stations
    
    def _index_zones(self) -> Dict[str, dict]:
        """Index zone information including energy prices"""
        zones = {}
        for zone in self.map_data.get('zones', []):
            zone_id = zone['id']
            zones[zone_id] = zone
        return zones
    
    def dijkstra(self, start: str, end: str) -> Tuple[float, List[str]]:
        """
        Find shortest path using Dijkstra's algorithm
        
        Returns:
            (distance, path) where path is list of node IDs
        """
        if start not in self.graph or end not in self.graph:
            return float('inf'), []
        
        # Priority queue: (distance, node, path)
        pq = [(0, start, [start])]
        visited = set()
        
        while pq:
            dist, node, path = heapq.heappop(pq)
            
            if node in visited:
                continue
            
            visited.add(node)
            
            if node == end:
                return dist, path
            
            for neighbor, edge_length in self.graph[node]:
                if neighbor not in visited:
                    new_dist = dist + edge_length
                    new_path = path + [neighbor]
                    heapq.heappush(pq, (new_dist, neighbor, new_path))
        
        return float('inf'), []
    
    def calculate_path_distance(self, path: List[str]) -> float:
        """
        Calculate total distance for a given path using actual edge lengths
        
        Args:
            path: List of node IDs in order (e.g., ["0.0", "0.1", "1.1", "2.1"])
            
        Returns:
            Total distance in km, or 0 if path is invalid
        """
        if not path or len(path) < 2:
            return 0.0
        
        total_distance = 0.0
        for i in range(len(path) - 1):
            from_node = path[i]
            to_node = path[i + 1]
            
            # Find edge length in graph
            if from_node in self.graph:
                for neighbor, edge_length in self.graph[from_node]:
                    if neighbor == to_node:
                        total_distance += edge_length
                        break
                else:
                    # Edge not found, path is invalid
                    print(f"⚠️  Edge {from_node} → {to_node} not found in graph")
                    return 0.0
            else:
                print(f"⚠️  Node {from_node} not found in graph")
                return 0.0
        
        return total_distance
    
    def calculate_range(self, charge_kwh: float, consumption_per_km: float) -> float:
        """Calculate vehicle range in km"""
        if consumption_per_km == 0:
            return float('inf')
        return charge_kwh / consumption_per_km
    
    def needs_charging(self, distance_km: float, charge_remaining: float, 
                      consumption_per_km: float, safety_margin: float = None) -> bool:
        """
        Determine if customer needs to charge
        
        Args:
            distance_km: Total journey distance
            charge_remaining: Current battery charge in kWh
            consumption_per_km: Energy consumption rate
            safety_margin: Multiply required energy by this factor (uses config if None)
        """
        if safety_margin is None:
            safety_margin = self.strategy_config['charging_thresholds']['safety_margin']
        
        required_energy = distance_km * consumption_per_km * safety_margin
        return required_energy > charge_remaining
    
    def find_optimal_charging_station(self, customer: dict, route_path: List[str], tick: int = 0,
                                       charge_remaining_kwh: Optional[float] = None,
                                       consumption_per_km: Optional[float] = None) -> Optional[dict]:
        """
        Find the optimal charging station based on customer persona
        
        Args:
            customer: Customer data dictionary
            route_path: List of nodes in the customer's route
            tick: Current tick for looking up dynamic data (green energy, pricing)
            charge_remaining_kwh: Current battery charge in kWh (for reachability filtering)
            consumption_per_km: Energy consumption per km (for reachability filtering)
        
        Returns:
            Station dictionary or None
        """
        persona = customer['persona']
        from_node = customer['fromNode']
        
        # Get all operational stations
        operational_stations = [
            s for s in self.stations_data['chargingStations']
            if s['status']['operational'] and s['capacity']['availableChargers'] > 0
        ]
        
        if not operational_stations:
            print(f"⚠️  No operational stations available for customer {customer['customerId']}")
            return None
        
        if persona == 'EcoConscious':
            return self._find_greenest_station(operational_stations, from_node, route_path, tick,
                                              charge_remaining_kwh, consumption_per_km)
        
        elif persona == 'CostSensitive':
            return self._find_cheapest_station(operational_stations, from_node, route_path,
                                               charge_remaining_kwh, consumption_per_km)
        
        elif persona in ['Stressed', 'DislikesDriving']:
            return self._find_closest_station(operational_stations, from_node, route_path,
                                             charge_remaining_kwh, consumption_per_km)
        
        else:  # Neutral or unknown
            return self._find_closest_station(operational_stations, from_node, route_path,
                                             charge_remaining_kwh, consumption_per_km)
    
    def _find_greenest_station(self, stations: List[dict], from_node: str, 
                               route_path: Optional[List[str]] = None, tick: int = 0,
                               charge_remaining_kwh: Optional[float] = None,
                               consumption_per_km: Optional[float] = None) -> Optional[dict]:
        """
        Find station with highest green energy percentage at the given tick
        
        Uses zone weather data to determine actual green energy percentage per zone at this tick.
        Falls back to static station data if zone weather data is not available.
        Prefers stations on route_path if provided.
        If charge_remaining_kwh and consumption_per_km provided, only return reachable stations.
        """
        # Filter to reachable stations if battery constraints provided
        if charge_remaining_kwh is not None and consumption_per_km is not None:
            reachability_margin = self.strategy_config['charging_thresholds']['reachability_margin']
            reachable_stations = []
            for station in stations:
                dist_to_station, _ = self.dijkstra(from_node, station['nodeId'])
                energy_needed = dist_to_station * consumption_per_km
                if charge_remaining_kwh >= energy_needed * reachability_margin:
                    reachable_stations.append(station)
            
            if not reachable_stations:
                print(f"⚠️ No reachable green charging stations from {from_node} (have {charge_remaining_kwh:.1f} kWh)")
                return None
            
            stations = reachable_stations
        
        # If route provided, filter to acceptable stations
        stations_to_score = stations
        if route_path:
            # First, try stations on the path
            on_path_stations = [s for s in stations if s['nodeId'] in route_path]
            
            if on_path_stations:
                stations_to_score = on_path_stations
            else:
                # No stations on path, use path-aware detour logic
                destination = route_path[-1] if route_path else None
                if destination:
                    dist_to_dest, _ = self.dijkstra(from_node, destination)
                    acceptable_stations = []
                    
                    for station in stations:
                        station_node = station['nodeId']
                        dist_to_station, _ = self.dijkstra(from_node, station_node)
                        dist_station_to_dest, _ = self.dijkstra(station_node, destination)
                        
                        total_via_station = dist_to_station + dist_station_to_dest
                        if total_via_station <= dist_to_dest * 1.5:
                            acceptable_stations.append(station)
                    
                    if acceptable_stations:
                        stations_to_score = acceptable_stations
                        print(f"   ℹ️  No green stations on path from {from_node}, using nearby stations")
                    else:
                        print(f"   ⚠️  No suitable green charging stations found near path from {from_node}")
                        return None
        
        scored_stations = []
        
        for station in stations_to_score:
            # Get zone ID for this station
            zone_id = station.get('location', {}).get('zoneId', None)
            
            # Look up green energy percentage for this zone at this tick
            green_pct = 0
            if self.zone_logs_collection and zone_id:
                # Find the tick data in our collected zone logs
                tick_data = next((t for t in self.zone_logs_collection if t['tick'] == tick), None)
                
                if tick_data:
                    # Find the zone data
                    zones = tick_data.get('zones', [])
                    zone_data = next((z for z in zones if z['zoneId'] == zone_id), None)
                    
                    if zone_data:
                        # Calculate green energy percentage from sourceinfo
                        sourceinfo = zone_data.get('sourceinfo', {})
                        total_production = zone_data.get('totalProduction', 0)
                        
                        if total_production > 0:
                            green_production = sum(
                                source_data.get('production', 0)
                                for source_data in sourceinfo.values()
                                if source_data.get('isGreen', False)
                            )
                            green_pct = (green_production / total_production) * 100
            
            # Fallback: If we don't have zone log data for this tick yet, use station's static data
            #if green_pct == 0 and not self.zone_weather_data:
            if green_pct == 0 and not self.zone_logs_collection:
                zone_energy = station.get('zoneEnergy', {})
                green_pct = zone_energy.get('greenEnergyPercentage', 0)
            
            # Calculate distance to station
            dist, _ = self.dijkstra(from_node, station['nodeId'])
            
            if dist == float('inf'):
                continue
            
            # Prefer on-route or nearby stations with high green energy
            # Score: green% is primary, distance is secondary
            green_weight = self.strategy_config['station_selection']['eco_conscious']['green_energy_weight']
            dist_penalty = self.strategy_config['station_selection']['eco_conscious']['distance_penalty']
            score = green_pct * green_weight - (dist * dist_penalty)
            
            scored_stations.append((score, station, green_pct))
        
        if not scored_stations:
            return None
        
        scored_stations.sort(reverse=True, key=lambda x: x[0])
        best_station = scored_stations[0][1]
        best_green_pct = scored_stations[0][2]
        
        print(f"   EcoConscious → Station {best_station['nodeId']} "
              f"(Green: {best_green_pct:.0f}% at tick {tick})")
        
        return best_station
    
    def _find_cheapest_station(self, stations: List[dict], from_node: str, route_path: Optional[List[str]] = None,
                               charge_remaining_kwh: Optional[float] = None,
                               consumption_per_km: Optional[float] = None) -> Optional[dict]:
        """
        Find station in zone with lowest energy price, preferring stations on route_path if provided
        If charge_remaining_kwh and consumption_per_km provided, only return reachable stations.
        
        Args:
            stations: List of operational stations
            from_node: Starting node
            route_path: Optional route path to prioritize on-path stations
            charge_remaining_kwh: Current battery charge in kWh
            consumption_per_km: Energy consumption per kilometer
        """
        # Filter to reachable stations if battery constraints provided
        if charge_remaining_kwh is not None and consumption_per_km is not None:
            reachability_margin = self.strategy_config['charging_thresholds']['reachability_margin']
            reachable_stations = []
            for station in stations:
                dist_to_station, _ = self.dijkstra(from_node, station['nodeId'])
                energy_needed = dist_to_station * consumption_per_km
                if charge_remaining_kwh >= energy_needed * reachability_margin:
                    reachable_stations.append(station)
            
            if not reachable_stations:
                print(f"⚠️ No reachable cheap charging stations from {from_node} (have {charge_remaining_kwh:.1f} kWh)")
                return None
            
            stations = reachable_stations
        
        # If route provided, use path-aware selection with price preference
        if route_path:
            # First, try to find stations on the path
            on_path_stations = [s for s in stations if s['nodeId'] in route_path]
            
            if on_path_stations:
                # Score on-path stations by price
                stations_to_score = on_path_stations
            else:
                # No stations on path, use path-aware detour logic with price scoring
                # Filter to acceptable detour stations using the same 1.5x distance rule
                destination = route_path[-1] if route_path else None
                if destination:
                    dist_to_dest, _ = self.dijkstra(from_node, destination)
                    acceptable_stations = []
                    
                    for station in stations:
                        station_node = station['nodeId']
                        dist_to_station, _ = self.dijkstra(from_node, station_node)
                        dist_station_to_dest, _ = self.dijkstra(station_node, destination)
                        
                        total_via_station = dist_to_station + dist_station_to_dest
                        if total_via_station <= dist_to_dest * 1.5:
                            acceptable_stations.append(station)
                    
                    if acceptable_stations:
                        stations_to_score = acceptable_stations
                        print(f"   ℹ️  No stations on path from {from_node}, using nearby stations")
                    else:
                        print(f"   ⚠️  No suitable charging stations found near path from {from_node}")
                        return None
                else:
                    stations_to_score = stations
        else:
            stations_to_score = stations
        
        # Score the filtered stations by price
        scored_stations = []
        
        for station in stations_to_score:
            zone_id = station['location']['zoneId']
            zone = self.zone_data.get(zone_id, {})
            
            # Get base price from zone
            base_price = zone.get('basePrice', 100)  # Default to 100 if not found
            
            # Calculate distance to station
            dist, _ = self.dijkstra(from_node, station['nodeId'])
            
            if dist == float('inf'):
                continue
            
            # Score: lower price is better, closer is better
            # Normalize distance penalty (divide by 10 to make price dominant)
            price_weight = self.strategy_config['station_selection']['cost_sensitive']['price_weight']
            dist_penalty = self.strategy_config['station_selection']['cost_sensitive']['distance_penalty']
            score = -(base_price * price_weight) - (dist * dist_penalty)
            
            scored_stations.append((score, station, base_price))
        
        if not scored_stations:
            return None
        
        scored_stations.sort(reverse=True, key=lambda x: x[0])
        best_station = scored_stations[0][1]
        best_price = scored_stations[0][2]
        
        print(f"   CostSensitive → Station {best_station['nodeId']} (Price: {best_price:.2f})")
        
        return best_station
    
    def _find_closest_station(self, stations: List[dict], from_node: str, route_path: Optional[List[str]] = None,
                              charge_remaining_kwh: Optional[float] = None,
                              consumption_per_km: Optional[float] = None) -> Optional[dict]:
        """
        Find closest operational station, preferring stations on route_path if provided
        If charge_remaining_kwh and consumption_per_km provided, only return reachable stations.
        
        Args:
            stations: List of operational stations
            from_node: Starting node
            route_path: Optional route path to prioritize on-path stations
            charge_remaining_kwh: Current battery charge in kWh
            consumption_per_km: Energy consumption per kilometer
        """
        # If route provided, use path-aware selection
        if route_path:
            return self._find_nearest_station_to_node(from_node, route_path, 
                                                     charge_remaining_kwh, consumption_per_km)
        
        # Otherwise, simple nearest distance (with reachability filtering if battery info provided)
        if charge_remaining_kwh is not None and consumption_per_km is not None:
            reachability_margin = self.strategy_config['charging_thresholds']['reachability_margin']
            reachable_stations = []
            for station in stations:
                dist, _ = self.dijkstra(from_node, station['nodeId'])
                if dist == float('inf'):
                    continue
                energy_needed = dist * consumption_per_km
                if charge_remaining_kwh >= energy_needed * reachability_margin:
                    reachable_stations.append(station)
            
            if not reachable_stations:
                print(f"⚠️ No reachable closest stations from {from_node} (have {charge_remaining_kwh:.1f} kWh)")
                return None
            
            stations = reachable_stations
        
        min_dist = float('inf')
        closest_station = None
        
        for station in stations:
            dist, _ = self.dijkstra(from_node, station['nodeId'])
            
            if dist < min_dist:
                min_dist = dist
                closest_station = station
        
        if closest_station:
            print(f"   Closest → Station {closest_station['nodeId']} (Distance: {min_dist:.1f} km)")
        
        return closest_station
    
    def calculate_charge_amount(self, customer: dict, total_distance: float, 
                               persona: str) -> float:
        """
        Calculate how much to charge based on persona and journey
        
        Returns:
            Charge level as fraction (0.0 to 1.0)
        """
        max_charge = customer['maxCharge']
        consumption = customer['energyConsumptionPerKm']
        
        # Get persona charge target from config
        charge_targets = self.strategy_config['persona_charge_targets']
        
        # Energy needed for journey with safety margin
        energy_buffer = self.strategy_config['charging_thresholds']['energy_buffer_multiplier']
        energy_needed = total_distance * consumption * energy_buffer
        
        if persona == 'Stressed':
            return charge_targets.get('Stressed', 1.0)
        
        elif persona == 'CostSensitive':
            # Charge just enough + small buffer, but respect config minimum
            charge_fraction = min(1.0, energy_needed / max_charge + 0.1)
            return max(charge_targets.get('CostSensitive', 0.8), charge_fraction)
        
        elif persona == 'DislikesDriving':
            return charge_targets.get('DislikesDriving', 1.0)
        
        elif persona == 'EcoConscious':
            return charge_targets.get('EcoConscious', 1.0)
        
        else:  # Neutral
            return charge_targets.get('Neutral', 0.9)
    
    def generate_recommendations(self) -> dict:
        """
        Generate complete game input with recommendations for all customers
        
        Returns:
            Complete game input JSON structure
        """
        print("\n" + "="*80)
        print("AUTOMATED PERSONA STRATEGY - GENERATING RECOMMENDATIONS")
        print("="*80 + "\n")
        
        # Initialize game input structure
        map_name = self.map_data.get('name', self.map_data.get('mapName', 'Unknown'))
        game_input = {
            "mapName": map_name,
            "playToTick": 288,  # Full day
            "ticks": []
        }
        
        # Track recommendations by departure tick
        recommendations_by_tick = {}
        
        # Process each customer
        for idx, customer in enumerate(self.customers_data['customers']):
            customer_id = customer['customerId']
            persona = customer['persona']
            from_node = customer['fromNode']
            to_node = customer['toNode']
            departure_tick = customer['departureTick']
            charge_remaining_fraction = customer['chargeRemaining']
            max_charge = customer['maxCharge']
            consumption = customer['energyConsumptionPerKm']
            
            # Convert charge from fraction to kWh
            charge_remaining_kwh = charge_remaining_fraction * max_charge
            
            print(f"Customer {idx+1}/{len(self.customers_data['customers'])}: {customer_id} ({persona})")
            print(f"   Route: {from_node} → {to_node} (Departs: Tick {departure_tick})")
            
            # Calculate shortest path
            distance, path = self.dijkstra(from_node, to_node)
            
            if distance == float('inf'):
                print(f"   ⚠️  No path found! Skipping...")
                continue
            
            current_range = self.calculate_range(charge_remaining_kwh, consumption)
            print(f"   Distance(dijkstra): {distance:.1f} km, Current range: {current_range:.1f} km")
            
            # Check if charging is needed
            needs_charge = self.needs_charging(distance, charge_remaining_kwh, consumption)
            
            # ALWAYS charge to get points (per game rules)
            if True:  # Always charge at least once
                # Get customer battery info for reachability filtering
                charge_remaining_kwh = customer['maxCharge'] * customer['chargeRemaining']
                
                # Get vehicle-specific travel speed
                vehicle_speed = self.get_vehicle_speed(customer)
                
                # Estimate when customer will arrive at charging station
                # First, we need to find the station to know the distance
                temp_station = self.find_optimal_charging_station(customer, path, departure_tick,
                                                                  charge_remaining_kwh, consumption)
                
                if temp_station:
                    station_node = temp_station['nodeId']
                    
                    # Calculate distance to station and estimate arrival tick using vehicle speed
                    dist_to_station, _ = self.dijkstra(from_node, station_node)
                    # Use actual vehicle speed from zone weather data
                    estimated_travel_ticks = int(dist_to_station / vehicle_speed) + 1 if vehicle_speed > 0 else int(dist_to_station) + 1
                    estimated_arrival_tick = departure_tick + estimated_travel_ticks
                    
                    # Now find the optimal station using the estimated arrival tick
                    charging_station = self.find_optimal_charging_station(customer, path, estimated_arrival_tick,
                                                                          charge_remaining_kwh, consumption)
                    
                    if charging_station:
                        station_node = charging_station['nodeId']
                    
                    # Calculate charge amount
                    charge_to = self.calculate_charge_amount(customer, distance, persona)
                    
                    print(f"   ✓ Will charge at {station_node} to {charge_to*100:.0f}%")
                    
                    # Create recommendation using chargingRecommendations format
                    # Add at the customer's departure tick
                    recommendation = {
                        "customerId": customer_id,
                        "chargingRecommendations": [
                            {
                                "nodeId": station_node,
                                "chargeTo": charge_to
                            }
                        ]
                    }
                    
                    # Add to the tick matching customer's departureTick
                    if departure_tick not in recommendations_by_tick:
                        recommendations_by_tick[departure_tick] = []
                    recommendations_by_tick[departure_tick].append(recommendation)
                
                else:
                    print("   ⚠️ No suitable charging station found")
                    # Provide empty recommendations (will use default path)
                    recommendation = {
                        "customerId": customer_id,
                        "chargingRecommendations": []
                    }
                    if departure_tick not in recommendations_by_tick:
                        recommendations_by_tick[departure_tick] = []
                    recommendations_by_tick[departure_tick].append(recommendation)
            
            print()
        
        # Build ticks array - create entries for all ticks that have recommendations
        if recommendations_by_tick:
            max_tick = max(recommendations_by_tick.keys())
            for tick in range(max_tick + 1):
                tick_data = {"tick": tick}
                if tick in recommendations_by_tick:
                    tick_data["customerRecommendations"] = recommendations_by_tick[tick]
                game_input["ticks"].append(tick_data)
        
        print("="*80)
        total_recs = sum(len(recs) for recs in recommendations_by_tick.values())
        print(f"✓ Generated {total_recs} recommendations")
        print(f"✓ Across {len(recommendations_by_tick)} different departure ticks")
        print("="*80 + "\n")
        
        return game_input
    
    def save_game_input(self, output_file: str):
        """Generate and save complete game input"""
        game_input = self.generate_recommendations()
        
        with open(output_file, 'w') as f:
            json.dump(game_input, f, indent=2)
        
        print(f"✓ Saved game input to: {output_file}")
        return game_input
    
    def _evaluate_and_add_charging_recommendations(self, game_result: dict, current_tick: int, 
                                                   dynamic_game_input: dict) -> int:
        """
        Evaluate game result and add charging recommendations for customers who need them
        
        Args:
            game_result: Result from the game API
            current_tick: Current tick number
            dynamic_game_input: Dynamic game input that will be modified
            map_name: Name of the map
            
        Returns:
            Number of new recommendations added
        """
        new_recommendations = []
        customer_logs = game_result.get('customerLogs', [])
        
        # Save engine paths for all customers (including new bonus customers)
        self.save_engine_paths(customer_logs)
        
        # Collect zone logs from this game result
        self.collect_zone_logs_from_result(game_result)
        
        # Get customers in DestinationReached state from map nodes
        completed_customers = set()
        game_map = game_result.get('map', {})
        nodes = game_map.get('nodes', [])
        
        # nodes is a list, iterate directly
        for node_data in nodes:
            customers = node_data.get('customers', [])
            for customer in customers:
                if customer.get('state') == 'DestinationReached':
                    completed_customers.add(customer.get('id'))
        
        for customer_log in customer_logs:
            customer_id = customer_log.get('customerId')
            persona = customer_log.get('persona', 'Neutral')
            logs = customer_log.get('logs', [])
            
            if not logs:
                continue
            
            # Skip if customer has completed (in DestinationReached state)
            if customer_id in completed_customers:
                continue
            
            # Get destination from the FIRST log entry (when path is set)
            # Path becomes null when customer is Traveling on an edge
            first_log = logs[0]
            first_path = first_log.get('path', [])
            destination = first_path[-1] if first_path else None
            
            # Get current state
            current_log = logs[-1]
            state = current_log.get('state')
            charge_remaining_fraction = current_log.get('chargeRemaining', 0)
            current_node = current_log.get('node')
            
            # Get maxCharge from game map (search nodes and edges for this customer)
            max_charge = 100  # Default
            consumption_per_km = 1.0  # Default
            
            # Search in nodes
            for node_data in nodes:
                customers_on_node = node_data.get('customers', [])
                for cust in customers_on_node:
                    if cust.get('id') == customer_id:
                        max_charge = cust.get('maxCharge', 100)
                        consumption_per_km = cust.get('energyConsumptionPerKm', 1.0)
                        break
            
            # If not found in nodes, search in edges
            if max_charge == 100:  # Still default, not found yet
                edges = game_map.get('edges', [])
                for edge_data in edges:
                    customers_on_edge = edge_data.get('customers', [])
                    for cust in customers_on_edge:
                        if cust.get('id') == customer_id:
                            max_charge = cust.get('maxCharge', 100)
                            consumption_per_km = cust.get('energyConsumptionPerKm', 1.0)
                            break
            
            # Convert charge_remaining from fraction to kWh
            charge_remaining_kwh = charge_remaining_fraction * max_charge
            
            # Skip if customer hasn't departed yet (still at Home waiting)
            if state == 'Home':
                continue  # Customer hasn't started traveling yet
            
            # Skip if customer is currently charging (will be at same node multiple ticks)
            if state in ['WaitingForCharger', 'Charging', 'DoneCharging']:
                # Customer reached a charging station - clear pending recommendation
                if customer_id in self.pending_recommendations:
                    del self.pending_recommendations[customer_id]
                continue  # Customer is at charging station, don't check for loops
            
            # Check if customer reached the recommended station (even if not charging yet)
            # This handles cases where travel took longer than expected
            if customer_id in self.pending_recommendations:
                pending_station = self.pending_recommendations[customer_id]['station']
                if current_node == pending_station:
                    # Customer is at the recommended station - clear the pending recommendation
                    print(f"   ✅ {customer_id}: Reached recommended station {pending_station}, clearing pending rec")
                    del self.pending_recommendations[customer_id]
            
            # Skip if customer has already reached destination (but not yet marked DestinationReached)
            if destination and current_node == destination and state in ['TransitioningToNode', 'TransitioningToEdge']:
                continue  # Customer is at destination, don't add charging rec
            
            # Check for loop detection if customer is at a node AND has started traveling
            is_looping = False
            loop_config = self.strategy_config['loop_detection']
            if loop_config['enabled'] and current_node and state not in ['Home', 'WaitingForCharger', 'Charging', 'DoneCharging']:
                is_looping = self._detect_loop(customer_id, current_node)
            
            # Emergency charging threshold from config
            emergency_threshold = self.strategy_config['charging_thresholds']['emergency_threshold']
            is_emergency = charge_remaining_fraction < emergency_threshold
            
            # Get customer's original engine path and current position
            engine_path = self.customer_paths.get(customer_id)
            current_path = None
            if engine_path and current_node in engine_path:
                idx = engine_path.index(current_node)
                # Only consider the forward portion of the path (EXCLUDING current node to avoid going backward)
                # If customer is at node X, they should only go to stations ahead, not back to X
                current_path = engine_path[idx+1:] if idx + 1 < len(engine_path) else engine_path[idx:]
            elif engine_path and current_node:
                # Customer's current node is not in saved path (may have deviated or bonus customer just appeared)
                print(f"   ⚠️  Customer {customer_id} at {current_node} not in saved path, using log path")
                current_path = current_log.get('path')
            elif not engine_path:
                # No saved path for this customer (shouldn't happen after fix, but keep fallback)
                print(f"   ⚠️  No saved path for customer {customer_id}, using log path")
                current_path = current_log.get('path')
            else:
                # Fallback to whatever is in the log
                current_path = current_log.get('path')
            remaining_distance = 0.0
            remaining_distance = 0.0
            
            if current_path and len(current_path) > 1:
                # Calculate actual remaining distance using engine's path
                remaining_distance = self.calculate_path_distance(current_path)
                if remaining_distance > 0:
                    # Calculate if customer can reach destination with current charge (in kWh)
                    required_energy = remaining_distance * consumption_per_km
                    safety_margin = self.strategy_config['charging_thresholds']['safety_margin']
                    required_energy_safe = required_energy * safety_margin
                    
                    # Check if energy is critically low for remaining journey
                    if charge_remaining_kwh < required_energy_safe:
                        is_emergency = True
                        print(f"   🔋 {customer_id}: {remaining_distance:.1f}km left, "
                              f"need {required_energy_safe:.1f} kWh but have {charge_remaining_kwh:.1f} kWh")
            
            # Check if customer needs charging
            # Criteria: At a node with charge < proactive_threshold OR detected in a loop OR emergency
            proactive_threshold = self.strategy_config['charging_thresholds']['proactive_threshold']
            if state in ['TransitioningToNode', 'TransitioningToEdge'] and current_node:
                needs_intervention = charge_remaining_fraction < proactive_threshold or is_looping or is_emergency
                
                if needs_intervention:
                    # Use the forward-only path we calculated earlier (current_path already set above)
                    # This ensures we only recommend stations ahead, not behind
                    
                    # Find nearest charging station (prefer on-path stations, forward only, reachable with current charge)
                    nearest_station = self._find_nearest_station_to_node(
                        current_node, current_path, charge_remaining_kwh, consumption_per_km
                    )
                    
                    if nearest_station:
                        station_node = nearest_station['nodeId']
                        
                        # Station is guaranteed reachable (filtered in _find_nearest_station_to_node)
                        distance_to_station, _ = self.dijkstra(current_node, station_node)
                        energy_to_station = distance_to_station * consumption_per_km
                        
                        # Calculate charge amount based on persona using config
                        charge_targets = self.strategy_config['persona_charge_targets']
                        charge_to = charge_targets.get(persona, 0.90)
                        
                        # Create recommendation for next tick
                        recommendation = {
                            "customerId": customer_id,
                            "chargingRecommendations": [{
                                "nodeId": station_node,
                                "chargeTo": charge_to
                            }]
                        }
                        
                        # Track this pending recommendation
                        self.pending_recommendations[customer_id] = {
                            'station': station_node,
                            'tick': current_tick + 1
                        }
                        
                        # Build reason message with station distance info (show as percentage)
                        reason = f"Low charge ({charge_remaining_fraction:.1%}) at node {current_node}"
                        if is_emergency:
                            reason = f"🚨 EMERGENCY: Critical battery ({charge_remaining_fraction:.1%}) at node {current_node}"
                        elif is_looping:
                            reason = f"LOOP DETECTED + charge ({charge_remaining_fraction:.1%}) at node {current_node}"
                        
                        if distance_to_station > 0:
                            reason += f" → Station {station_node} ({distance_to_station:.1f}km, {energy_to_station:.1f} kWh)"
                        
                        new_recommendations.append({
                            'tick': current_tick + 1,
                            'recommendation': recommendation,
                            'reason': reason
                        })
        
        # Add new recommendations to dynamic input
        added_count = 0
        for rec_data in new_recommendations:
            tick = rec_data['tick']
            recommendation = rec_data['recommendation']
            
            # Find or create tick entry
            tick_entry = None
            for t in dynamic_game_input['ticks']:
                if t['tick'] == tick:
                    tick_entry = t
                    break
            
            if tick_entry is None:
                tick_entry = {'tick': tick, 'customerRecommendations': []}
                dynamic_game_input['ticks'].append(tick_entry)
            
            if 'customerRecommendations' not in tick_entry:
                tick_entry['customerRecommendations'] = []
            
            # Check if recommendation already exists for this customer
            customer_id = recommendation['customerId']
            already_exists = any(
                r['customerId'] == customer_id 
                for r in tick_entry['customerRecommendations']
            )
            
            if not already_exists:
                tick_entry['customerRecommendations'].append(recommendation)
                added_count += 1
                print(f"   + Added charging rec for {customer_id} at tick {tick}: {rec_data['reason']}")
        
        return added_count
    
    def _find_nearest_station_to_node(self, node_id: str, customer_path: Optional[List[str]] = None,
                                      charge_remaining_kwh: Optional[float] = None,
                                      consumption_per_km: Optional[float] = None) -> Optional[dict]:
        """
        Find the nearest operational charging station to a given node
        If customer_path is provided, prefer stations on that path or nearby
        If charge_remaining_kwh and consumption_per_km provided, only return reachable stations
        
        Args:
            node_id: Current node ID
            customer_path: Optional list of nodes in customer's remaining path (forward-only)
            charge_remaining_kwh: Optional current battery charge in kWh
            consumption_per_km: Optional energy consumption rate in kWh/km
            
        Returns:
            Station dictionary or None
        """
        min_dist = float('inf')
        nearest_station = None
        
        # Get operational stations
        operational_stations = [
            s for s in self.stations_data['chargingStations']
            if s.get('status', {}).get('operational', True) and 
               s.get('capacity', {}).get('availableChargers', 1) > 0
        ]
        
        # Filter to reachable stations if battery constraints provided
        if charge_remaining_kwh is not None and consumption_per_km is not None:
            reachability_margin = self.strategy_config['charging_thresholds']['reachability_margin']
            reachable_stations = []
            for station in operational_stations:
                dist_to_station, _ = self.dijkstra(node_id, station['nodeId'])
                energy_needed = dist_to_station * consumption_per_km
                # Use configured reachability margin for safety
                if charge_remaining_kwh >= energy_needed * reachability_margin:
                    reachable_stations.append(station)
            
            if not reachable_stations:
                print(f"   ⚠️  No reachable charging stations from {node_id} "
                      f"(have {charge_remaining_kwh:.1f} kWh)")
                return None
            
            operational_stations = reachable_stations
        
        # If path provided, use intelligent station selection
        if customer_path and len(customer_path) > 0:
            destination = customer_path[-1] if customer_path else None
            
            # Strategy 1: Look for stations ON the forward path
            on_path_stations = [
                s for s in operational_stations
                if s['nodeId'] in customer_path
            ]
            
            if on_path_stations:
                # Found stations on the forward path - use the nearest one
                for station in on_path_stations:
                    station_node = station['nodeId']
                    dist, _ = self.dijkstra(node_id, station_node)
                    
                    if dist < min_dist:
                        min_dist = dist
                        nearest_station = station
                
                return nearest_station
            
            # Strategy 2: No stations on path - find nearby stations that are "forward-ish"
            # A station is acceptable if: distance_to_station + distance_station_to_dest <= distance_to_dest * 1.5
            # This allows small detours but prevents major backtracking
            if destination:
                dist_to_dest, _ = self.dijkstra(node_id, destination)
                
                acceptable_stations = []
                for station in operational_stations:
                    station_node = station['nodeId']
                    dist_to_station, _ = self.dijkstra(node_id, station_node)
                    dist_station_to_dest, _ = self.dijkstra(station_node, destination)
                    
                    # Allow detour if total distance is within 150% of direct route
                    total_via_station = dist_to_station + dist_station_to_dest
                    if total_via_station <= dist_to_dest * 1.9:
                        acceptable_stations.append((dist_to_station, station))
                
                if acceptable_stations:
                    # Sort by distance and take the nearest acceptable station
                    acceptable_stations.sort(key=lambda x: x[0])
                    nearest_station = acceptable_stations[0][1]
                    print(f"   ℹ️  No stations on path from {node_id}, using nearby station {nearest_station['nodeId']}")
                    return nearest_station
                else:
                    # No acceptable nearby stations - customer may run out of battery
                    print(f"   ⚠️  No suitable charging stations found near path from {node_id} to {destination}")
                    return None
        
        # No path provided (fallback for initial recommendations)
        # Find nearest station by distance
        for station in operational_stations:
            station_node = station['nodeId']
            dist, _ = self.dijkstra(node_id, station_node)
            
            if dist < min_dist:
                min_dist = dist
                nearest_station = station
        
        return nearest_station
    
    def _detect_loop(self, customer_id: str, current_node: str, lookback_ticks: int = None) -> bool:
        """
        Detect if a customer is stuck in a loop by checking if they've revisited nodes
        
        Args:
            customer_id: Customer ID to check
            current_node: Current node the customer is at
            lookback_ticks: Number of recent ticks to analyze (uses config if None)
            
        Returns:
            True if loop detected (oscillating between 2-3 different nodes), False otherwise
        """
        if lookback_ticks is None:
            lookback_ticks = self.strategy_config['loop_detection']['lookback_ticks']
        
        if customer_id not in self.customer_visit_history:
            self.customer_visit_history[customer_id] = []
        
        # Add current node to history
        history = self.customer_visit_history[customer_id]
        
        # Skip if already in history at the same position (haven't moved)
        if history and history[-1] == current_node:
            return False  # Still at same node, not moving yet
        
        history.append(current_node)
        
        # Keep only recent history (last lookback_ticks entries)
        if len(history) > lookback_ticks:
            history = history[-lookback_ticks:]
            self.customer_visit_history[customer_id] = history
        
        # Get loop detection thresholds from config
        two_node_min = self.strategy_config['loop_detection']['two_node_loop_min_visits']
        three_node_min = self.strategy_config['loop_detection']['three_node_loop_min_visits']
        
        # Need at least two_node_min visits to detect a 2-node loop
        if len(history) < two_node_min:
            return False
        
        # Check for 2-node oscillation pattern (A→B→A→B→A→B)
        recent = history[-two_node_min:]  # Last N visits
        
        # Check if alternating between just 2 DIFFERENT nodes
        unique_nodes = set(recent)
        if len(unique_nodes) == 2:
            node_a, node_b = list(unique_nodes)
            # Check if pattern alternates between different nodes
            alternating = all(
                recent[i] != recent[i+1] for i in range(len(recent)-1)
            )
            if alternating:
                print(f"   🔄 LOOP DETECTED for {customer_id}: oscillating between {node_a}↔{node_b}")
                return True
        
        # Check for 3-node loop pattern (A→B→C→A→B→C) with DIFFERENT nodes
        if len(history) >= three_node_min:
            recent_n = history[-three_node_min:]
            unique_in_n = set(recent_n)
            # Only check if we have 3 different nodes
            cycle_len = 3
            if len(unique_in_n) == cycle_len:
                # Check if pattern repeats
                cycles = three_node_min // cycle_len
                pattern_match = all(
                    recent_n[i] == recent_n[i + cycle_len] 
                    for cycle in range(cycles - 1)
                    for i in range(cycle_len)
                )
                if pattern_match:
                    loop_nodes = recent_n[:cycle_len]
                    print(f"   🔄 LOOP DETECTED for {customer_id}: repeating pattern {loop_nodes}")
                    return True
        
        return False
    
    def _submit_to_cloud(self, game_input: dict, cloud_api_url: str = "https://api.considition.com/api/game",
                        api_key: str = "xxx") -> Optional[dict]:
        """
        Submit final game input to the cloud API
        
        Args:
            game_input: Complete game input with all ticks
            cloud_api_url: Cloud API endpoint
            api_key: API key for authentication
            
        Returns:
            Cloud game result or None if submission failed
        """
        import requests
        
        try:
            print("\n" + "="*80)
            print("☁️  SUBMITTING TO CLOUD API")
            print("="*80)
            print(f"Endpoint:      {cloud_api_url}")
            print(f"Map:           {game_input['mapName']}")
            print(f"Total ticks:   {len(game_input['ticks'])}")
            
            headers = {
                'Content-Type': 'application/json',
                'x-api-key': api_key
            }
            
            response = requests.post(cloud_api_url, json=game_input, headers=headers)
            
            if response.status_code == 200:
                cloud_result = response.json()
                game_id = cloud_result.get('gameId')
                score = cloud_result.get('score', 0)
                
                print(f"\n✅ SUCCESS!")
                if game_id:
                    print(f"   Game ID:              {game_id}")
                    print(f"   Score:                {score:,.2f}")
                    print(f"   kWh Revenue:          {cloud_result.get('kwhRevenue', 0):,.2f}")
                    print(f"   Customer Completion:  {cloud_result.get('customerCompletionScore', 0):,.2f}")
                    
                    achievements = cloud_result.get('unlockedAchievements', [])
                    if achievements:
                        print(f"\n🏆 Unlocked Achievements: {', '.join(achievements)}")
                else:
                    print(f"   No Game ID returned (score did not beat previous best)")
                    print(f"   Current score:        {score:,.2f}")
                
                print("="*80 + "\n")
                return cloud_result
            else:
                print(f"\n✗ FAILED: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                print("="*80 + "\n")
                return None
                
        except Exception as e:
            print(f"\n✗ ERROR: {e}")
            print("="*80 + "\n")
            return None
    
    def _print_weather_summary(self, game_result: dict):
        """Print weather and energy production summary from zoneLogs"""
        zone_logs = game_result.get('zoneLogs', [])
        if not zone_logs:
            return
        
        # Aggregate weather and energy data across all ticks and zones
        total_wind_production = 0
        total_solar_production = 0
        total_green_production = 0
        total_non_green_production = 0
        total_revenue = 0
        weather_counts = {}
        tick_count = 0
        zone_count = 0
        
        for tick_log in zone_logs:
            zones = tick_log.get('zones', [])
            tick_count += 1
            
            for zone in zones:
                zone_count += 1
                weather_type = zone.get('weatherType', 0)
                weather_counts[weather_type] = weather_counts.get(weather_type, 0) + 1
                
                total_revenue += zone.get('totalRevenue', 0)
                
                sourceinfo = zone.get('sourceinfo')
                if sourceinfo and isinstance(sourceinfo, dict):  # Check if sourceinfo exists and is a dict
                    for source_name, source_data in sourceinfo.items():
                        if not isinstance(source_data, dict):  # Skip if source_data is not a dict
                            continue
                        
                        production = source_data.get('production', 0)
                        is_green = source_data.get('isGreen', False)
                        
                        if source_name == 'Wind':
                            total_wind_production += production
                        elif source_name == 'Solar':
                            total_solar_production += production
                        
                        if is_green:
                            total_green_production += production
                        else:
                            total_non_green_production += production
        
        # Calculate percentages
        total_production = total_green_production + total_non_green_production
        green_pct = (total_green_production / total_production * 100) if total_production > 0 else 0
        wind_pct = (total_wind_production / total_production * 100) if total_production > 0 else 0
        solar_pct = (total_solar_production / total_production * 100) if total_production > 0 else 0
        
        # Weather type names (based on game rules)
        weather_names = {
            0: '☀️  Clear',
            1: '⛅ PartlyCloudy',
            2: '☁️  Cloudy',
            3: '🌫️  Overcast',
            4: '💨 Windy',
            5: '⛈️  Storm'
        }
        
        print("\n  🌤️  Weather & Energy Analysis:")
        print(f"    Zone-Ticks Analyzed:  {zone_count} (each tick × number of zones)")
        print(f"\n    ⚡ Energy Production:")
        print(f"      🌱 Green Energy:       {total_green_production:,.2f} MWh ({green_pct:.1f}%)")
        print(f"      ⚫ Non-Green Energy:   {total_non_green_production:,.2f} MWh ({100-green_pct:.1f}%)")
        print(f"      💨 Wind Production:    {total_wind_production:,.2f} MWh ({wind_pct:.1f}%)")
        print(f"      ☀️  Solar Production:   {total_solar_production:,.2f} MWh ({solar_pct:.1f}%)")
        print(f"      📊 Total Production:   {total_production:,.2f} MWh")
        
        print(f"\n    🌦️  Weather Distribution:")
        for weather_code, count in sorted(weather_counts.items()):
            weather_name = weather_names.get(weather_code, f'❓ Unknown({weather_code})')
            pct = count / zone_count * 100 if zone_count > 0 else 0
            print(f"      {weather_name:20s}: {count:5d} zone-ticks ({pct:5.1f}%)")
    
    def _extract_weather_summary(self, game_result: dict) -> dict:
        """Extract weather and energy production summary data from zoneLogs"""
        zone_logs = game_result.get('zoneLogs', [])
        if not zone_logs:
            return {}
        
        # Aggregate data
        total_wind_production = 0
        total_solar_production = 0
        total_green_production = 0
        total_non_green_production = 0
        weather_counts = {}
        tick_count = 0
        zone_count = 0
        
        for tick_log in zone_logs:
            zones = tick_log.get('zones', [])
            tick_count += 1
            
            for zone in zones:
                zone_count += 1
                weather_type = zone.get('weatherType', 0)
                weather_counts[weather_type] = weather_counts.get(weather_type, 0) + 1
                
                sourceinfo = zone.get('sourceinfo')
                if sourceinfo and isinstance(sourceinfo, dict):  # Check if sourceinfo exists and is a dict
                    for source_name, source_data in sourceinfo.items():
                        if not isinstance(source_data, dict):  # Skip if source_data is not a dict
                            continue
                        
                        production = source_data.get('production', 0)
                        is_green = source_data.get('isGreen', False)
                        
                        if source_name == 'Wind':
                            total_wind_production += production
                        elif source_name == 'Solar':
                            total_solar_production += production
                        
                        if is_green:
                            total_green_production += production
                        else:
                            total_non_green_production += production
        
        total_production = total_green_production + total_non_green_production
        
        return {
            'totalTicks': tick_count,
            'totalZoneTicks': zone_count,
            'energyProduction': {
                'greenMWh': round(total_green_production, 2),
                'nonGreenMWh': round(total_non_green_production, 2),
                'windMWh': round(total_wind_production, 2),
                'solarMWh': round(total_solar_production, 2),
                'totalMWh': round(total_production, 2),
                'greenPercent': round(total_green_production / total_production * 100, 1) if total_production > 0 else 0,
                'windPercent': round(total_wind_production / total_production * 100, 1) if total_production > 0 else 0,
                'solarPercent': round(total_solar_production / total_production * 100, 1) if total_production > 0 else 0
            },
            'weatherDistribution': {
                str(code): count for code, count in weather_counts.items()
            }
        }
    
    def run_iterative_ticks(self, start_tick: int = 0, end_tick: int = None, 
                           tick_step: int = 1, api_url: str = "http://localhost:8080/api/game",
                           submit_to_cloud: bool = True):
        """
        Run the game iteratively, tick by tick, evaluating results and adding charging recommendations dynamically
        
        Args:
            start_tick: Starting tick (default: 0)
            end_tick: Ending tick (default: from config, typically 288)
            tick_step: Tick increment (default: 1)
            api_url: Game API endpoint
            submit_to_cloud: Submit to cloud API after full run completes (default: True)
        """
        import requests
        from datetime import datetime
        
        # Get map name and max ticks from config
        map_name = self.map_data.get('name', self.map_data.get('mapName', 'Turbohill'))
        max_ticks = self.config_data.get('ticks', 288)
        
        if end_tick is None:
            end_tick = max_ticks
        
        # Create log directory structure
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_dir = Path(__file__).parent.parent.parent / 'maps' / map_name.lower()
        log_dir = base_dir / 'logs' / timestamp
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create 'latest' symlink
        latest_link = base_dir / 'logs' / 'latest'
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(timestamp)
        
        print("\n" + "="*80)
        print("DYNAMIC ITERATIVE TICK-BY-TICK EXECUTION")
        print("="*80)
        print(f"Map:              {map_name}")
        print(f"Ticks:            {start_tick} to {end_tick} (step: {tick_step})")
        print(f"Log directory:    {log_dir}")
        print(f"Latest link:      {latest_link}")
        print("="*80 + "\n")
        
        # Start timing
        start_time = datetime.now()
        
        # Generate initial recommendations (only for departures)
        initial_game_input = self.generate_recommendations()
        
        # Initialize dynamic game input (will be modified as we go)
        dynamic_game_input = {
            "mapName": map_name,
            "ticks": []
        }
        
        # Copy initial recommendations to dynamic input
        for tick_data in initial_game_input["ticks"]:
            dynamic_game_input["ticks"].append(tick_data.copy())
        
        # Save initial input
        initial_input_file = log_dir / f"{map_name.lower()}_initial_input.json"
        with open(initial_input_file, 'w') as f:
            json.dump(initial_game_input, f, indent=2)
        print(f"✓ Saved initial input: {initial_input_file}\n")
        
        # Run tick by tick
        print("="*80)
        print(f"{'Tick':>4} | {'Score':>8} | {'kWh':>7} | {'Cust':>7} | "
              f"{'Total':>5} | {'Home':>4} | {'Travel':>6} | {'Charge':>6} | {'Done':>4} | {'New Recs':>8}")
        print("-"*80)
        
        tick_analyses = []
        added_recommendations_count = 0
        
        for tick in range(start_tick, end_tick + 1, tick_step):
            # Prepare input for this tick
            game_input_for_tick = {
                "mapName": map_name,
                "playToTick": tick,
                "ticks": [t for t in dynamic_game_input["ticks"] if t["tick"] <= tick]
            }
            
            # Run game to this tick
            try:
                response = requests.post(api_url, json=game_input_for_tick)
                if response.status_code != 200:
                    print(f"✗ Failed at tick {tick}: {response.status_code}")
                    break
                
                game_result = response.json()
            except Exception as e:
                print(f"✗ Error at tick {tick}: {e}")
                break
            
            # Only save tick_0 and final tick to reduce file clutter
            should_save = (tick == 0 or tick == max_ticks)
            
            if should_save:
                # Create tick directory
                tick_dir = log_dir / f"tick_{tick}"
                tick_dir.mkdir(exist_ok=True)
                
                # Save input and result
                input_file = tick_dir / f"{map_name.lower()}_tick_{tick}_input.json"
                result_file = tick_dir / f"{map_name.lower()}_tick_{tick}_result.json"
                
                with open(input_file, 'w') as f:
                    json.dump(game_input_for_tick, f, indent=2)
                
                with open(result_file, 'w') as f:
                    json.dump(game_result, f, indent=2)
            
            # Evaluate result and add new charging recommendations if needed
            new_recs = self._evaluate_and_add_charging_recommendations(
                game_result, tick, dynamic_game_input
            )
            added_recommendations_count += new_recs
            
            # Analyze result
            customer_logs = game_result.get('customerLogs', [])
            
            # Get actual customer states from map (not from customerLogs which don't show DestinationReached)
            states = {}
            map_data = game_result.get('map', {})
            
            # Count customers on nodes
            for node in map_data.get('nodes', []):
                for customer in node.get('customers', []):
                    state = customer.get('state', 'Unknown')
                    states[state] = states.get(state, 0) + 1
            
            # Count customers on edges (traveling/ran out of juice)
            for edge in map_data.get('edges', []):
                for customer in edge.get('customers', []):
                    state = customer.get('state', 'Unknown')
                    states[state] = states.get(state, 0) + 1
            
            analysis = {
                'tick': tick,
                'score': game_result.get('score', 0),
                'kwhRevenue': game_result.get('kwhRevenue', 0),
                'customerCompletionScore': game_result.get('customerCompletionScore', 0),
                'totalCustomers': len(customer_logs),
                'customerStates': states
            }
            tick_analyses.append(analysis)
            
            # Print summary
            completed = states.get('DestinationReached', 0)
            traveling = states.get('Traveling', 0)
            charging = states.get('Charging', 0)
            home = states.get('Home', 0)
            
            print(f"{tick:4d} | {analysis['score']:8.2f} | {analysis['kwhRevenue']:7.2f} | "
                  f"{analysis['customerCompletionScore']:7.2f} | {len(customer_logs):5d} | "
                  f"{home:4d} | {traveling:6d} | {charging:6d} | {completed:4d} | {new_recs:8d}")
        
        print("-"*80)
        print("\n" + "="*80)
        print("ITERATION COMPLETE")
        print("="*80)
        
        # Calculate execution time
        end_time = datetime.now()
        execution_time = end_time - start_time
        
        # Final summary
        if tick_analyses:
            final = tick_analyses[-1]
            print(f"\nFinal Results (Tick {final['tick']}):")
            print(f"  Total Score:           {final['score']:,.2f}")
            print(f"  kWh Revenue:           {final['kwhRevenue']:,.2f}")
            print(f"  Customer Completion:   {final['customerCompletionScore']:,.2f}")
            print(f"  Total Customers:       {final['totalCustomers']}")
            print(f"  Dynamic Recs Added:    {added_recommendations_count}")
            print(f"  ⏱️  Execution Time:       {execution_time.total_seconds():.2f}s ({execution_time})")
            
            print("\n  Customer States:")
            for state, count in sorted(final['customerStates'].items()):
                pct = count / final['totalCustomers'] * 100 if final['totalCustomers'] > 0 else 0
                print(f"    {state:20s}: {count:3d} ({pct:5.1f}%)")
            
            # Show key strategy config parameters
            config_name = self.strategy_config.get('name', 'unknown')
            print(f"\n  Strategy Configuration: {config_name}")
            print(f"    Charge Targets:")
            for persona, target in self.strategy_config['persona_charge_targets'].items():
                print(f"      {persona:20s}: {target:.2f}")
            print(f"\n    Charging Thresholds:")
            thresholds = self.strategy_config['charging_thresholds']
            print(f"      Proactive:           {thresholds['proactive_threshold']:.2f}")
            print(f"      Emergency:           {thresholds['emergency_threshold']:.2f}")
            print(f"      Safety Margin:       {thresholds['safety_margin']:.2f}")
            print(f"      Energy Buffer:       {thresholds['energy_buffer_multiplier']:.2f}")
            
            # Analyze weather impact from final game result
            if game_result and 'zoneLogs' in game_result:
                self._print_weather_summary(game_result)
        
        # Save summary with weather data
        summary_file = log_dir / f"{map_name.lower()}_iteration_summary.json"
        
        # Extract weather summary data if available
        weather_summary = None
        if game_result and 'zoneLogs' in game_result:
            weather_summary = self._extract_weather_summary(game_result)
        
        with open(summary_file, 'w') as f:
            summary_data = {
                'mapName': map_name,
                'startTick': start_tick,
                'endTick': end_tick,
                'tickStep': tick_step,
                'executionTime': {
                    'seconds': round(execution_time.total_seconds(), 2),
                    'formatted': str(execution_time)
                },
                'tickAnalyses': tick_analyses,
                'logDirectory': str(log_dir),
                'strategyConfig': {
                    'name': self.strategy_config.get('name', 'unknown'),
                    'persona_charge_targets': self.strategy_config['persona_charge_targets'],
                    'charging_thresholds': self.strategy_config['charging_thresholds']
                }
            }
            
            if weather_summary:
                summary_data['weatherSummary'] = weather_summary
            
            json.dump(summary_data, f, indent=2)
        
        print(f"\n✓ Summary saved: {summary_file}")
        print(f"✓ All logs saved to: {log_dir}")
        print(f"✓ Latest symlink: {latest_link}\n")
        
        # Submit to cloud if we completed a full run (check end_tick, not loop variable)
        cloud_result = None
        if submit_to_cloud and tick == max_ticks:
            # Prepare final game input (no playToTick, includes all ticks)
            final_game_input = {
                "mapName": map_name,
                "ticks": game_input_for_tick["ticks"]
            }
            
            # Save final input for reference
            final_input_file = log_dir / f"{map_name.lower()}_final_input.json"
            with open(final_input_file, 'w') as f:
                json.dump(final_game_input, f, indent=2)
            print(f"✓ Saved final input: {final_input_file}")
            
            # Submit to cloud
            cloud_result = self._submit_to_cloud(final_game_input)
            
            # Save cloud result if successful
            if cloud_result:
                cloud_result_file = log_dir / f"{map_name.lower()}_cloud_result.json"
                with open(cloud_result_file, 'w') as f:
                    json.dump(cloud_result, f, indent=2)
                print(f"✓ Saved cloud result: {cloud_result_file}\n")
        
        return tick_analyses


def main():
    """Run the automated strategy"""
    import sys
    import argparse
    from datetime import datetime
    
    parser = argparse.ArgumentParser(description='Automated Persona Strategy')
    parser.add_argument('--map-name', type=str, default='turbohill',
                       help='Map name (default: turbohill)')
    parser.add_argument('--strategy-config', type=str, default=None,
                       help='Strategy config file (default, conservative, aggressive, experimental, or path to JSON)')
    parser.add_argument('--mode', choices=['single', 'iterative'], default='single',
                       help='Run mode: single (one shot) or iterative (tick by tick)')
    parser.add_argument('--start-tick', type=int, default=0,
                       help='Starting tick for iterative mode')
    parser.add_argument('--end-tick', type=int, default=None,
                       help='Ending tick for iterative mode')
    parser.add_argument('--tick-step', type=int, default=1,
                       help='Tick increment for iterative mode')
    parser.add_argument('--api-url', type=str, default='http://localhost:8080/api/game',
                       help='Game API URL')
    parser.add_argument('--submit-to-cloud', action='store_true', default=False,
                       help='Submit to cloud API after full run completes (default: False)')
    parser.add_argument('--cloud-api-key', type=str, default='xxx',
                       help='Cloud API key')
    
    args = parser.parse_args()
    
    # Use map name from args
    map_name = args.map_name.lower()
    base_dir = Path(__file__).parent.parent.parent / 'maps' / map_name
    
    map_file = base_dir / f'{map_name}-map.json'
    customers_file = base_dir / f'{map_name}-customers.json'
    stations_file = base_dir / f'{map_name}-stations.json'
    config_file = base_dir / f'{map_name}-map-config.json'
    
    # Resolve strategy config path
    strategy_config_file = None
    if args.strategy_config:
        # Check if it's a preset name (default, conservative, aggressive, experimental)
        if args.strategy_config in ['default', 'conservative', 'aggressive', 'experimental', 'optimize_params']:
            config_dir = Path(__file__).parent / 'config'
            strategy_config_file = str(config_dir / f'automated_persona_strategy_{args.strategy_config}.json')
        else:
            # Treat as file path
            strategy_config_file = args.strategy_config
    
    print("🤖 AUTOMATED PERSONA STRATEGY")
    print("="*80)
    print(f"Mode:          {args.mode}")
    print(f"Map file:      {map_file}")
    print(f"Customers:     {customers_file}")
    print(f"Stations:      {stations_file}")
    print(f"Config:        {config_file}")
    if strategy_config_file:
        print(f"Strategy:      {strategy_config_file}")
    else:
        print(f"Strategy:      default (built-in)")
    print("="*80 + "\n")
    
    # Create strategy
    strategy = AutomatedPersonaStrategy(
        str(map_file),
        str(customers_file),
        str(stations_file),
        str(config_file),
        strategy_config_file
    )
    
    if args.mode == 'iterative':
        # Run iterative tick by tick
        strategy.run_iterative_ticks(
            start_tick=args.start_tick,
            end_tick=args.end_tick,
            tick_step=args.tick_step,
            api_url=args.api_url,
            submit_to_cloud=args.submit_to_cloud
        )
    else:
        # Single run mode
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = base_dir / f'automated_persona_input_{timestamp}.json'
        
        print(f"Output:        {output_file}\n")
        
        # Generate and save
        game_input = strategy.save_game_input(str(output_file))
        
        # Summary
        print("\n📊 STRATEGY SUMMARY")
        print("="*80)
        print(f"Map: {game_input['mapName']}")
        print(f"Total ticks: {len(game_input['ticks'])}")
        print(f"Total recommendations: {sum(len(t.get('customerRecommendations', [])) for t in game_input['ticks'])}")
        print("="*80 + "\n")
        
        print("✅ Ready to submit to game engine!")
        print("   curl -X POST http://localhost:8080/api/game \\")
        print("     -H 'Content-Type: application/json' \\")
        print(f"     -d @{output_file}")


if __name__ == '__main__':
    main()
