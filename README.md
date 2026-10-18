# MoviePilot-Plugins

在 MoviePilot 的插件市场设置中添加仓库地址：

```text
https://github.com/narapeka/MoviePilot-Plugins
```

仓库分别提供 `package.v2.json` / `plugins.v2` 与
`package.v3.json` / `plugins.v3`，由 MoviePilot 选择对应版本。
插件直接从源码安装，无需手动替换容器内文件。

## 文件名多级分类

V2 保留原有 1.0 版；V3 提供独立的 3.0.0 版，使用 V3 SDK 和整理事件接口。
V3 适配基线为 MoviePilot 3.1.7。

规则格式、先后顺序、`{年代}`、`{首字母}` 和原分类下追加子目录的行为保持不变：

```text
#CHD|CHDBits#CHDBits/原盘
/downloads##{年代}
/我的接收#UHD|4K#4K/{首字母}
```

路径条件是目标路径的包含匹配，文件名关键字支持不区分大小写的正则表达式。
V3 使用源文件项或源路径取得原始文件名，仅通过事件输出改写整理路径，
不修改主程序传入的原始媒体对象。

设备状态检测（DeviceCheck）已从仓库下架。已安装的实例不会自动卸载，
需要在 MoviePilot 中自行停用或卸载。
