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
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEN = HERE / "generate.py"
TEMPLATE = HERE / "templates" / "cordis.patch.template.yml"
EXAMPLE = HERE / "examples" / "cordis.patch.example.yml"

# pyyaml 是可选依赖：没有它时跳过产物回读，而不是把每条用例判成失败。
HAS_YAML = importlib.util.find_spec("yaml") is not None

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


def test_cases(tmp: Path) -> tuple[int, int]:
    """返回 (失败数, 跳过数)。没有 pyyaml 时跳过 YAML 回读并计为 SKIP。"""
    failures = 0
    skips = 0
    for i, (label, name, short, expect) in enumerate(CASES):
        out = tmp / f"case{i}"
        proc = run_gen(["--name", name, "--short", short, "--out", str(out), "--refresh"], tmp)
        ok = proc.returncode == expect
        detail = f"exit={proc.returncode} expect={expect}"
        if not ok:
            print(f"  [FAIL] {label}: {detail}")
            failures += 1
            continue
        if expect != 0:
            print(f"  [OK] {label}: {detail}")
            continue
        if not HAS_YAML:
            print(f"  [SKIP] {label}: 未装 pyyaml，跳过 YAML 回读")
            skips += 1
            continue
        try:
            doc = load_yaml(out / "cordis.patch.yml")
            got = doc[0]["insert"][0]["config"]["name"]
        except Exception as exc:  # noqa: BLE001
            print(f"  [FAIL] {label}: YAML 解析失败: {exc}")
            failures += 1
            continue
        want = name.strip().strip("'").strip('"').strip()
        if got != want:
            print(f"  [FAIL] {label}: name 回读不符: {got!r}")
            failures += 1
        else:
            print(f"  [OK] {label}: {detail}")
    return failures, skips


def test_template_hygiene() -> int:
    failures = 0
    raw = TEMPLATE.read_bytes()
    checks = [
        ("无 BOM", not raw.startswith(b"\xef\xbb\xbf")),
        ("无 Tab", b"\t" not in raw),
        ("含 {{ROLE_NAME}}", b"{{ROLE_NAME}}" in raw),
        ("含 {{ROLE_SHORT}}", b"{{ROLE_SHORT}}" in raw),
        ("含 {{ROLE_NAME_YAML}}", b"{{ROLE_NAME_YAML}}" in raw),
        ("含 {{PRESET_ROW_ID}}", b"{{PRESET_ROW_ID}}" in raw),
        ("含 {{PRESET_ID}}", b"{{PRESET_ID}}" in raw),
        ("保留 {{cwd}}", b"{{cwd}}" in raw),
    ]
    for label, ok in checks:
        print(f"  [{'OK' if ok else 'FAIL'}] {label}")
        failures += 0 if ok else 1
    return failures


def test_example_sync(tmp: Path) -> int:
    out = tmp / "example"
    proc = run_gen(["--name", "Lin Wan", "--short", "Wan", "--out", str(out), "--refresh"], tmp)
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


