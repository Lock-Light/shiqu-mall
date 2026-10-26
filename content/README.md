# 演示内容与开放素材

批次 `experience-content-20261024-v1`。

- `experience_catalog.py` 为原创虚构门店和体验课程编辑源；`catalog.json` 是可审阅的导入清单，含32店、96商品、48篇演示分享。不得将其当成真实商家供给或消费评价。
- `photo-manifest.json` 为40张Commons照片的逐图台账，包含作者、文件说明页、许可及链接、下载版本哈希、本地WebP和缩略图哈希、处理步骤和用途限制。各图及缩略图继承各自许可，独立于代码Apache 2.0。`asset-choices.json` 固定人工选图结果。
- 通过 `python scripts/content_assets.py` 校验或恢复固定台账中的素材；需Python与`requirements-content.txt`固定的Pillow。默认只使用已固定URL和哈希，不重新搜索排名；来源字节变化时停止，不悄悄替换。`--refresh-search`仅用于有意重新选图。API/下载限流按Retry-After等待；运行页面不依赖外部图片站点。
- 已选照片原始许可元数据保存于`photo-source-metadata.json`，Commons文件页与台账一一对应。额外候选在`photo-candidates.json`、缓存在`.runtime/content-sources`。页面署名入口为 `/content-sources.html`。
- `poi/shanghai-sports-osm-sample.json` 保留OSM原始ID、原始名称（可回退nameEn）、坐标、查询、来源链接和2026-10-24基准时间；原样本26条。仅将有名称且坐标有效的记录接入独立开放场所参考表，不生成商品、商户权限或评论。
- POI原样本与衍生数据库内容采用[ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/)，署名 **© OpenStreetMap contributors**；[版权说明](https://www.openstreetmap.org/copyright)。与原创虚构门店表保持独立。
- 原始POI文件的`importedIntoBusinessDatabase=false`为采集当时状态，原文件未改写；本批实际导入独立参考表25条，剔除1条无中文/英文名称记录。演示分享日期为固定编辑时间轴，非真实消费发生时间；关注关系仅在明确演示账号之间建立。
- 上游餐饮笔记/远程照片保留在“上游历史示例”，来源与逐图许可未完成核查，不用作本批次新图库或新体验语料。ASAP餐饮评论不导入；Foursquare受限数据不绕过登录，Overture为备选评估，不因其下载等待阻塞已有OSM样本。

首次复建：

1. 按项目README构建并启动当前前后端和基础设施，执行 `python scripts/migrate_commerce.py`，确认18091可用。
2. **先运行 `python scripts/seed_commerce.py`**，建立原30个商品、60个SKU及5个演示账号/权限。丰富内容为这60个既有SKU保留配置，不会替代这一步；导入器缺少基线时会在写账号/业务数据前拒绝执行。
3. 安装 `python -m pip install -r scripts/requirements-content.txt`（已有对应Pillow可跳过），再执行 `python scripts/content_assets.py` 校验或恢复40张固定素材。
4. 执行 `python scripts/import_content.py --apply`，补到32店/96商品/192SKU/48分享/25参考地点。
5. 重建前端 `npm --prefix hmdp-vue3 run build`，替换/重启本项目app以重新加载新门店Bloom索引，并执行 `docker compose exec -T web openresty -s reload`。

已有环境增量重跑只需校验图片并执行 `python scripts/import_content.py --apply`，不用重新建库。仅更新已知种子记录，旧SKU库存/价格/活动和交易快照保持不变；活动中商品内容不更新。备份、保护字段哈希与实际数量见`docs/evidence/content-import.json`。第一次完整新环境复建与本轮已验证的现有环境重跑属于不同场景，本轮验收不冒充执行过全新空库恢复。
