"""
从 Foundry 编译产物导出合约 ABI，供后端和前端共用
用法（仓库根目录）：python scripts/export_abi.py
需先在 contracts 目录执行 forge build
"""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT_DIR / "contracts" / "out" / "Payment.sol" / "Payment.json"
TARGETS = [
    ROOT_DIR / "backend" / "abi" / "Payment.json",
    ROOT_DIR / "frontend" / "src" / "abi" / "Payment.json",
]


def main() -> None:
    # Git Bash 中 Windows 版 Python 默认按 GBK 输出，中文会乱码
    sys.stdout.reconfigure(encoding="utf-8")

    if not ARTIFACT.exists():
        sys.exit(f"找不到编译产物 {ARTIFACT}，请先在 contracts 目录运行 forge build")

    # 编译产物里还有字节码等内容，前后端只需要 abi 部分
    abi = json.loads(ARTIFACT.read_text(encoding="utf-8"))["abi"]
    content = json.dumps(abi, indent=2, ensure_ascii=False) + "\n"

    for target in TARGETS:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"已导出 {target.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
