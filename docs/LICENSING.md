# 授权边界

代码使用根目录 MIT License。字体名 Fluent 3D Community，不冒充微软官方字体。
微软官方仓库中的 PNG 使用随其发布的 MIT 许可证，保留 Microsoft Corporation 版权声明：
https://github.com/microsoft/fluentui-emoji/blob/main/LICENSE
构建时逐字节核对已经审阅的许可证；变更时停止。Release 同时携带许可证和精确来源 commit。许可文本也嵌入字体的 name ID 13，以便单独下载字体时保留通知。

Emojipedia 是最新素材的参考目录和候选来源。它不是厂商图案的授权人：
https://emojipedia.org/licensing
CDN 可访问、路径在 microsoft-3D-fluent 下、视觉与旧 MIT 图案相似，都不构成新图案可再分发的证据。
默认仅查询目录，不批量下载、提交或发布这些未确认的图片。
网站的访问条款和图案的版权是不同问题。robots.txt 不是版权许可证，也不是长期的抓取许可。
若站点拒绝访问、接口改变或返回错误，任务失败；不绕过验证或访问限制。

额外候选图案必须先在 licenses/ 下保存可核查的许可文本，并在 approvals.json 添加：

```json
{
  "sequence": "1faea",
  "url": "https://em-content.zobj.net/source/.../distorted-face_1faea.png",
  "sha256": "图案原文件 SHA256",
  "license_id": "明确的许可证标识",
  "license_file": "licenses/相应授权文件.txt",
  "license_sha256": "授权文本 SHA256",
  "evidence_url": "权利方授权证据的公开地址",
  "redistribution_and_font_embedding": true
}
```

文件实际为 JSON 数组。不要把这个示例当作授权。许可必须允许图案再分发及字体嵌入；
任何额外通知要求也应保存在许可文件中。每次构建重新下载已批准图案，核对哈希；
同 URL 内容改变会阻止发布，直到审阅新文件。新 CDN 版本需要重新匹配 URL，不能泛化批准整个域名。
若微软官方后续纳入对应新图案，可直接按官方仓库许可随下一次构建自动发布。

Unicode 数据使用 Unicode License v3： https://www.unicode.org/license.txt
Release 附带使用的 emoji-test.txt 和 Unicode 许可证；其列表用于覆盖率计算，不能据此授权厂商图案。
Microsoft、Windows、Fluent 是相应权利方的商标。本项目无官方隶属关系。
