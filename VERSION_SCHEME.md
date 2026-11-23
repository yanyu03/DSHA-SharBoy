# 版本方案 / Release and working tree

- **最新 GitHub Release：V1.1**（2026-11-03 已发布），参见 [Release V1.1](https://github.com/yanyu03/DSHA-SharBoy/releases/tag/V1.1)。该 Release 对应独立历史标签，不自动包含后续 `main` 变更。
- **主分支 `main`**：持续迭代与公共试用准备，2026-11 已合入 MCP 注解修复、契约测试及后续安全安装文档。**不要把这些后续修复称为 V1.1 标签已包含**。
- **遗留机器字段**：根目录 `VERSION` 仍为 `1.0.0`，与已发布 V1.1 的展示版本尚未统一。暂不改写已发布标签或旧资产；在下一个正式版本发行前校正机器版本，并建立新标签/发行说明。
- **开放协议版本**：`v1.2.0-std` 是接口规范标识，与 GitHub Release 或 `VERSION` 完全独立。

V1.0 的自定义源码 ZIP/TAR、哈希清单属于 V1.0 历史资产；当前 V1.1 Release 页面未提供类似的自定义上传资产，可以通过 GitHub 自动源码归档取得标签对应的代码。所有安装说明须标注使用的是 `main` 还是发行标签。

历史实验线 `2.x` 和旧标签保留，不能单靠版本号大小推断发行顺序。发布测试证据应带有 commit SHA、平台、具体命令和 PASS/FAIL/SKIP；旧测试不能自动证明新提交可运行。

**下次发行前**：更新 `VERSION`、CHANGELOG、安装器、README 和标签一致性；打包源码/校验值时从最终 tag commit 重新计算；不挪动旧标签、不复用旧资产。
