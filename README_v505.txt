QuietBJ refactor v505

这版把 v504 的引擎架构真正接进了现有主工程。

核心变化
1. app.py 继续做 orchestration
2. noise_point_engine / shielding_engine / building_engine 都返回 EngineResult
3. score_engine 作为主引擎统一 aggregate
4. engine_schema 负责统一 schema
5. 页面展示使用主引擎采纳后的 breakdown

说明
- 这包包含本次重构涉及的核心工程文件。
- 你原仓库里未修改的支持文件（如 amap_provider.py / community_repository.py / text_match.py / zone_repository.py / communities.csv / community_zones.csv / background.jpg）继续沿用原来的即可。
