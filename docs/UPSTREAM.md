# 上游调查记录（2026-10-17）

## Emojipedia

参考页面：https://emojipedia.org/microsoft-3D-fluent
最新日期条目：Windows 11 26H2，slug `windows-11-26h2-august-2026-update`，目录日期 2026-08-27。
查询当日共取得 4,345 个去重序列（包含 Unicode 非 RGI 扩展，不能把它等同于 Unicode 标准 Emoji 总数）。
样例：https://em-content.zobj.net/source/microsoft-3D-fluent/473/distorted-face_1faea.png

`473` 是这批目录引用的素材集数字标识；没有查到可保证长期有效的编号语义规范。
**不是 Unicode 473，也不能假定最大编号就是最新版本。**
本次所有返回的路径引用 473。应以厂商目录中发布日期最新的条目及其实际图片引用为准。
版本名称、发布日期和素材集 ID 分开保存。不同版本可能共享或混用资产路径，因此实现保存 ID 集合。

文件名是 `<可读 slug>_<码点用连字符连接>.png`。示例：

- `distorted-face_1faea.png` → U+1FAEA。
- `technologist-light-skin-tone_1f9d1-1f3fb-200d-1f4bb.png` → 🧑🏻‍💻。

真正的键是码点序列，不能仅凭英文 slug 对应 Unicode。VS16、ZWJ、肤色、区域指示符和 tag 码点不得随意移除。
实现对路径前缀、扩展名、码点有效性和序列冲突进行检查。

前端公开 JS 中的目录查询：`POST https://emojipedia.org/api/graphql`，
`vendorHistoric_v1(slug:...)` 返回版本日期；`vendorHistoricEmoji_v1(slug:..., version:...)`
返回按类别分组的 `items.images`，含 slug、image.source 和 status。
先读版本，再显式请求最新版本完整列表，不仅抓 NEW 分类，因旧图案也会修改。
使用页面已经公开调用的接口，不使用登录态、私有凭据或绕过访问控制。
每天查询目录并按下文方式校验码点；不下载未批准图片。接口结构变化会停止，不使用旧清单假装最新。

此接口没有稳定 API 承诺；也未找到稳定的完整离线目录授权承诺。
授权页 https://emojipedia.org/licensing 明确其不负责为厂商图案授予许可。
robots https://emojipedia.org/robots.txt 是访问规则而非素材许可，未来可能改变。

## Microsoft 官方

https://github.com/microsoft/fluentui-emoji
调查时 HEAD：`1ffb34c752ecf5d402f04cfb4b392c77f57c54bc`。
1,595 个 metadata.json，3,145 张 3D PNG；310 个图案有六种肤色目录。
metadata 中 `unicodeSkintones` 已给出完整序列，不需要猜测肤色修饰符位置。
官方仓库包含 Microsoft MIT 许可证。项目逐次核对该文本并附在 Release 内。
官方授权不能自动延伸至 Emojipedia 上尚未出现在该仓库的新版本图案。

## 字体实现依据

- sbix 规范：https://learn.microsoft.com/en-us/typography/opentype/spec/sbix
- fontTools：https://fonttools.readthedocs.io/en/latest/ttLib/index.html
- Unicode Emoji 测试数据：https://unicode.org/Public/emoji/latest/emoji-test.txt
- OpenType SVG：https://learn.microsoft.com/en-us/typography/opentype/spec/svg

sbix 直接嵌入 PNG，可保持源文件原始字节。OpenType-SVG 内嵌同一 PNG，
提供另一种应用相关的兼容选择。WOFF2 不改变底层彩色表的兼容范围。
不能仅凭表存在或 HarfBuzz 通过便声称已验证所有操作系统的视觉渲染。

### 文件名陷阱与独立校验

实测部分肤色 PNG 路径为 `waving-hand_light-skin-tone_1f44b-1f3fb_1f3fb.png`。
只读最后一段会误映射成独立 U+1F3FB。实现批量请求 `emoji_v1(slug:...) { code }`，
独立校验全部候选的完整序列，再接收目录中的真实 URL，不自行重写文件名。
一次目录请求加每 100 个 slug 一次只读查询（当前约 45 次/天），有小批次间隔。
公开接口故障或码点不一致即停止发布。历史条目与当前目录分开记录，
先用 `version:null` 发现版本，再按最新日期的 slug 显式获取该版本完整列表；若期间最新版本发生变化，停止并要求重新观测。
