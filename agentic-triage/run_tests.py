"""Run all agentic-triage tests and print a summary."""

import subprocess
import sys
from pathlib import Path


def main():
    project_root = Path(__file__).parent

    print("=" * 60)
    print("AGENTIC TRIAGE: Full Test Suite")
    print("=" * 60)
    print()

    # 1. Generate test set
    print("[1/3] Generating evaluation test set...")
    result = subprocess.run(
        [sys.executable, str(project_root / "tests/generate_test_set.py")],
        capture_output=True, text=True, cwd=str(project_root),
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        return 1

    # 2. Run integration tests
    print("[2/3] Running integration tests...")
    result = subprocess.run(
        [sys.executable, str(project_root / "tests/test_integration.py")],
        capture_output=True, text=True, cwd=str(project_root),
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"FAILED:\n{result.stderr}")
        return 1

    # 3. Verify outputs exist
    print("[3/3] Verifying artifacts...")
    data_dir = project_root / "data"
    artifacts = {
        "test_set": data_dir / "test_set/test_set.jsonl",
        "logs": data_dir / "logs",
        "memory": data_dir / "memory_store",
        "vault_index": data_dir / "vault_index",
        "prompts": data_dir / "prompts",
    }
    for name, path in artifacts.items():
        exists = path.exists()
        status = "EXISTS" if exists else "MISSING"
        print(f"  {name}: {path} -> {status}")

    print()
    print("=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
