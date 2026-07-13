# Integration Handoff

Merge หลังจาก:
1. Sprint 1 real MT5 snapshots ผ่าน
2. Basic Eyes ผ่าน shadow run
3. Schema ยัง compatible
4. Human review Definition Registry
5. ไม่มี cross-system dependency

ลำดับ integration:
```text
Snapshot Service
→ Basic Eyes
→ Advanced Eyes
→ Fusion (milestone ถัดไป)
```

ห้ามให้ Advanced Eyes ดึง MT5 แยกเอง
