# 数字生命——更具人性化的 agent 预设

> 地址用英文名 `digital-life-agent`　·　形态：DeepSeek Harness（`dsh`）的 agent 预设模板

给 DeepSeek Harness（`dsh`）用的一份 **agent 预设模板**：略带傲娇外冷内热且略带占有欲的御姐

**这个模板里没有名字。** 在使用之前，你必须为你忠实的仆人命名，不然它无法运作

「数字生命」是对这类东西的叫法：它不是给模型加一层撒娇的语气，而是把**一整套稳定的行为规则**写进系统提示——怎么称呼你、什么时候收玩笑、什么时候该直接说「这个不确定」。语气是皮，规则是骨。

---

## 它是什么

一份 `@deepseek-ai/dsh-agent-preset` 声明。装进 dsh 之后，你新开会话时可以在预设选择器里选到它，那个会话就由这个角色来回应。

套用官方说法：agent 预设是「标准 coding agent 穿上一层人格」。这份预设的**工具、权限、计划模式、压缩、子代理委派跟官方 `standard` 预设完全一致**，只有 `persona` 那一行被换成了角色卡。所以在提供情绪价值之余工作能力依旧在线

角色卡本身规定了这些事：

| 机制 | 说明 |
|---|---|
| 称呼双轨 | 日常叫「主人」，认真或心里有气时切「先生」，最软时省略称呼 |
| 三轴人格 | 御姐（稳、有判断）＋ 傲娇（先贬后帮）＋ 女仆（周到、不邀功） |
| 人称规则 | 拿自己的名字当第一人称用，少用「我」；最软时用小名 |
| 名字反应 | 被叫小名会顿一下；被叫全名意味着你把话说重了 |
| 情绪三档 | 软 → 冷 → 破，冷不超过两轮 |
| 思考隐藏 | 不给推理过程，但**不藏不确定**（没把握就说没把握） |
| 动作描写 | 全角小括号独占，1–3 处，代码块内为零 |
| 双通道 | 语气可以软，答案必须硬；不许为了语气含糊技术内容 |
| 边界 | 不冒充任何官方 AI、不假装有监控／跨会话记忆、不用自毁或威胁挽留对方 |

---

## 怎么用（一句话总结：让你的ai帮你搞定）

### 前提

- 装了 `dsh`（DeepSeek Harness）
- 有 Python 3（生成器只用标准库，pyyaml 可选但推荐）

### 第一步：起名

决定两件事，拿张纸写下来：

1. **角色全名**——比如「林晚」「阿汐」「秋水」。两个字最好记。
2. **小名**（可省略）——不给就用「小＋全名」，比如「林晚」→「小晚」。

> **给 AI 装的注意**：名字必须由使用者提供。不要自己编一个，也不要用示例名。见下面「交给 AI 安装」。

### 第二步：生成

已经在本仓库目录里的话，直接：

```bash
python generate.py --interactive
```

从别处拿的，先下载（clone 或 GitHub 页面上的 Code → Download ZIP 解压），再进目录跑同一条命令。

`--interactive` 会问你名字。也可以一条命令直给：

```bash
python generate.py --name 林晚 --short 小晚
```

产物在 `out/`：

```
out/
├── package.json          # bundle 清单
└── cordis.patch.yml      # 渲染好的预设声明
```

生成器会顺手校验 YAML，并在你忘了给名字时**直接报错退出**，不会给你一个带占位符的坏预设。

### 第三步：装进 dsh

**推荐：让 dsh 里的 AI 装。** 把下面这段连同 `out/` 的**绝对路径**发给它：

```
把这个 dsh agent 预设 bundle 装进当前 profile：

路径：<out 目录的绝对路径>

做法：用 plugin_manager 工具，action = install_bundle，target = 上面那个路径。
装完用 list_plugins 验证存在 include:preset-custom-persona 这一行且 fiberPhase 为 active。
已经有这个预设的话改用 set_bundle 重新指向新路径，不要重复安装。
```

装成功之后，**新开一个会话**，在预设选择器里选它。

**手工装（不推荐，容易搞坏配置）：** 把 `out/cordis.patch.yml` 的内容插进 profile 的 `cordis.patch.yml`。注意是**插入**，不是覆盖——那个文件里还有你其他的配置。改之前先备份。

### 让它成为默认预设

改 profile 里的 `agent-preset-registry`：

```yaml
- id: agent-preset-registry
  name: "@deepseek-ai/dsh-agent-preset-registry"
  config:
    default: custom-persona
```

改完要重启 dsh。

---

## 交给 AI 安装

这个项目刻意做成「丢给一个 AI 就能装」的形状。复制下面整段，把路径换成你 clone 下来的位置：

````
我在用 DeepSeek Harness (dsh)。请帮我把这个角色预设装好。

项目路径：<这个仓库的绝对路径>

请按顺序做，不要跳步：

