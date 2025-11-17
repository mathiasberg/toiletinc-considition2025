This application is for hackathon considition 2025.

Considition 2025 is an algorithmic challenge where you design a strategy to manage a fleet of electric vehicles (EVs). Your goal is to maximize your score by efficiently transporting customers to their destinations.
The competition runs from November 3rd to 12th with training maps, culminating in a secret, final map on November 13th. Each "game" is a simulation that runs in discrete time steps called "ticks," with 288 ticks representing a full day.
Your main task is to create an algorithm that makes key decisions for the EVs:
Routing: Choosing the best paths.
Charging: Deciding when and where to charge the vehicles.
Balancing Priorities: Juggling travel speed, cost, green energy usage, and customer satisfaction.
The final score is a combination of two factors:
kWh Revenue: Income earned from selling energy at charging stations.
Customer Completion Score: Points awarded for getting customers to their destinations after they have charged at least once.
Customers have different "personas" (like Cost-Sensitive or Eco-Conscious) which affect their scoring. The simulation also includes a weather system that impacts the availability of green energy (solar and wind), and an energy grid that can experience "brownouts," reducing charging capacity and revenue.

The complete rules are described in this file:considition-2025-rules.txt

swagger for the api is swagger.json

Summary of the structure of the maps/ directory and related scripts:
==================
maps/
├── README.md                    # Maps overview and workflow
└── turbohill/
    ├── README.md                # Turbohill-specific info
    ├── TURBOHILL_STRATEGY.md    # Complete strategy guide
    ├── turbohill-map.json       # Full map data
    ├── turbohill-summary.json   # Map summary
    ├── turbohill-visualization.png   # Main visualization
    ├── turbohill-heatmap.png    # Heatmap analysis
    └── test-turbohill.sh        # Testing script

Under maps all files related to each map are organized into their own subdirectory. Each map folder contains:
- A README.md with map-specific information.
- Strategy guides (e.g., TURBOHILL_STRATEGY.md).
- The full map data JSON file (e.g., turbohill-map.json).
- Summary JSON files with key statistics (e.g., turbohill-summary.json).
- Visualization images (e.g., turbohill-visualization.png, turbohill-heatmap.png).

🔧 Updated Scripts:
===================
✅ generate-map-summary.sh       → Now saves to maps/<mapname>/
✅ generate-map-visualization.sh → Now saves to maps/<mapname>/

Explain response structure:
important game output structure: 
  map - shows map at last tick with customers positions and states
  customerLogs - detailed logs per customer including their journey, states, and positions over ticks.
  customer state : example Home -> TransitioningToEdge -> Traveling -> TransitioningToNode -> DestinationReached. DestinationReached means the customer has reached their destination.
============
{
  "tick": 0,
  "gameId": null,
  "map": {...}, # shows map at last tick with customers positions and states
  "score": 0,
  "kwhRevenue": 0,
  "customerCompletionScore": 0,
  "customerLogs": [ # important customer journey logs
    {
      "customerId": "0.0",
      "name": "Customer 0.0",
      "maxCharge": 0,
      "persona": "Stressed",
      "vehicleType": "None",
      "logs": [
        {
          "state": "Home",  
          "mood": "Happy",
          "tick": 0,
          "posX": 5,
          "posY": 2,
          "chargeRemaining": 0.3534185,
          "ticksSpentWaiting": null,
          "path": [
            "5.2",
            "5.3",
            "6.3",
            "6.4",
            "7.4",
            "7.5",
            "7.6",
            "8.6",
            "9.6"
          ],
          "ticksSpentCharging": null,
          "edge": null,
          "node": "5.2"
        }
      ]
    },
    ...
  ],
  "unlockedAchievements": [],
  "zoneLogs": []
}

📝 Benefits:
============
✓ Clean organization by map
✓ Easy to add new training maps
✓ All related files in one place
✓ Scalable structure for 4 training maps + final
✓ Each map has its own README and strategy

🚀 Usage (unchanged):
====================
./generate-map-summary.sh Turbohill
./generate-map-visualization.sh Turbohill

Files automatically organized in: maps/turbohill/


