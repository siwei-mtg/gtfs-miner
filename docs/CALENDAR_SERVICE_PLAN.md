# 内部日历微服务 (Calendar Service) 设计方案

## 1. 背景与目标
目前 GTFS Miner 依赖 `Calendrier.xls` 静态文件来获取法国学区假期（Zone A/B/C）和节假日信息。为了实现 Web SaaS 化的自动化处理，需将此逻辑转变为数据库驱动的微服务。

**目标**：
- 消除对本地 Excel 文件的硬依赖。
- 实现与法国官方 API (`api.gouv.fr`) 的自动同步。
- 为 GTFS 处理 Pipeline 提供高可用的日期特征查询。

## 2. 系统架构

### 数据流向
1. **初始化**：系统首次启动时从 `Calendrier.xls` 刷入基础历史数据。
2. **同步 (Sync Agent)**：定时任务（每周）从官方 API 获取最新假期排期。
3. **查询 (Provider)**：算法在计算服务频率时，根据日期范围从数据库提取 `Type_Jour_Vacances_*` 特征。

## 3. 数据库设计 (Schema)

### `calendar_dates` 表
| 字段 | 类型 | 索引 | 说明 |
| :--- | :--- | :--- | :--- |
| `date_gtfs` | String(8) | PK | 格式 `YYYYMMDD` |
| `is_holiday` | Boolean | - | 是否为法定节假日 |
| `holiday_name` | String | - | 节日名称（如 Noël） |
| `zone_a_holiday` | Boolean | - | 区域 A 是否在放假 |
| `zone_b_holiday` | Boolean | - | 区域 B 是否在放假 |
| `zone_c_holiday` | Boolean | - | 区域 C 是否在放假 |
| `updated_at` | DateTime | - | 数据最后同步时间 |

## 4. 同步策略 (API Integration)

### 数据源
- **假期数据**：`https://calendrier.api.gouv.fr/vacances/scolaires/zones.json`
- **节假日数据**：`https://calendrier.api.gouv.fr/jours-feries/metropole.json`

### 逻辑逻辑
- 采用 **Upsert** 模式：如果日期已存在则更新，不存在则插入。
- 覆盖策略：官方 API 数据具有最高优先级。

## 5. 算法集成方式
在 `backend/app/services/worker.py` 中：
1. 算法启动前检查数据库中是否存在该 GTFS 覆盖范围的日历数据。
2. 缺失时触发一次性强制同步。
3. 将查询结果注入 `gtfs_core` 的 `Dates` DataFrame。
