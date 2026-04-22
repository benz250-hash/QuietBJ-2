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


v509 patch notes:
- Added expressway fallback road supplement when reverse geocode roads miss highways.
- Kept road categories independent; shielding remains a separate buffering item.
- Penalty card now shows raw -> adopted values explicitly.
- Added raw road candidate debug list under debug panel.


v510 patch notes:
- Removed expressway fallback API supplement.
- Restored pre-refactor road-bed logic: use reverse geocode roads only, classify locally by road kind.
- Kept v509 main/sub-engine structure and UI raw->adopted display.


v511 patch notes:
- Removed extra expressway fallback API search.
- Added Streamlit cache for input_tips / geocode / reverse_geocode / search_around.
- Added Chinese comments/docstrings to amap_provider.py and API_LOGIC_v511.txt.


v512 patch notes:
- Removed formal-query input_tips API call.
- Removed expressway fallback supplement; roads now come only from reverse geocode.
- Reduced fixed POI around searches from 5 to 3 (commercial / restaurant / rail).
- School and hospital are disabled by default to save API.
- Added API_LOGIC_v512.txt with simple Chinese notes.


v513 patch notes:
- Added cache export/import manager in app.py.
- Added structured export payload with schema_version / exported_at / app_version / stats / communities.
- Added merge import and replace import modes.
- Kept runtime cache auto-write behavior for building points.


v514 patch notes:
- Added cache table view in the cache manager.
- Added delete-one-community cache action.
- Added clear-all cache action.
- Kept export/import logic introduced in v513.


v516 patch notes:
- Removed input_tips from formal query flow.
- Removed expressway fallback around-search supplement.
- Restored low-API road-bed behavior: reverse_geocode roads only, local classification.
- Added API_LOGIC_v516.txt with simple Chinese API explanations.