Interactive Documentation:
Open in your browser: http://localhost:8080/scalar

/api/game
Validates, runs and scores your game

/api/game
Get previous game by gameId

/api/map​
Get map by name

/api/map-config
Get map config by name

/api/map-config
Get map config by name

/api/game-replay
Get game for playback

/api/game-with-custom-map
Special endpoint that is only available in a local environment. Here the player can post both a map and input data simultaneously, and thous create their own maps! When training AI this could be useful


GET /api/map-configs - List all available maps ✅
GET /api/map-config?mapName=Turbohill - Get specific map config ✅
GET /api/map?mapName=Turbohill - Get full map data ✅
POST /api/game - Run game simulation ✅
POST /api/game-replay - Replay a game
POST /api/game-with-custom-map - Custom maps (advanced)

Example API usage:
# Map metadata
GET /api/map-config?mapName={mapName}

# Full map with customers
GET /api/map?mapName={mapName}


Website: https://www.considition.com/rules
Here are the complete rules

== How to Play
From training maps to real challenges
Between November 3rd – 12th, you'll receive four training maps to practice on. Each map comes with starting conditions, and your goal is to guide electric vehicles (EVs) filled with customers to their destinations.

Important! the game should always be played locally and when you feel like there is a game you want to "save" (has to be better than ur last high score to be saved) then you should post it to the API

== A map consists of
- Roads and destinations
-Charging stations (regular & green)
-Electric vehicles with limited battery capacity
-Customers with unique "personalities" and preferences

== Your task is to design an algorithm that makes the smartest decisions
-Which route to take
-Where and when to charge
-How to balance speed, sustainability, and customer satisfaction


== Quick overview
The simulation runs in discrete ticks: 1 tick = 5 minutes. There are 288 ticks per simulated day.
You run a map (a match) locally using the player Docker image or via the API. The engine simulates customers, charging, the power grid, and scores your run.
Final score = kWh revenue (charging income) + customer completion score.
Released maps are validated on the cloud API; locally you can play arbitrary or experimental maps using the Docker player image.


== Start playing — quick steps
1. Pull and run the player Docker image
# pull latest player image
docker pull considition/considition2025:latest

# You can optionally pass CACHE_ENABLED = false if you want to disable cached gamestate
# run the local player with (example)
docker run considition/considition2025 -p 8080:8080


2. Inspect map & config (local)
# Map metadata
GET /api/map-config?mapName={mapName}

# Full map with customers
GET /api/map?mapName={mapName}

3. Run a game
POST your input to run the simulation (examples can be found in the starterkits):

curl -X POST "http://localhost:8080/api/game" \
  -H "Content-Type: application/json" \
  -d '{
    "mapName": "example-map",
    "playToTick": 288,
    "ticks": []
  }'
Cloud API requires authorization: x-api-key: <api-key>. We release official maps through new docker images. Current mapName and seed will be visible through our visualizer (Coming soon).

== Maps, seeds and local testing
The Docker player image lets you run any map locally (including random/experimental maps).

The cloud/API accepts only released maps. For reproducible runs we publish mapName + seed.

If no seed is provided, the engine uses a random seed.

Recommended flow: fetch the map config via /api/map-config, tweak local MapConfigDto values (cloud/wind volatility, offsets, ticks) and re-run locally.


== Gameplay fundamentals
What happens each tick
Add new customers per map rules.
Process customer state machines — movement, charging, and transitions.
Update zones: aggregate charging demand, request energy from the grid, handle brownouts.
Compute revenue and customer completion events.


== Customer state machine
Typical lifecycle:

Home -> TransitioningToEdge -> Traveling -> TransitioningToNode -> DestinationReached
                |
         WaitingForCharger -> Charging -> DoneCharging
                |
         FailedToCharge (on supply shortage)


== Scoring
Score is composed of two main parts:

- Score breakdown
- kWh revenue
energy sold at charging stations in zones. Brownouts reduce supplied energy and therefore revenue.
- Customer completion score
points for customers that reach their destination. The scoring depends on persona, time, charging behavior and penalties. The requirement to achieve customer completion score on a customer is that they charge at least once and then reach their destination.


