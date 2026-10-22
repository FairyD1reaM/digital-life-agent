#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generate.py 的自检。改完生成器/模板后跑一遍，防止回归。

用法：
    python selftest.py
    python selftest.py --standard /path/to/standard-0.2.1.patch.yml

不依赖 pytest，只用标准库 + 可选的 pyyaml。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEN = HERE / "generate.py"
TEMPLATE = HERE / "templates" / "cordis.patch.template.yml"
EXAMPLE = HERE / "examples" / "cordis.patch.example.yml"

# (说明, 名字, 小名, 期望退出码)
CASES = [
    ("普通中文名", "林晚", "小晚", 0),
    ("单引号", "O'Brien", "小OB", 0),
    ("双引号", 'He said "hi"', "H", 0),
    ("冒号与井号", "蓝:汐 #1", "小汐", 0),
    ("反斜杠", "a\\b", "ab", 0),
    ("YAML 特殊符号", "&a*b |>-", "x", 0),
    ("表情", "喵🐱", "小喵", 0),
    ("超长名字", "长" * 200, "短", 0),
    ("前后空格会被 strip", "  空格名  ", "  ", 0),
    ("占位符撞名应拒绝", "{{ROLE_NAME}}", "x", 2),
    ("换行名字应拒绝", "a\nb", "x", 2),
]


def load_yaml(path: Path):
    import yaml  # noqa: PLC0415

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def run_gen(args, tmp: Path):
    return subprocess.run(
        [sys.executable, str(GEN), *args],
        cwd=HERE,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_cases(tmp: Path) -> int:
    failures = 0
    for i, (label, name, short, expect) in enumerate(CASES):
        out = tmp / f"case{i}"
        proc = run_gen(["--name", name, "--short", short, "--out", str(out), "--refresh"], tmp)
        ok = proc.returncode == expect
        detail = f"exit={proc.returncode} expect={expect}"
        if ok and expect == 0:
            try:
                doc = load_yaml(out / "cordis.patch.yml")
                got = doc[0]["insert"][0]["config"]["name"]
                if got != name.strip().strip("'").strip('"').strip():
                    ok = False
                    detail += f" | name 回读不符: {got!r}"
            except Exception as exc:  # noqa: BLE001
                ok = False
                detail = f"YAML 解析失败: {exc}"
        print(f"  [{'OK' if ok else 'FAIL'}] {label}: {detail}")
        failures += 0 if ok else 1
    return failures


def test_template_hygiene() -> int:
    failures = 0
    raw = TEMPLATE.read_bytes()
    checks = [
        ("无 BOM", not raw.startswith(b"\xef\xbb\xbf")),
        ("无 Tab", b"\t" not in raw),
        ("含 {{ROLE_NAME}}", b"{{ROLE_NAME}}" in raw),
        ("含 {{ROLE_SHORT}}", b"{{ROLE_SHORT}}" in raw),
        ("含 {{ROLE_NAME_YAML}}", b"{{ROLE_NAME_YAML}}" in raw),
        ("保留 {{cwd}}", b"{{cwd}}" in raw),
    ]
    for label, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {label}")
        failures += 0 if ok else 1
    return failures


def test_example_sync(tmp: Path) -> int:
    out = tmp / "example"
    proc = run_gen(["--name", "示例名", "--short", "小名", "--out", str(out), "--refresh"], tmp)
    if proc.returncode != 0:
        print(f"  [FAIL] 示例生成失败: {proc.stderr.strip()}")
        return 1
    generated = (out / "cordis.patch.yml").read_text(encoding="utf-8")
    current = EXAMPLE.read_text(encoding="utf-8")
    ok = generated == current
    print(f"  [{'OK' if ok else 'FAIL'}] examples/cordis.patch.example.yml 与模板同步")
    if not ok:
        print("        提示：重新生成后覆盖示例文件")
    return 0 if ok else 1


def test_plugin_parity(standard: Path) -> int:
    import re

    def rows(path: Path, indent: int):
        out = []
        cur = None
        for ln in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^ {" + str(indent) + r"}- id: (\S+)\s*$", ln)
            if m:
                if cur:
                    out.append(cur)
                cur = [m.group(1), None]
                continue
            m2 = re.match(r"^ {" + str(indent) + r"}  name: (\S+)\s*$", ln)
            if m2 and cur and cur[1] is None:
                cur[1] = m2.group(1).strip("'\"")
        if cur:
            out.append(cur)
        return dict(out)

    std = rows(standard, 10)
    tpl = rows(TEMPLATE, 10)
    missing = [i for i in std if i not in tpl]
    extra = [i for i in tpl if i not in std]
    renamed = [(i, std[i], tpl[i]) for i in std if i in tpl and std[i] != tpl[i]]
    ok = not missing and not extra and not renamed
    print(f"  [{'OK' if ok else 'FAIL'}] 插件清单与 standard 对齐（{len(std)} 条）")
    if not ok:
        print(f"        缺少={missing} 多出={extra} 改名={renamed}")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="generate.py 自检")
    parser.add_argument("--standard", help="可选：shipped standard.patch.yml 的路径，用于插件清单对齐检查")
    args = parser.parse_args()

    failures = 0
    with tempfile.TemporaryDirectory(prefix="lanxi-selftest-") as td:
        tmp = Path(td)
        print("[1] 生成器边界用例")
        failures += test_cases(tmp)
        print("[2] 模板卫生")
        failures += test_template_hygiene()
        print("[3] 示例文件同步")
        failures += test_example_sync(tmp)
        if args.standard:
            print("[4] 插件清单对齐")
            failures += test_plugin_parity(Path(args.standard))

    print()
    if failures:
        print(f"自检失败：{failures} 项")
        return 1
    print("自检全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