def test_out_guard(tmp: Path) -> int:
    failures = 0
    # 在临时副本里打靶：即使护栏回归，被删的也只是副本，不会毁掉工作树。
    proj = tmp / "proj"
    proj.mkdir()
    shutil.copy2(GEN, proj / "generate.py")
    shutil.copytree(TEMPLATE.parent, proj / "templates")

    def run_in_copy(args):
        return subprocess.run(
            [sys.executable, str(proj / "generate.py"), *args],
            cwd=str(proj),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    for label, arg in (("--out .", "."), ("--out ..", "..")):
        proc = run_in_copy(["--name", "护栏测试", "--out", arg, "--refresh"])
        ok = proc.returncode == 2 and (proj / "generate.py").exists()
        print(f"  [{'OK' if ok else 'FAIL'}] {label} 被拒绝，副本仍在 (exit={proc.returncode})")
        failures += 0 if ok else 1

    ok = (HERE / "generate.py").exists() and (HERE / "templates").exists()
    print(f"  [{'OK' if ok else 'FAIL'}] 执行后项目文件仍然存在")
    failures += 0 if ok else 1

    afile = tmp / "afile.txt"
    afile.write_text("x", encoding="utf-8")
    proc = run_gen(["--name", "护栏测试", "--out", str(afile)], tmp)
    ok = proc.returncode == 2 and "不是目录" in (proc.stdout + proc.stderr)
    print(f"  [{'OK' if ok else 'FAIL'}] --out 指向文件被拒绝 (exit={proc.returncode})")
    failures += 0 if ok else 1

    notours = tmp / "notours"
    notours.mkdir()
    (notours / "keep.txt").write_text("keep", encoding="utf-8")
    proc = run_gen(["--name", "护栏测试", "--out", str(notours), "--refresh"], tmp)
    ok = proc.returncode == 2 and (notours / "keep.txt").exists()
    print(f"  [{'OK' if ok else 'FAIL'}] 非产物目录拒绝清空、keep.txt 保留")
    failures += 0 if ok else 1

    # 只有 package.json 的普通 Node 项目也不能被当成产物删掉
    notours_pkg = tmp / "notours_pkg"
    notours_pkg.mkdir()
    (notours_pkg / "package.json").write_text('{"name":"someone-elses-project"}', encoding="utf-8")
    (notours_pkg / "keep.txt").write_text("keep", encoding="utf-8")
    proc = run_gen(["--name", "护栏测试", "--out", str(notours_pkg), "--refresh"], tmp)
    ok = proc.returncode == 2 and (notours_pkg / "keep.txt").exists()
    print(f"  [{'OK' if ok else 'FAIL'}] 普通 package.json 目录拒绝清空")
    failures += 0 if ok else 1

    # 自己的产物目录仍然允许 --refresh 重建
    okout = tmp / "okout"
    run_gen(["--name", "甲", "--out", str(okout), "--refresh"], tmp)
    proc = run_gen(["--name", "乙", "--out", str(okout), "--refresh"], tmp)
    ok = proc.returncode == 0
    print(f"  [{'OK' if ok else 'FAIL'}] 自己的产物目录允许 --refresh 重建")
    failures += 0 if ok else 1
    return failures


def test_identity(tmp: Path) -> int:
    """不同角色必须得到不同身份；--preset-id 必须能复现旧 id。"""
    failures = 0
    identities = {}
    for i, nm in enumerate(("林晚", "苏晴")):
        out = tmp / f"id{i}"
        proc = run_gen(["--name", nm, "--out", str(out), "--refresh"], tmp)
        if proc.returncode != 0:
            print(f"  [FAIL] 生成 {nm} 失败: exit={proc.returncode}")
            failures += 1
            continue
        pkg = json.loads((out / "package.json").read_text(encoding="utf-8"))
        row_id = config_id = None
        if HAS_YAML:
            import yaml  # noqa: PLC0415

            doc = yaml.safe_load((out / "cordis.patch.yml").read_text(encoding="utf-8"))
            row = doc[0]["insert"][0]
            row_id, config_id = row["id"], row["config"]["id"]
        identities[nm] = (pkg["name"], row_id, config_id)

    if len(identities) == 2:
        a, b = identities["林晚"], identities["苏晴"]
        pkg_ok = a[0] != b[0]
        print(f"  [{'OK' if pkg_ok else 'FAIL'}] 两个角色的包名不同")
        failures += 0 if pkg_ok else 1
        if HAS_YAML:
            id_ok = a[1] != b[1] and a[2] != b[2]
            print(f"  [{'OK' if id_ok else 'FAIL'}] 两个角色的 preset id 不同")
            failures += 0 if id_ok else 1
        else:
            print("  [SKIP] preset id 比对（未装 pyyaml）")

    out = tmp / "idoverride"
    proc = run_gen(["--name", "林晚", "--out", str(out), "--refresh", "--preset-id", "custom-persona"], tmp)
    ok = proc.returncode == 0
    detail = f"exit={proc.returncode}"
    if ok and HAS_YAML:
        import yaml  # noqa: PLC0415

        doc = yaml.safe_load((out / "cordis.patch.yml").read_text(encoding="utf-8"))
        row = doc[0]["insert"][0]
        ok = row["id"] == "preset-custom-persona" and row["config"]["id"] == "custom-persona"
        detail += f" | row={row['id']!r} config.id={row['config']['id']!r}"
    print(f"  [{'OK' if ok else 'FAIL'}] --preset-id custom-persona 复现旧 id: {detail}")
    failures += 0 if ok else 1

    if proc.returncode == 0:
        pkg = json.loads((out / "package.json").read_text(encoding="utf-8"))
        pkg_ok = pkg["name"] == "@local/dsh-custom-persona-preset"
        print(f"  [{'OK' if pkg_ok else 'FAIL'}] --preset-id custom-persona 包名回退: {pkg['name']}")
        failures += 0 if pkg_ok else 1

    # 同一角色换一个 --preset-id：包名必须跟着 id 变。否则两个不同预设共用一个 bundle 名，
    # install_bundle 会把第二个当成同一个包（跳过或覆盖），用户看到「改了 id 却没生效」。
    out2 = tmp / "idcustom"
    proc2 = run_gen(["--name", "林晚", "--out", str(out2), "--refresh", "--preset-id", "linwan"], tmp)
    if proc2.returncode == 0:
        pkg2 = json.loads((out2 / "package.json").read_text(encoding="utf-8"))
        default_pkg = identities.get("林晚", (None,))[0]
        ok2 = default_pkg is not None and pkg2["name"] != default_pkg
        print(f"  [{'OK' if ok2 else 'FAIL'}] 换 --preset-id 后包名随之改变: {pkg2['name']}")
        failures += 0 if ok2 else 1
    return failures


def test_preset_id_scalars(tmp: Path) -> tuple[int, int]:
    """--preset-id 传纯数字 / true / null 这类值时，config.id 必须仍是字符串。

    YAML 里未加引号的 `id: 0` 会解析成 int、`id: true` 成 bool、`id: null` 成 None，
    而 dsh 的 preset schema 要求 string —— 装上去会直接加载失败。模板现在给两个 id
    都加了单引号，这条测试防止有人把引号去掉。
    """
    failures = 0
    skips = 0
    for i, preset in enumerate(("0", "123", "true", "null", "-")):
        out = tmp / f"scalar{i}"
        proc = run_gen(["--name", "林晚", "--out", str(out), "--refresh", "--preset-id", preset], tmp)
        if proc.returncode != 0:
            print(f"  [FAIL] --preset-id {preset!r}: exit={proc.returncode} {proc.stderr.strip()[:70]}")
            failures += 1
            continue
        if not HAS_YAML:
            print(f"  [SKIP] --preset-id {preset!r} 类型校验（未装 pyyaml）")
            skips += 1
            continue
        import yaml  # noqa: PLC0415

        doc = yaml.safe_load((out / "cordis.patch.yml").read_text(encoding="utf-8"))
        got = doc[0]["insert"][0]["config"]["id"]
        ok = isinstance(got, str) and got == preset
        print(f"  [{'OK' if ok else 'FAIL'}] --preset-id {preset!r} → config.id={got!r} ({type(got).__name__})")
        failures += 0 if ok else 1
    return failures, skips


def main() -> int:
    parser = argparse.ArgumentParser(description="generate.py 自检")
    parser.add_argument("--standard", help="可选：shipped standard.patch.yml 的路径，用于插件清单对齐检查")
    args = parser.parse_args()

    failures = 0
    skips = 0
    with tempfile.TemporaryDirectory(prefix="lanxi-selftest-") as td:
        tmp = Path(td)
        print("[1] 生成器边界用例")
        case_failures, case_skips = test_cases(tmp)
        failures += case_failures
        skips += case_skips
        print("[2] 模板卫生")
        failures += test_template_hygiene()
        print("[3] 示例文件同步")
        failures += test_example_sync(tmp)
        print("[4] --out 护栏")
        failures += test_out_guard(tmp)
        print("[5] 身份派生")
        failures += test_identity(tmp)
        print("[6] --preset-id 标量安全")
        sid_failures, sid_skips = test_preset_id_scalars(tmp)
        failures += sid_failures
        skips += sid_skips
        if args.standard:
            print("[7] 插件清单对齐")
            failures += test_plugin_parity(Path(args.standard))

    print()
    if failures:
        print(f"自检失败：{failures} 项")
        return 1
    if skips:
        print(f"自检通过（跳过 {skips} 项：未装 pyyaml，无法做 YAML 回读）")
    else:
        print("自检全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
