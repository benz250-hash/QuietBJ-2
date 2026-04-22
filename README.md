# QuietBJ Full Engineering Bundle v506

This is the full project bundle based on the earlier complete project package,
with the refactored core engine files overlaid from v505.

Included core files:
- app.py
- config.py
- engine_schema.py
- noise_point_engine.py
- shielding_engine.py
- building_engine.py
- score_engine.py
- building_overrides.csv
- community_building_cache.json

Included support files from the earlier full project:
- amap_provider.py
- community_repository.py
- zone_repository.py
- text_match.py
- communities.csv
- community_zones.csv
- background.jpg
- requirements.txt
- SECRETS_EXAMPLE.toml

Notes:
- Base score is 85.
- app.py remains the orchestration layer.
- score_engine.py is the main engine.
- subordinate engines return EngineResult objects.


v508 patch notes:
- Fixed penalty card to display main-engine adopted deltas.
- Shielding correction now shows as a separate positive buffering item.
- Highway / arterial / other road factors remain independent and are not replaced by shielding.
