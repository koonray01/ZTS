# Advanced Eyes Architecture

```text
Immutable Snapshot
    ↓
Basic Primitives
    ├─ confirmed swings
    ├─ true range
    ├─ candle direction
    └─ closed-bar break
    ↓
Advanced Sensors
    ├─ zone primitives
    ├─ S/R
    ├─ supply/demand
    ├─ liquidity
    ├─ FVG
    ├─ SMC structure
    ├─ order-block candidates
    └─ dealing range
    ↓
Sensor Schema Validation
```

ทางเข้าหลักมีเพียง:

```python
run_advanced_eyes(snapshot)
```

ไม่มี Sensor ตัวใดอนุญาตให้เข้าเทรด
