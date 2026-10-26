# Native test fixtures

`bambu-pla-basic-white.json` models the public TigerTag product response for
product 3608667697 (Bambu PLA Basic, Jade White, non-refill). Product identifiers
and technical values are retained to exercise the generated catalog index.
Descriptions and timestamps are omitted; URLs use `example.test`. It contains
no account records, credentials or physical tag identities.

Tag identities and account records in `test-inventory.py` are synthetic. The
tests do not contact the product API, Firestore, a reader or a scale.

`tigertag-encoding.json` contains 16 synthetic, 80-byte golden vectors checked
against the official JavaScript SDK, Python SDK, and protocol-guide serializer.
The pinned source revisions are recorded in the fixture. The vectors cover
standard/Plus format IDs, all supported weight units, numeric fields, both twin
indices, and UTF-8 characters crossing the raw 28-byte message boundary.
Expected bytes come from those upstream serializers, not the firmware encoder.