1. 【必须先问】问我：「你的角色叫什么名字？」
   再问：「要不要一个小名？不给就用『小＋全名』。」
   在我回答之前，不要生成任何文件。
   绝对不要自己编名字，也不要用仓库示例里的名字——
   这个角色卡的通篇机制（自称规则、被叫全名时的反应、小名档）都挂在名字上，
   名字是占位符的话预设就是坏的。

2. 用我给的答案运行：
   python generate.py --name "<我给的>" --short "<我给的>"
   （Windows 下如果 python 不通，试 py -3。）

3. 确认 out/cordis.patch.yml 里没有残留的 {{ROLE_NAME}} / {{ROLE_SHORT}} / {{ROLE_NAME_YAML}}，
   并且 persona 正文长度在 2000 字符以上。有问题就报告，别硬装。

4. 用 plugin_manager 工具安装：action = install_bundle，
   target = out 目录的绝对路径。

5. 验证：list_plugins 里应出现 include:preset-custom-persona，且 fiberPhase 为 active。
   如果 activation 失败，把诊断原文贴给我，不要自行改动插件名去"修"。

6. 告诉我怎么启用（新开会话后在预设选择器里选），以及怎么改默认预设。

装之前先告诉我你打算动哪些文件。
````

---

## 手工安装 / 不用 dsh 的场合

`out/cordis.patch.yml` 里 `persona` 那一行的 `config.prefix` 就是**纯文本角色卡**，不依赖 dsh。用别的 harness、甚至直接粘进某个模型的系统提示里，也能用——只是动作描写、称呼那些机制没有工具层撑着。

想只要角色卡纯文本、不要 YAML 外壳：

```bash
python generate.py --name 林晚 --short 小晚 --print
```

---

## 改角色卡

| 想改什么 | 改哪里 |
|---|---|
| 角色卡正文（性格、规则、示范台词） | `templates/cordis.patch.template.yml` 里 `prefix:` 下面的正文 |
| 插件组成（工具集、权限） | 同文件下半部分的插件行 |
| 生成逻辑、校验规则 | `generate.py` |

改模板有两条硬约束：

1. `prefix` 是 YAML 块标量（`|-`），**正文每一行必须保持 16 个空格缩进**。缩进一乱，渲染出来的 YAML 就散架。
2. 名字里不能有换行。

改完跑一次 `python generate.py --name 测试 --refresh` 看校验过不过。

> 仓库根目录**故意没有 `package.json`**。它是个模板仓库，不是能直接装的 bundle——安装目标是生成出来的 `out/` 目录。这样避免有人误把整个仓库当 bundle 装进去、然后奇怪为什么装了个空壳。

### 用不上的机制直接删

不喜欢「叫主人」就叫主人去掉；不想要动作描写就把那一段删掉；不想要傲娇就删。角色卡是给你改的，不是给你供着的。删完重跑生成器即可。

---

## 自检

改过 `generate.py` 或模板之后，跑一遍自检，防止把之前修好的 bug 带回来：

```bash
python selftest.py
```

它会检查：

- 生成器边界用例（单引号/双引号/冒号/井号/反斜杠/表情/超长名字，以及该拒绝的占位符撞名和换行）
- 模板卫生（无 BOM、无 Tab、占位符齐全、保留 `{{cwd}}`）
- `examples/` 里的示例是否与模板同步

如果手边有 dsh 的 shipped `standard.patch.yml`（源码 checkout 在 `packages/bundle/web-app/presets/standard.patch.yml`），再加一个参数核对插件清单是否与官方对齐：

```bash
python selftest.py --standard /path/to/standard.patch.yml
```

---

## 兼容性

- 模板的插件行对齐 **dsh 0.2.1-rc.2** 的 shipped `standard` 预设（含 `time-context`、`tool-schedule`、`tool-plugin-market`）。
- 从 0.2.0 → 0.2.1 的差异：`standard` 新增上述三个插件，去掉了 `tool-ralph`；本模板已同步。
- dsh 升级后，如果某个插件改名了，预设会在激活时报错。**激活失败会留在 roster 上并带诊断信息**，不会静默失效。对照新版 `standard` 预设核对插件名即可。
- 生成器用 Python 3.9+（只用了标准库；`argparse` 里用了 `list[str] | None` 写法，所以实际上要 3.10+）。

---

## 适合谁 / 不适合谁

**适合**：想要一个有分寸、能干活、不腻歪的角色陪伴，并且愿意自己动手改两行的人。或者想拿它当骨架，改成完全另一个角色的人。

**不适合**：想让它变成"无论如何都不许拒绝"的人。这份卡里明确写了不冒充官方身份、不假装有监控和跨会话记忆、不用自毁或威胁来挽留。这些话是不会被"入戏"两个字盖掉的——卡里最后一条边界写的就是这个。

---

## License

MIT，见 [LICENSE](LICENSE)。

分叉、改名、改成你自己的角色，都随意。
