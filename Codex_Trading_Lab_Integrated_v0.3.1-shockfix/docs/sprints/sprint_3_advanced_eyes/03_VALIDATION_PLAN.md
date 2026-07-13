# Validation Plan

## Verify
- ใช้ closed bars เท่านั้น
- FVG ใช้สามแท่งตามลำดับ
- wick-through ไม่ถูกนับเป็น BOS
- CHoCH/MSS ย้อนกลับไปหา prior structure และ break ได้
- Order Block เป็น Candidate ไม่ใช่ Fact

## Validate
ต้องทดสอบแยก Incremental Value:
- Basic structure vs +S/R
- +Supply/Demand
- +Liquidity
- +FVG
- +SMC labels
- +Order Block

Metrics:
- entry precision
- opportunity throughput
- blocked winners / blocked losers
- entry latency
- expectancy by detector
- scenario usefulness

ชุดนี้ยังไม่ผ่าน Validate
