# Strategy Configuration Files

This directory contains configuration files for the `automated_persona_strategy.py` that allow you to easily experiment with different parameter values without modifying the code.

## 📁 Available Configurations

### `automated_persona_strategy_default.json`
**Balanced strategy** with moderate safety margins and charging thresholds.
- Proactive charging at 50% battery
- Emergency charging at 30% battery
- Standard loop detection (6 visits for 2-node loops)
- Best for: General testing and baseline performance

### `automated_persona_strategy_conservative.json`
**High success rate strategy** - charges earlier and more frequently to minimize RanOutOfJuice failures.
- Proactive charging at 60% battery (earlier!)
- Emergency charging at 40% battery
- More sensitive loop detection (4 visits)
- Higher charge targets for all personas
- Best for: Maximizing customer completion, reducing failures

### `automated_persona_strategy_aggressive.json`
**Fast strategy** - lower charging thresholds, risks running out for speed/score optimization.
- Proactive charging at 40% battery (later!)
- Emergency charging at 25% battery
- Lower charge targets (saves time)
- Best for: Speed optimization, higher risk tolerance

### `automated_persona_strategy_experimental.json`
**Experimental strategy** for testing extreme parameters.
- Very high charging thresholds (70% proactive, 50% emergency)
- Very sensitive loop detection (4 visits for 2-node, 6 for 3-node)
- All personas charge to 95-100%
- Best for: Testing edge cases and validating assumptions

## 🎯 Configuration Structure

Each configuration file contains:

```json
{
  "name": "strategy_name",
  "description": "What this strategy does",
  
  "charging_thresholds": {
    "proactive_threshold": 0.50,      // Trigger charging at this battery %
    "emergency_threshold": 0.30,       // Emergency charging threshold
    "safety_margin": 1.1,              // Multiply required energy (10% buffer)
    "energy_buffer_multiplier": 1.2    // Journey energy buffer (20%)
  },
  
  "persona_charge_targets": {
    "Stressed": 1.0,           // Full charge (minimize anxiety)
    "CostSensitive": 0.80,     // 80% (balance cost/range)
    "DislikesDriving": 1.0,    // Full charge (avoid extra stops)
    "EcoConscious": 1.0,       // Full at green stations
    "Neutral": 0.90            // 90% (good balance)
  },
  
  "loop_detection": {
    "enabled": true,
    "lookback_ticks": 20,              // Track last N node visits
    "two_node_loop_min_visits": 6,     // A→B→A→B→A→B = loop
    "three_node_loop_min_visits": 9    // A→B→C pattern 3x = loop
  },
  
  "station_selection": {
    "eco_conscious": {
      "green_energy_weight": 1000,     // Green% heavily outweighs distance
      "distance_penalty": 1.0
    },
    "cost_sensitive": {
      "price_weight": 1.0,
      "distance_penalty": 0.1          // Distance matters less than price
    },
    "stressed_dislikes_driving": {
      "prefer_closest": true
    }
  },
  
  "dynamic_intervention": {
    "enabled": true,
    "check_states": ["TransitioningToNode", "TransitioningToEdge"],
    "exclude_states": ["Home", "WaitingForCharger", "Charging", "DoneCharging"]
  }
}
```

## 🚀 Usage

### Using Preset Configurations

```bash
# Default (balanced)
python/venv/bin/python python/strategies/automated_persona_strategy.py \
  --map-name turbohill \
  --mode iterative \
  --strategy-config default

# Conservative (high success rate)
python/venv/bin/python python/strategies/automated_persona_strategy.py \
  --map-name turbohill \
  --mode iterative \
  --strategy-config conservative

# Aggressive (fast, risky)
python/venv/bin/python python/strategies/automated_persona_strategy.py \
  --map-name turbohill \
  --mode iterative \
  --strategy-config aggressive

# Experimental (extreme parameters)
python/venv/bin/python python/strategies/automated_persona_strategy.py \
  --map-name turbohill \
  --mode iterative \
  --strategy-config experimental
```

### Using Custom Configuration

