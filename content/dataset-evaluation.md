本文件保留导入前的选型核查。当前实际接入为25条有名称OSM记录，实际导入与验收见docs/内容补强验收报告.md；原始26条样本在content/poi。

# 同城体验商城：可直接使用的开放数据选型

核查日期：2026-10-24。用于本轮商品、门店、图片与内容补强，不增加 BI 功能。以下为一手文档核查，实际城市覆盖、可下载性和字段完整度仍需小样本验证；不把文档存在称为已经导入。

## 推荐顺序

| 来源 | 能直接提供什么 | 许可与获取 | 对本项目的用途与限制 |
|---|---|---|---|
| [Overture Places](https://docs.overturemaps.org/guides/places/) | 门店/场所名、地址、坐标、分类、来源、置信度 | Places 官方说明为 CDLA Permissive 2.0 / Apache 2.0，可按边界框下载 GeoJSON；实际保留记录来源及对应许可 | 优先抽取上海小区域，补附近查询和搜索。没有完整套餐、价格、SKU、评论或图片组；中文及体验行业覆盖需实测 |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) | 门店与运动设施等兴趣点，部分含营业时间和地址 | ODbL，保留贡献者署名及数据许可，衍生数据库分发按许可处理；Overpass 可查询小区域 | 备选，适合 GEO。字段有缺失，不是现成在售商品库；本次接口小样本获取状态见下文 |
| [Foursquare OS Places](https://huggingface.co/datasets/foursquare/fsq-os-places) | 地点名、经纬度、地址、类别、更新/关闭标记等 | 数据标注 Apache 2.0，但当前 Hugging Face 下载入口有访问门槛，要求登录及接受额外条件 | 不作为无需账号即可下载的首选；不为获取数据擅自同意机构名称/logo使用条款。完整字段见[官方 schema](https://docs.foursquare.com/data-products/docs/places-os-data-schema) |
| [美团 ASAP](https://github.com/Meituan-Dianping/ASAP) | 中文餐饮评论、星级及细分情感标注 | 仓库有 Apache 2.0 许可及样本 CSV，沿用现有素材选型的核查记录 | 适合餐饮评论语料；不能把餐饮文本直接改店名放进攀岩/陶艺商品，不补齐本项目的非餐饮商品和照片 |

## Overture 的实际接入注意点

官方当前文档明确：2026 年 9 月起移除旧 `categories` 字段，使用 `taxonomy` 与 `basic_category`。旧教程中的 `categories.primary` 不能直接用于当前发行版。

官方按范围提取示例：

```text
overturemaps download --bbox=12.46,41.89,12.48,41.91 -f geojson --type=place -o rome.geojson
```

这是文档示例，并非本次已经运行的上海导入命令。实施时固定实际发行版/下载时间，先检查少量上海记录的名称、坐标、分类及来源，再决定采用范围；不要下载全球全量数据。

## 数据与商品的关联方式

真实 POI 用于“附近场所/开放数据参考”，保留 `sourceId`、来源页、版本和许可。没有真实合作关系时，不把它说成平台已入驻商户，也不在真实场所名下虚构在售套餐、消费评论或真实成交量。

可交易演示门店及套餐继续明确为演示资料，补差异化服务流程、时长、包含/不含项目、价格及规则。摄影素材单独逐图核查，不从 POI 数据许可推断网站照片也可复用。

本轮没有找到经核验、能直接整套导入的“中文同城体验门店＋套餐/SKU＋照片＋评论”开放数据包。推荐组合为开放 POI＋来源明确的图片＋有业务差异的演示套餐与分享。

## 实际可获取的小样本

已通过 Overpass GET 请求获取上海范围 `(31.20,121.43,31.26,121.50)` 内的运动/健身等地点，输出为同目录 `shanghai-sports-osm-sample.json`：26 条记录，其中 21 条含 `name`。每条保留原始 OSM ID/来源链接、分类及坐标，包含中文名称。未导入业务数据库，未附带虚构套餐。

首次 POST 返回 HTTP 406，随后 GET 获取成功。查询及 OSM 数据基准时间保存在样本文件，便于复现。无名称或地址缺失的记录须筛选/标注，不能凭空补成真实资料。该样本是有限区域的运动类记录，不代表上海所有行业的覆盖情况。

## 核查证据

网页快照保存在工作区根目录 `.firecrawl/`：

- `overture-places.md`：Places 一手说明、许可、当前分类字段与范围下载方法。
- `osm-copyright.md`：OSM 一手许可说明。
- `fsq-dataset-card.md`：当前下载入口的登录/额外条件及许可。
- `fsq-schema.md`：地点与分类字段。
- `dataset-foursquare.json`、`dataset-local-commerce.json`、`dataset-open-poi.json`、`dataset-overture-search.json`、`dataset-asap-search.json`：检索记录。

外部数据库尚未因此自动替换主演示库；实际导入须在内容补强验收中另列数量、映射、缺失字段和页面抽查证据。
