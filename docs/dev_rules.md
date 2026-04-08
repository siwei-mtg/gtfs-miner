# 开发规范 - 面向代码集成 (最优版)

:::
目的：通过高度模块化与明确的代码契约，减少代码串联时的二次开发工作量。
:::

## 规范 1：模块化与层级解耦 (Layering)

**核心原则**：将“核心计算逻辑”与“表现/环境层”彻底分离。
1.  **按功能划分模块文件**：每个独立功能必须放在单独的 .py 文件中。
2.  **QGIS 依赖隔离**：算法核心模块（如 `gtfs_norm.py`）**不得导入** `qgis.core`。所有 QGIS 相关的逻辑（图层加载、消息日志）应集中在 `gtfs_miner.py` 或专门的 `adapter` 模块中。
3.  **模块大小控制**：单个功能模块建议不超过 **600 行**。

## 规范 2：函数契约与类型注解

1.  **类型注解强制使用**：所有公开函数必须使用 Python 类型注解（`typing`）。
2.  **Data Schema 说明**：对于处理 Pandas DataFrame 的函数，在 docstring 中必须明确输入输出所需的**核心列名**。
    ```python
    def process_stops(df: pd.DataFrame) -> pd.DataFrame:
        """
        Input Schema: [stop_id, stop_lat, stop_lon]
        Output Schema: [stop_id, normalized_lat]
        """
    ```

## 规范 3：模块内部结构标准

每个模块文件必须包含：
1.  **模块文档字符串**：功能说明、流程图（复杂逻辑必选）。
2.  **显式导入**：严禁 `from module import *`，统一采用明文导入。
3.  **路径标准化**：严禁字符串拼接路径，**强制使用 `pathlib.Path`**。
4.  **自测块**：必须包含 `if __name__ == '__main__':` 用于快速验证。

## 规范 4：复杂流程的说明

复杂逻辑必须包含 ASCII 流程图：
```plaintext
"""
处理流程：
输入 GTFS 目录 -> [gtfs_norm 模块] -> 规范化 DF 字典 
               -> [gtfs_generator 模块] -> 计算 ITI 
               -> [gtfs_export 模块] -> 输出 CSV/QGIS 图层
"""
```

## 附加规范：代码审查检查表

| 检查项 | 是/否 | 备注 |
| --- | --- | --- |
| 模块是否单一功能且高度解耦 | | |
| 算法层是否独立于 QGIS (无 qgis.core 导入) | | |
| 函数是否包含类型注解及核心 Schema 说明 | | |
| 路径处理是否使用 pathlib | | |
| 是否包含功能性自测用例 | | |