# Fluent 3D Emoji Font

[![自动更新](https://github.com/soizo/fluent-3d-emoji-font/actions/workflows/update.yml/badge.svg)](https://github.com/soizo/fluent-3d-emoji-font/actions/workflows/update.yml)
[字体下载](https://github.com/soizo/fluent-3d-emoji-font/releases/latest) · [更新记录与覆盖率](https://github.com/soizo/fluent-3d-emoji-font/releases) · [构建状态](https://github.com/soizo/fluent-3d-emoji-font/actions)

从微软官方 PNG 自动构建保留原始 3D 视觉效果的彩色字体，并通过 Emojipedia 发现最新候选素材。
**当前公开字体是授权明确的素材子集，不宣称与最新 Microsoft 版本完整一致。**
Emojipedia 新图案的再分发授权尚未确认时，仅记录其目录和缺失情况，不将图片放进公开字体。
这项限制不能通过修改 Release 日期解决。项目不使用第三方预编译字体。

每天 UTC 02:17（北京时间 10:17）检查；GitHub 的计划任务可能延迟，长期无活动的公开仓库可能暂停计划任务。
也可在 Actions → Update fonts → Run workflow 手动执行。失败时不更新 Release，请查看 Actions 日志。
代码、授权明确的素材、许可或 Unicode 覆盖数据发生变化才创建新内容版本；无变化时保留原 Release 日期。仅参考目录变化时更新本次 Actions 报告，不把同一批字体重新发布。

## 下载与安装

在最新 Release 下载 `Fluent3D-fonts.tar.gz`，解压以同时获取许可证和来源清单。
单独下载字体时也应保留压缩包内的许可通知。

| 文件 | 推荐用途 | 限制 |
| --- | --- | --- |
| `Fluent3D-sbix.ttf` | macOS Font Book / CoreText 应用 | 首选；应用的字体选择和系统 Emoji 回退会影响实际显示 |
| `Fluent3D-svg.ttf` | 支持 OpenType-SVG 的应用，如部分 Windows、Linux 应用 | 支持依赖渲染器；嵌入 PNG 的 SVG 也需要应用支持 |
| `Fluent3D-sbix.woff2` | 支持 sbix 的网页渲染器 | WOFF2 只压缩字体，不增加彩色表支持 |
| `Fluent3D-svg.woff2` | 支持 OpenType-SVG 的网页渲染器 | 请在目标浏览器验证，不能作为通用 Chromium 方案 |

macOS：双击 sbix TTF → 安装字体，在支持选择字体的应用中选择 **Fluent 3D Community**。
不要同时安装两个同名 TTF；要切换格式请先移除旧格式并重启目标应用。
不会自动替换 Apple Color Emoji，部分应用强制使用系统 Emoji 字体。官方素材缺少许多国旗和较新的序列，缺失项会回退到系统字体，见 manifest。可先测试：`😀 👩🏻‍💻 🇨🇳 1️⃣ ❤️ 🏴`。
Windows：右键 TTF → 安装；Linux：放入 `~/.local/share/fonts/` 并执行 `fc-cache -f`。
安装成功不代表应用支持该彩色表。已加入 macOS CoreText 原生显示冒烟测试；其他平台尚无实际设备渲染认证。

网页示例（根据目标浏览器选一个格式）：

```css
@font-face {
  font-family: "Fluent 3D Community";
  src: url("./Fluent3D-sbix.woff2") format("woff2");
  font-display: swap;
}
.emoji { font-family: "Fluent 3D Community", "Apple Color Emoji", "Segoe UI Emoji", sans-serif; }
```

保留位图比描摹成 COLR 矢量更忠实；因此目前提供 sbix 和嵌入原 PNG 的 SVG。
未实现 CBDT/CBLC；Android/Chromium 等需要这一格式的组合不保证可用。不把有损矢量化作为兼容性捷径。
原 PNG 在字体内不缩放、不重编码；超过素材原生尺寸显示仍会受位图分辨率限制。

## 本地构建

需要 Python 3.13、Git、网络；建议至少 2 GB 可用空间。命令从仓库根目录运行：

```sh
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
git clone --depth 1 https://github.com/microsoft/fluentui-emoji.git work/upstream
fluent-font --upstream work/upstream --output dist
```

输出目录必须为空，防止混入旧字体。再次构建请使用另一个输出目录。
官方素材使用干净的 checkout；已存在 checkout 需要自行更新到官方最新 main。
版本、源码、Unicode 输入不变时字体字节应一致；完整依赖环境的跨系统一致性尚不保证。
依赖版本固定，Dependabot 检查升级；升级需经过测试。

## 发现、映射与质量

Emojipedia 的公开目录 GraphQL 接口先返回版本和日期，并获取当前完整图案列表；
不猜 CDN 编号，不按英文名称生成 URL，不把 `473` 写死在程序中。接口不是稳定承诺，结构变化就报错。
详见 [调查记录](docs/UPSTREAM.md)。

官方 metadata.json 的 `unicode` / `unicodeSkintones` 决定映射，包括六种 Default/肤色目录；
不从文件名猜肤色插入位置。候选图片名中的完整码点序列与独立 emoji.code 字段交叉校验，处理重复肤色后缀；未知命名和映射冲突阻止构建。
Unicode 官方 `emoji-test.txt` 的最新版本提供覆盖率分母。保留非 RGI 图案并单独报告，
只对 Unicode 明确列出的 VS16 资格形式建立别名；不凭空生成不存在的双肤色或家庭图案。

构建包含 cmap、GSUB `rlig`，按长序列优先处理 ZWJ、肤色、旗帜、键帽及 tag 序列。
每个发布格式都重新打开并用 HarfBuzz 验证所有映射；每个图案核对内嵌 PNG 原字节。
这验证字体结构和映射，不代替 CoreText/DirectWrite 的真实显示测试。
混合源分辨率、空图片、许可变化、下载失败、未知目录、重复冲突或塑形错误均阻止发布。

Release 中：

- `manifest.json`：源 URL、官方 commit、参考版本、源文件/像素 SHA256、Unicode 版本、覆盖率和全部缺失序列。
- `SHA256SUMS`：字体、清单、Unicode 数据和许可证校验和。
- `RELEASE.md`：该内容版本的覆盖情况和未确认授权差距。
- `emoji-test.txt` 和 `licenses/`：重建依据及许可通知。

目录有新版本不代表旧字符图案没改。微软官方每次检查实际 PNG 哈希；
获批的 CDN 图片每次重新取回并核对授权绑定的哈希，同地址改图会要求重新审阅。
未获批 CDN 图案不下载，所以不会声称已验证它们与官方旧图案的视觉一致性。

## 授权与贡献

代码 MIT；微软官方素材另附 Microsoft MIT；Unicode 数据另附 Unicode License。
Emojipedia 目录信息与其图案不是本项目代码许可证的一部分。
[授权边界与新素材批准方式](docs/LICENSING.md) · [微软官方项目](https://github.com/microsoft/fluentui-emoji)

欢迎提交映射修复、渲染器测试结果和可核查的权利方授权证据。
不能确认授权的新图案仅进入候选清单。项目与 Microsoft、Emojipedia 无官方隶属关系。