== What the API returns
GameId — this will only be set in cloud environment, only returns a guid if you've beaten your own score.
Score — total score (revenue + completion)
KwhRevenue — revenue from energy sold
CustomerCompletionScore
DetailsCustomerScores — per-customer score cards
UnlockedAchievements - Id of unlocked achievements (only on games submitted to cloud)

== Personas
Each customer has a Persona that influences behavior and scoring:

CostSensitive — penalizes expensive charging.
DislikesDriving — prefers shorter travel time.
EcoConscious — rewards greener energy usage.
Stressed — stronger preference for faster travel.
Neutral — baseline behavior.
Your challenge is to find out how each persona acts in different scenarios.

== Weather system
Weather is generated per tick using multi-octave smooth noise and a time-of-day pattern. The Weather object contains:

CloudCover (0..1) — reduces solar production
WindStrength (0..1) — affects wind production
WeatherType (enum) — Clear, PartlyCloudy, Cloudy, Overcast, Windy, Storm

Solar output follows a day cycle: 
no sunlight outside 6:00–18:00 local simulation time. 
Wind varies with time-of-day and noise. 
Good weather means that energy grid & zones use green energy which gives more points for the player when charging customers at the station.

== Energy grid & zones
The map is partitioned into zones. Each zone aggregates charging station demand and:

Requests energy from the simulated market/grid for the current tick.
Receives either full supply or a proportionally reduced supply (brownout).
Computes revenue for energy actually supplied.
Power grid snapshots compute production from solar/wind/other sources based on weather and time-of-day, factor storage decisions, and return price and availability to zones.


== API endpoints
API documentation can be found locally at: localhost:8080/openapi/v1.json
as well as rest client:localhost:8080/scalar
Get map config (local & cloud)
GET /api/map-config?mapName={mapName}
Get map populated (local & cloud)
GET /api/map?mapName={mapName}
Run game (local & cloud)
POST /api/game
Body: GameInputDto {
  mapName: string,
  playToTick?: int,
  ticks: TickInputDto[]
}


== Testing tips & troubleshooting
Recommended experiments
Run the Docker player to experiment with random maps and MapConfig variations.
Use the published map configurations to reproduce official maps.
Add local map configs with higher volatility to stress-test the grid.

== Common pitfalls
Brownouts will reduce charging throughput and revenue dramatically.
If a map is not released on the cloud, the cloud API may reject your run — use the local player image for experimentation.
Customer that havent charged at least once wont return any points
If you dont manage your customers, they can run out of juice on the way
If you feel like the cache is acting weird, use "CACHE_ENABLED = false" as docker environment variable to disable


== How to Win
Final night Challenge
On November 13th, all teams will face the same final map. This map is brand new and kept secret until the start. A warmup map will be released 17:45 with the grand finale starting at 19:15. It contains:

A unique seed and road layout
Charging stations
Customers with different personas
Limited battery capacity and iteration time.

== 45 intense minutes
You'll have 45 minutes to play your algorithm against the API. Once the time is up, the map is locked, and the winners are announced live on Twitch.

Spectators can follow live commentators, scoreboards and highlights from different teams. You'll also be able to visualize your own map with our built-in visualizer, watching your vehicles and customers move iteration by iteration.

== The team with the highest Total Score on the final map wins Considition 2025!

Prize Pool for Considition 2025
🥇 1st place: Choose your prize - valued at 40,000 SEK (~$4,000)

The Sustainability Roadtrip, Electric car & hotel package
Tech Gift Card, spend it on the latest gadgets, gear or smart tech
🥈 2nd place: 3,000 SEK Tech Gift Card (~$300)

🥉 3rd place: 2,000 SEK Tech Gift Card (~$200)

🙋 Best Single Player Award: 1,000 SEK Tech Gift Card (~$100)

🧠 Most Creative Algorithm: 1,000 SEK Tech Gift Card (~$100)

🤪 Best Worst Algorithm: 1,000 SEK Tech Gift Card (~$100)

🏅 Achievement Hunters (4 teams): 1,000 SEK Tech Gift Card (~$100 each)

