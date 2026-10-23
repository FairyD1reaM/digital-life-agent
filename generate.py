#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把一个「空名字」的角色卡模板渲染成可直接安装的 dsh agent 预设。

用法：
    python generate.py --name 名字 [--short 小名] [--out 输出目录] [--refresh]
    python generate.py --interactive

设计约束（很重要，改这个脚本时别破坏）：
  * --name 没有缺省值。不给名字就报错退出，绝不自动编一个名字。
  * 之所以这么硬，是因为角色卡的通篇机制（自称规则、被叫全名时的反应、
    昵称档）都挂在名字上。名字一旦是占位符，整个预设就是坏的。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "templates" / "cordis.patch.template.yml"
DEFAULT_OUT = HERE / "out"

# 模板里出现过的占位符。新增占位符时同步加到这张表。
# {{ROLE_NAME_YAML}} 只出现在 name: 这一行，替换成"已正确加引号"的 YAML 标量，
# 这样名字里带单引号（O'Brien）或双引号都不会把 YAML 写坏。
# {{PRESET_ROW_ID}} / {{PRESET_ID}} 是声明行 id 与 config.id，按角色名派生，
# 保证不同角色生成不同预设，不会互相顶掉。
TOKENS = (
    "{{ROLE_NAME}}",
    "{{ROLE_SHORT}}",
    "{{ROLE_NAME_YAML}}",
    "{{PRESET_ROW_ID}}",
    "{{PRESET_ID}}",
)


def fail(msg: str) -> "NoReturn":  # type: ignore[valid-type]
    print(f"错误：{msg}", file=sys.stderr)
    raise SystemExit(2)


def normalize(raw: str) -> str:
    """去掉首尾空白与包裹引号；名字里不允许换行（会破坏 YAML 块标量）。"""
    s = raw.strip().strip('"').strip("'").strip()
    if "\n" in s or "\r" in s:
        fail("名字里不能有换行。")
    return s


def name_slug(name: str) -> str:
    """角色名 → 稳定的 ASCII slug。不做拼音转换（会引入依赖），
    非 ASCII 名字回退到名字哈希的前 8 位——同一个名字永远得到同一个身份。
    截断后补 4 位哈希，避免长名字在 20 字符处相撞。"""
    ascii_part = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", ascii_part.lower()).strip("-")
    if s:
        return f"{s[:20]}-{hashlib.sha256(name.encode('utf-8')).hexdigest()[:4]}"
    return "n" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]


def read_name_interactive() -> tuple[str, str]:
    """交互式取名字。空输入一律重新问，不提供缺省。"""
    print("在为你的角色生成预设之前，必须先命名。")
    print("（这个文件名会贯穿角色卡：自称规则、被叫全名时的反应、昵称档都挂在它上面。）\n")
    while True:
        try:
            raw = input("你的角色叫什么名字？> ")
        except EOFError:
            fail("检测到非交互输入（stdin 已结束）。请改用：--name <名字> [--short <小名>]")
        name = normalize(raw)
        if name:
            break
        print("不能为空。请给它起一个名字——随便起一个也行，之后还能改。\n")

    print(f"\n角色可以有一个更亲昵的小名（比如「{name}」→「小{name}」）。")
    try:
        raw_short = input(f"小名（留空则用「小{name}」）> ")
    except EOFError:
        print()          # 管道场景没有回显，补一个换行
        raw_short = ""   # 有默认值，降级而不是失败
    short = normalize(raw_short)
    if not short:
        short = f"小{name}"
        print(f"（未填，采用「{short}」）")
    return name, short


def yaml_single_quoted(value: str) -> str:
    """把任意文本渲染成 YAML 单引号标量（内部单引号按 YAML 规则翻倍转义）。"""
    return "'" + value.replace("'", "''") + "'"


