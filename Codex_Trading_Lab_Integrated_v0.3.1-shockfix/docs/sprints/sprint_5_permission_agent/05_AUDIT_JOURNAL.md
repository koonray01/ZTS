# Audit Journal

Records are JSON Lines with:
- sequence
- event_type
- payload_hash
- previous_record_hash
- record_hash
- created_at

Journal verification must detect:
- edited record
- removed middle record
- changed sequence
- broken previous hash

Journal does not contain credentials or full account numbers.
