# 《Fighting Fantasy Classics》BLOODBONES 简体中文汉化

> **v0.1 测试版** —— 目前只汉化了免费书 **Bloodbones（血骨）**。其他书（DLC）仍是英文，后续有空再继续。

把 Steam 版《战斗幻想经典》(Fighting Fantasy Classics) 里这本免费游戏书做成全简体中文：一个 exe 双击即装，自动定位 Steam 目录，自带备份，随时一键还原。

---

## 汉化了什么

| 项目 | 覆盖量 |
|---|---|
| 正文 | 639 段全译，2,563 个文本块（约 6.5 万字符 / 5.7 万汉字） |
| 选项 / 战斗按钮 | 全部（`选 12`、`战斗`、`逃跑` 等） |
| 掷骰 / 谜题 / 商店 | 全译 |
| UI 文案 | 126 条 |
| 地图地名 | 106 条 |
| 字形 | 新增 130 个生僻字（骷髅、骰子、鹦鹉、蜥蜴…），自建 4096×4096 SDF 图集，共 4,082 字形，**无方块** |
| 术语 | `STAMINA→耐力`、`SKILL→技巧`、`LUCK→运气`、`Gold→金币`、`Attack Strength→攻击强度` |
| 道具 / 怪物名 | **保留英文原词**（会被 `has Bone Sword` 之类的条件当键，翻了会破坏逻辑） |

译文按 90 年代游戏书译本的路子写：第二人称、短句、有画面感、不加注释、中文全角标点。

---

## 下载安装

1. 到 [Releases](../../releases) 下载 `FFC_Bloodbones_ZH_v0.1.zip`（约 38 MB）
2. **完全退出游戏**（Steam 里显示「停止」才算退了）
3. 双击 `FFC_Bloodbones_ZH.exe`
4. 它会自己找 Steam 游戏目录；找不到时让你粘一次路径
5. 看到「安装完成！汉化字体 4/4，字形 4082；书 639 段」就成功了 → 从 Steam 正常启动

安装器只改两个文件，且改前都会备份：

```
<游戏目录>\Fighting Fantasy Classics_Data\sharedassets0.assets     ← 字体资产（6.2 MB → 22.7 MB）
%USERPROFILE%\AppData\LocalLow\Tin Man Games\Fighting Fantasy Classics\
    ffhub.bloodbones\ffhub.bloodbones_book                          ← 整本书的中文数据
```

## 还原英文原版

再双击一次 exe，选 `2 = 还原为英文原版`；或者命令行：

```bat
FFC_Bloodbones_ZH.exe --restore
```

原始文件备份在 `%USERPROFILE%\AppData\LocalLow\Tin Man Games\Fighting Fantasy Classics\_hanhua_backup\`。

只想看看会改什么、不动文件：`FFC_Bloodbones_ZH.exe --check`

---

## 常见问题

**重装游戏 / 点了 Steam「验证游戏文件完整性」之后，进游戏全是方块字？**
正常。汉化改的是游戏安装目录里的字体资产，重装或验证完整性会把它换回原版（字库没有汉字），而中文书文件在 `AppData\LocalLow` 里、不会被删 —— 于是「中文书 + 英文字体」= 全方块。退出游戏，重跑一次安装器即可。

**杀软 / SmartScreen 报毒？**
安装器是 PyInstaller 打包的未签名程序，常见误报。它不联网、不碰存档，源码就在 [`tools/patcher.py`](tools/patcher.py) 里可以审。不放心就先跑 `--check`。

**装完还是英文？**
确认安装器最后显示「汉化字体 4/4」，然后**重启游戏**（字体是启动时加载的）。

**其他书还是英文？**
是。v0.1 只做了 Bloodbones。字体是全局的，其他书的英文会改用 Noto Sans SC 显示，能正常阅读，只是字形跟原版 Alegreya 略有差别。

**存档 / 成就受影响吗？**
不受影响，补丁不碰存档。

---

## 技术说明

游戏用 Unity + TextMeshPro 1.0.56，字体是 SDF 位图图集，书文件是自定义 XOR 混淆的 JSON。

- 自建 4096×4096 Alpha8 中文 SDF 图集：保留原 3,952 个拉丁/符号字形，用 Noto Sans SC 59pt 补渲到 4,082 个
- 四套字体资产（`Alegreya-Regular / Bold / Bold_outline / Italic`）全部指向同一中文图集 —— 因为 `Page.SetStyle` 发的 TMP 富文本 `<i>/<b>` 会切到独立字体资产，只换 Regular 会让斜体处出现方块和错位间距
- 字形表按 `id` 升序重排（TMP 用二分查找，乱序会取到错字形）
- 文本编码只变换 UTF-16 低字节，高字节原样保留

安装器源码：[`tools/patcher.py`](tools/patcher.py)（Python 3 + UnityPy）

---

## 声明

- 同人汉化，仅供已购买正版游戏的玩家学习交流，**请勿用于商业用途**；补丁不含游戏本体。
- 《Fighting Fantasy》系列版权归 Steve Jackson、Ian Livingstone 与 Tin Man Games 所有。
- 中文字形图集由 **Noto Sans SC**（SIL Open Font License 1.1）生成，可自由分发。
- 因为是基于免费 DLC 的非官方补丁，遇到游戏更新导致失效请提 issue。

## 更新日志

- **v0.1**（测试版）：Bloodbones 全本汉化 + 中文 SDF 字体 + 一键安装/还原
