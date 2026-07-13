# QA / QC / Verify / Validate

## QC
- snapshot schema version
- one run / one snapshot
- freshness status
- snapshot QC decision
- closed bars
- monotonic timestamps
- valid OHLC

## QA
- unit tests per sensor
- golden fixtures
- negative tests
- schema validation
- static safety scan

## Verify
- swing requires right-side confirmation
- wick through is not automatically a break
- sensor never emits trade permission
- blocked snapshot cannot be silently analyzed

## Validate
ยังไม่ผ่าน ต้องใช้:
- public replay
- broker data
- forward shadow
- incremental-value testing
- entry throughput metrics

Verify PASS ไม่ได้แปลว่า Validate PASS