def render(name: str, short: str, preset_id_override: str | None = None) -> tuple[str, str, str, str]:
    # utf-8-sig：模板若被 Windows 编辑器存成带 BOM 的 UTF-8，BOM 会成为第一个字符
    # （'\ufeff'），出现在产物开头，导致 YAML 解析器把首行当成乱码。统一剥掉再渲染。
    text = TEMPLATE.read_text(encoding="utf-8-sig")
    for tok in TOKENS:
        if tok not in text:
            fail(f"模板缺少占位符 {tok}，模板文件可能被改坏了。")
    # 名字本身不能是占位符文本，否则替换后会被误判成"还有残留"。
    for tok in TOKENS:
        if tok in name or tok in short:
            fail(f"名字里不能包含占位符文本 {tok}，请换一个名字。")

    slug = name_slug(name)
    if preset_id_override:
        raw = preset_id_override.strip()
        if not re.fullmatch(r"[a-z0-9-]+", raw):
            fail(f"--preset-id 只能用小写字母、数字和连字符：{preset_id_override!r}")
        row_id = raw if raw.startswith("preset-") else f"preset-{raw}"
        preset_id = raw[len("preset-"):] if raw.startswith("preset-") else raw
        if not preset_id:
            fail("--preset-id 不能是空的 preset id。")
    else:
        row_id = f"preset-persona-{slug}"
        preset_id = f"custom-persona-{slug}"

    # 先替换身份占位符，再替换名字；两者互不包含，顺序只为可读。
    text = text.replace("{{PRESET_ROW_ID}}", row_id).replace("{{PRESET_ID}}", preset_id)
    # 先替换 YAML 专用占位符：它会被渲染成带引号的标量，避免名字里的引号写坏 YAML。
    text = text.replace("{{ROLE_NAME_YAML}}", yaml_single_quoted(name))
    text = text.replace("{{ROLE_NAME}}", name).replace("{{ROLE_SHORT}}", short)
    leftover = [t for t in TOKENS if t in text]
    if leftover:
        fail(f"渲染后仍残留占位符：{leftover}")
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    return text, row_id, preset_id, slug


def validate_yaml(text: str, expect_row_id: str) -> None:
    """尽量用真 YAML 解析器校验；没有 pyyaml 就退化成结构检查。"""
    try:
        import yaml  # type: ignore
    except Exception:
        _validate_loose(text)
        return
    try:
        data = yaml.safe_load(text)
        row = data[0]["insert"][0]
    except Exception as exc:  # noqa: BLE001
        fail(f"渲染结果不是合法 YAML：{exc}")
    if row["id"] != expect_row_id:
        fail(f"声明行 id 不对：{row.get('id')!r}（期望 {expect_row_id!r}）")
    plugins = row["config"]["plugins"]
    if not plugins or plugins[0]["id"] != "persona":
        fail("persona 必须是第一个插件行。")
    prefix = plugins[0]["config"]["prefix"]
    if len(prefix) < 1500:
        fail(f"persona 正文只有 {len(prefix)} 字符，疑似被截断。")
    print(f"  YAML 校验通过（persona 正文 {len(prefix)} 字符）")


def _validate_loose(text: str) -> None:
    if "\t" in text:
        fail("渲染结果含 Tab 字符，YAML 不允许用 Tab 缩进。")
    # 注意：模板/产物开头是若干行 # 注释，`- insert:` 在其后。所以只能查"包含"，
    # 不能用 startswith —— 之前写成 startswith 时，任何没装 pyyaml 的环境都会误报。
    if "- insert:" not in text:
        fail(
            "渲染结果里找不到 `- insert:`。\n"
            f"  实际开头是：{text[:40]!r}\n"
            "  模板文件可能被截断，或首行被编辑器/下载工具改动了。"
        )
    # 只查本项目自己的占位符。产物里的 {{cwd}} 是 dsh 的模板变量，必须原样保留，
    # 不能被当成"未替换"。
    if any(tok in text for tok in TOKENS):
        fail("渲染结果里还有未替换的花括号占位符。")
    print("  YAML 校验：pyyaml 不可用，已退化为结构检查（建议 pip install pyyaml 做完整校验）")


def guard_out_dir(out: Path) -> None:
    """--out 护栏：绝不把项目目录、其上级目录、用户主目录、盘根当成输出目录。"""
    if out == HERE or out in HERE.parents:
        fail(f"--out 不能是项目目录或其上级目录：{out}")
    if out == Path.home():
        fail(f"--out 不能是用户主目录：{out}")
    if out.parent == out:  # 盘根，如 C:\ 或 /
        fail(f"--out 不能是磁盘根目录：{out}")
    if out.is_dir():
        markers = [m for m in ("generate.py", "selftest.py", "templates", ".git") if (out / m).exists()]
        if markers:
            fail(
                f"--out 指向的目录里有项目文件（{', '.join(markers)}），拒绝写入：\n"
                f"  {out}\n"
                "  请换一个空目录，例如 --out out。"
            )


