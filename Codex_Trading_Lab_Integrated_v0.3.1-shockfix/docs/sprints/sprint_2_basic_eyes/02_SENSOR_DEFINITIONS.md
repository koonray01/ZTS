# Sensor Definitions v0.1

## Candle Features
คำนวณ body, range, wick, ratio และ range-to-median-true-range จากแท่งปิด

## Confirmed Swings
ใช้ symmetric fractal window ค่าเริ่มต้น left=2/right=2
จุด swing จะถูกยืนยันเมื่อมีแท่งด้านขวาครบแล้วเท่านั้น

## Basic Structure
เปรียบเทียบ confirmed swing highs/lows สองชุดล่าสุด:
- BULLISH: HH + HL
- BEARISH: LH + LL
- TRANSITION: โครงสร้างขัดกัน
- UNSCORABLE: ตัวอย่างไม่พอ

## Trend
ใช้ linear-regression slope ที่ normalize ด้วย median true range
ร่วมกับ directional efficiency

## Range
ใช้ directional efficiency, path efficiency และ bar overlap
เพื่อแยก RANGE / TRENDING / TRANSITION

## Volatility / Shock
ใช้ true-range ratio ต่อ rolling median และ body dominance
ค่าเริ่มต้นเป็น anomaly detector ไม่ใช่ execution gate

## Price Action
ตรวจ basic BREAK, SWEEP, RECLAIM, REJECTION และ DISPLACEMENT
โดยอ้าง confirmed swing ก่อนแท่งล่าสุด

## Important
นิยามทั้งหมดเป็น Research Definitions v0.1 ต้องผ่าน Replay, OOS และ Real MT5
ก่อนเลื่อนเป็น Canonical Rule
