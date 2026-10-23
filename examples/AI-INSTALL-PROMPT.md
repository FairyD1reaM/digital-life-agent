# 复制这段给任何 AI

把下面整段（连同你的仓库路径）发给一个 AI，它就能帮你装好。

````text
我在用 DeepSeek Harness (dsh)。请帮我把这个角色预设装好。

项目路径：<这个仓库的绝对路径>

请按顺序做，不要跳步：

1. 【必须先问】问我：「你的角色叫什么名字？」
   再问：「要不要一个小名？不给就用『小＋全名』。」
   在我回答之前，不要生成任何文件。
   绝对不要自己编名字，也不要用仓库文档、注释、示例里出现过的名字——
   这个角色卡的通篇机制（自称规则、被叫全名时的反应、小名档）都挂在名字上，
   名字是占位符的话预设就是坏的。

2. 用我给的答案运行（先 cd 到项目根）：
   cd "<这个仓库的绝对路径>"
   python generate.py --name "<我给的>" --short "<我给的>"
   （Windows 下如果 python 不通，试 py -3。）

3. 确认 out/cordis.patch.yml 里没有残留的 {{ROLE_NAME}} / {{ROLE_SHORT}} / {{ROLE_NAME_YAML}}，
   并且 persona 正文长度在 2000 字符以上。有问题就报告，别硬装。

4. 用 plugin_manager 工具安装：action = install_bundle，
   target = out 目录的绝对路径。

5. 验证：list_plugins 里应出现生成器打印的那行 include:…（照抄它的输出），
   且 fiberPhase 为 active。
   如果 activation 失败，把诊断原文贴给我，不要自行改动插件名去"修"。

6. 告诉我怎么启用（新开会话后在预设选择器里选），以及怎么改默认预设。

装之前先告诉我你打算动哪些文件。
````

---

## 如果你是在 dsh 里对 AI 说这句话

那更简单，上面的提示词照样能用。dsh 里的 AI 有 `plugin_manager` 工具，能直接装。

## 如果你只想拿角色卡纯文本

跟 AI 说：

```text
帮我渲染这个角色卡，只要 persona 的纯文本，不要 YAML 外壳。
名字用「<你的名字>」，小名用「<你的小名>」。
命令：python generate.py --name "<你的名字>" --short "<你的小名>" --print
```