```bash
# Create your own config file
cp automated_persona_strategy_default.json my_custom_config.json

# Edit parameters in my_custom_config.json
# Then use it:
python/venv/bin/python python/strategies/automated_persona_strategy.py \
  --map-name turbohill \
  --mode iterative \
  --strategy-config /path/to/my_custom_config.json
```

### No Config (Uses Built-in Defaults)

```bash
# Omit --strategy-config to use hardcoded defaults
python/venv/bin/python python/strategies/automated_persona_strategy.py \
  --map-name turbohill \
  --mode iterative
```

## 🔬 Parameter Experimentation Guide

### Most Impactful Parameters (Priority Order)

1. **`proactive_threshold`** (0.40-0.70)
   - **Most impact** on RanOutOfJuice failures
   - Higher = safer (more charging) but slower
   - Lower = faster but more failures

2. **`emergency_threshold`** (0.25-0.45)
   - Safety net for critical situations
   - Should always be lower than proactive_threshold

3. **`persona_charge_targets.CostSensitive`** (0.70-0.90)
   - CostSensitive is often the most failed persona
   - Higher = safer, Lower = faster but riskier

4. **`two_node_loop_min_visits`** (4-8)
   - Loop detection sensitivity
   - Lower = detect faster (more false positives)
   - Higher = more reliable (may miss some loops)

5. **`energy_buffer_multiplier`** (1.1-1.4)
   - Journey safety margin
   - Higher = more buffer but requires more charging

### Example Experiments

**Reduce 50% Failure Rate:**
```json
{
  "charging_thresholds": {
    "proactive_threshold": 0.60,     // Charge earlier
    "emergency_threshold": 0.40,     // Earlier emergency
    "energy_buffer_multiplier": 1.3  // More safety margin
  }
}
```

**Optimize for Speed:**
```json
{
  "charging_thresholds": {
    "proactive_threshold": 0.35,     // Charge later
    "emergency_threshold": 0.25,     // Lower threshold
    "energy_buffer_multiplier": 1.1  // Minimal buffer
  },
  "persona_charge_targets": {
    "Neutral": 0.75,                 // Charge less
    "CostSensitive": 0.70
  }
}
```

**Fix Loop Issues:**
```json
{
  "loop_detection": {
    "lookback_ticks": 30,            // Longer history
    "two_node_loop_min_visits": 4,   // Detect faster
    "three_node_loop_min_visits": 6  // Stricter
  }
}
```

## 📊 Testing Different Configurations

```bash
# Test all 4 configurations and compare results
for config in default conservative aggressive experimental; do
  echo "Testing $config configuration..."
  python/venv/bin/python python/strategies/automated_persona_strategy.py \
    --map-name turbohill \
    --mode iterative \
    --strategy-config $config \
    --end-tick 288 \
    > logs/test_${config}.log 2>&1
done

# Compare final scores
grep "Final Results" logs/test_*.log
```

## 🎓 Tips for Creating Your Own Config

1. **Start with a preset** - Copy default.json and modify gradually
2. **Change one parameter at a time** - Easier to see impact
3. **Test incrementally** - Use `--end-tick 50` for quick tests
4. **Document your changes** - Update the "description" field
5. **Keep backups** - Save configs that work well

## 📈 Expected Impact

| Configuration | RanOutOfJuice | Speed | Customer Completion |
|---------------|---------------|-------|---------------------|
| Conservative  | Low (10-20%)  | Slow  | High (80-90%)       |
| Default       | Medium (30-40%) | Medium | Medium (60-70%)   |
| Aggressive    | High (50-60%) | Fast  | Low (40-50%)        |
| Experimental  | Very Low (5-15%) | Very Slow | Very High (90%+) |

## 🆘 Troubleshooting

**Config file not found:**
- Check file path is correct
- Use preset names: `default`, `conservative`, `aggressive`, `experimental`
- Or provide full path to custom JSON file

**Strategy uses hardcoded defaults:**
- Config file has syntax errors (invalid JSON)
- Check file exists and is readable
- Look for error message in output

**Unexpected behavior:**
- Verify JSON is valid (use jsonlint.com)
- Check parameter values are within reasonable ranges
- Enable verbose logging to see which config is loaded
