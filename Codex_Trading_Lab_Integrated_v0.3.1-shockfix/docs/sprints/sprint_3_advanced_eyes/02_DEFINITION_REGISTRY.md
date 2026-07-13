# Definition Registry v0.1

## Zone Primitive
กลุ่ม confirmed swing levels ที่อยู่ภายใน tolerance จาก median true range

## Support / Resistance
Zone ต่ำกว่าราคาปัจจุบันเป็น SUPPORT_CANDIDATE
Zone สูงกว่าราคาปัจจุบันเป็น RESISTANCE_CANDIDATE
หากราคาซ้อนใน Zone เป็น ACTIVE_INTERACTION

## Supply / Demand Candidate
Base candle ที่ range ต่ำกว่าค่าฐาน ตามด้วย departure ที่เคลื่อนออกอย่างมีนัยสำคัญ
เป็น Candidate เท่านั้น ไม่ใช่ Institutional Order proof

## Liquidity Pool
confirmed swing high/low ตั้งแต่สองจุดขึ้นไปที่ใกล้กันภายใน tolerance

## Fair Value Gap
- Bullish: low ของแท่งที่ 3 สูงกว่า high ของแท่งที่ 1
- Bearish: high ของแท่งที่ 3 ต่ำกว่า low ของแท่งที่ 1

## BOS
close ผ่าน confirmed swing ไปในทิศเดียวกับ prior structure

## CHoCH / MSS
close ผ่าน confirmed swing ฝั่งตรงข้าม prior structure
ใช้ชื่อ CHOCH_MSS_CANDIDATE จนกว่าจะมีนิยามแยกที่ผ่าน Validation

## Order Block Candidate
แท่งฝั่งตรงข้ามล่าสุดก่อน displacement + structural break
ไม่ถือว่าเป็น Fact ว่ามี institutional orders

## Dealing Range
กรอบจาก confirmed swing low/high ล่าสุด พร้อม equilibrium 50%
