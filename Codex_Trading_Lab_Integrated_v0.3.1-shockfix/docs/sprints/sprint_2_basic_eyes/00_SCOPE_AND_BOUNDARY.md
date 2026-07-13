# Scope and Boundary

## Purpose
เตรียมโมดูล Market Perception แบบ deterministic ล่วงหน้า โดยไม่แตะ Runtime ของ Sprint 1

## Input
- Immutable snapshot schema version `0.2.0`
- Closed bars only
- One `snapshot_id` and one `run_id`

## Output
- Sensor outputs schema version `0.2.0`
- FACT / DERIVED / EVENT / UNKNOWN
- Evidence references
- No permission and no order action

## Hard boundaries
- ไม่เชื่อม MT5 เอง
- ไม่อ่านไฟล์จาก TradingOS ระบบหลัก
- ไม่แก้ raw evidence
- ไม่สร้าง BUY/SELL recommendation
- ไม่ให้ APPROVED/REJECTED trade permission
- ไม่อ้างว่า validated บนตลาดจริง