def write_bundle(out: Path, rendered: str, package_name: str) -> Path:
    patch_path = out / "cordis.patch.yml"
    patch_path.write_text(rendered, encoding="utf-8", newline="\n")

    pkg = {
        "name": package_name,
        "version": "1.0.0",
        "private": True,
        "type": "module",
        "dsh": {"bundle": {"patch": "./cordis.patch.yml"}},
    }
    (out / "package.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return patch_path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="把空名字角色卡模板渲染成可安装的 dsh agent 预设。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--name", help="角色名（必填，没有缺省值）")
    p.add_argument("--short", help="更亲昵的小名（省略则用「小<名字>」）")
    p.add_argument(
        "--preset-id",
        dest="preset_id",
        help="可选：覆盖 preset id（默认按角色名派生）。给 custom-persona 可复现旧行为。",
    )
    p.add_argument("--out", help=f"输出目录（默认 {DEFAULT_OUT}）")
    p.add_argument("--refresh", action="store_true", help="输出目录已存在时先清空")
    p.add_argument("--interactive", action="store_true", help="交互式取名字")
    p.add_argument("--print", dest="print_only", action="store_true", help="只打印渲染结果，不写文件")
    return p


def _force_utf8_stdio() -> None:
    """Windows 控制台默认 cp936 时，打印 emoji 会抛 UnicodeEncodeError。
    统一切到 UTF-8 + replace，保证不会崩在写文件之前。"""
    for stream in (getattr(sys, "stdout", None), getattr(sys, "stderr", None)):
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8_stdio()
    args = build_parser().parse_args(argv)

    if not TEMPLATE.exists():
        fail(f"找不到模板 {TEMPLATE}")

    if args.interactive:
        name, short = read_name_interactive()
    else:
        if not args.name:
            fail(
                "必须提供角色名：--name <名字>\n"
                "  这个项目刻意不设缺省名字，因为名字是角色卡机制的一部分。\n"
                "  如果你是在按 README 里的提示词安装：请先问用户「你的角色叫什么名字」。"
            )
        name = normalize(args.name)
        if not name:
            fail("--name 不能是空字符串。")
        short = normalize(args.short) if args.short else f"小{name}"

    out = Path(args.out).resolve() if args.out else DEFAULT_OUT
    if not args.print_only:
        # 护栏提前到渲染之前：失败时不再先打印“YAML 校验通过”再报错。
        guard_out_dir(out)

    print(f"角色名：{name}    小名：{short}")
    rendered, row_id, preset_id, slug = render(name, short, args.preset_id)
    validate_yaml(rendered, row_id)

    if args.print_only:
        print(rendered)
        return 0

    if out.exists():
        if not out.is_dir():
            fail(f"--out 指向的是一个已存在的文件，不是目录：{out}\n  删掉它，或换一个 --out。")
        if args.refresh:
            if not (out / "cordis.patch.yml").exists() and not (out / "package.json").exists():
                fail(
                    f"拒绝清空 {out}：它不是上一次生成的输出目录"
                    "（里面没有 cordis.patch.yml 或 package.json）。"
                )
            shutil.rmtree(out)
        elif any(out.iterdir()):
            fail(f"输出目录已存在且非空：{out}\n  加 --refresh 清空它，或换一个 --out。")
    out.mkdir(parents=True, exist_ok=True)
    package_name = f"@local/dsh-persona-{slug}"
    if args.preset_id and preset_id == "custom-persona":
        # 旧 id 沿用旧包名：install_bundle 才会把它认成同一个 bundle 走升级，
        # 而不是产生第二个 bundle 撞同一个 config.id。
        package_name = "@local/dsh-custom-persona-preset"
    patch_path = write_bundle(out, rendered, package_name)

    print("\n生成完成：")
    print(f"  {patch_path}")
    print(f"  {out / 'package.json'}")
    print(f"  预设 id：{preset_id}（在预设选择器里显示为「{name}」）")
    print("\n下一步（二选一）：")
    print("  A. 在 dsh 里让 AI 装：把 README.md 里那段「交给 AI 安装」的提示词连同本项目路径发给它，")
    print(f"     让它执行 plugin_manager install_bundle，target = {out}")
    print("  B. 手工装：把 cordis.patch.yml 的内容插到 profile 的 cordis.patch.yml 里")
    print("     （注意顶层 key，别整体覆盖别人的配置）——详见 README「手工安装」。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
