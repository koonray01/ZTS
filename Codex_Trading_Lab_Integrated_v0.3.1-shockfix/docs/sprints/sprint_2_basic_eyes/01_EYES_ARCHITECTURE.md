# Eyes Architecture

```text
Immutable Snapshot
    ↓
Sensor Context
    ├─ Candle Features
    ├─ Swing Detector
    ├─ Basic Structure
    ├─ Trend State
    ├─ Range State
    ├─ Volatility / Shock
    └─ Price Action Events
    ↓
Schema Validation
    ↓
Basic Eyes Envelope
```

Sensors เป็นชิ้นเล็กและทดสอบแยกได้ แต่เรียกผ่าน `run_basic_eyes()` เพียงทางเดียว

## Ownership
- Sensor อ่าน facts/features/events
- Fusion และ Scenario ยังไม่อยู่ใน Pack นี้
- Entry และ Permission ไม่อยู่ใน Pack นี้
