#!/usr/bin/env python3
"""Frontmatter repair tool — fixes common YAML parse failures in Obsidian notes.

Root causes identified:
1. Unquoted Wikilinks: [[note]] breaks YAML ( [ starts flow sequence)
2. Unquoted template variables: {{var}} breaks YAML ( { starts flow mapping)
3. Missing provenance fields

Modes:
  --dry-run: Show what would be fixed without changing files
  --fix: Apply fixes with .bak backups
  --add-provenance: Add minimal provenance_status frontmatter
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
import re
import shutil


def find_wikilinks_in_frontmatter(content: str) -> list[tuple[str, str]]:
    """Find unquoted Wikilinks in YAML frontmatter that will break parsing.

    Returns list of (original, fixed) tuples.
    """
    # Extract frontmatter
    if not content.startswith("---"):
        return []

    end = content.find("---", 3)
    if end == -1:
        return []

    frontmatter = content[3:end]
    fixes = []

    # Pattern: unquoted [[link]] on a YAML value line
    # Matches: key: [[value]] or key: [[v1]], [[v2]]
    # The issue: YAML interprets [ as flow sequence start
    for match in re.finditer(r'^([a-zA-Z_][a-zA-Z0-9_]*\s*:\s*)(.*\[\[.*\]\].*)$', frontmatter, re.MULTILINE):
        key_part = match.group(1)
        value_part = match.group(2)

        # Check if already quoted
        stripped = value_part.strip()
        if stripped.startswith('"') or stripped.startswith("'"):
            continue  # Already quoted

        # Quote the value
        new_line = f'{key_part}"{stripped}"'
        fixes.append((match.group(0), new_line))

    return fixes


def find_template_vars_in_frontmatter(content: str) -> list[tuple[str, str]]:
    """Find unquoted {{template}} variables in frontmatter."""
    if not content.startswith("---"):
        return []

    end = content.find("---", 3)
    if end == -1:
        return []

    frontmatter = content[3:end]
    fixes = []

    for match in re.finditer(r'^([a-zA-Z_][a-zA-Z0-9_]*\s*:\s*)(.*\{\{.*\}\}.*)$', frontmatter, re.MULTILINE):
        key_part = match.group(1)
        value_part = match.group(2)

        stripped = value_part.strip()
        if stripped.startswith('"') or stripped.startswith("'"):
            continue

        new_line = f'{key_part}"{stripped}"'
        fixes.append((match.group(0), new_line))

    return fixes


def add_provenance_frontmatter(content: str, status: str = "incomplete") -> str:
    """Add minimal provenance_status frontmatter to a note that has none."""
    if content.startswith("---"):
        # Has frontmatter — add field
        end = content.find("---", 3)
        if end == -1:
            return content
        frontmatter = content[3:end]
        if "provenance_status" in frontmatter:
            return content  # Already has it

        new_fm = frontmatter.rstrip() + f'\nprovenance_status: {status}\n'
        return "---" + new_fm + "---" + content[end + 3:]
    else:
        # No frontmatter — create one
        return f"---\nprovenance_status: {status}\n---\n\n{content}"


def repair_file(file_path: Path, dry_run: bool = True, add_provenance: bool = False) -> dict:
    """Repair a single file's frontmatter.

    Returns dict with repair details.
    """
    result = {
        "file": str(file_path),
        "wikilinks_fixed": 0,
        "templates_fixed": 0,
        "provenance_added": False,
        "backed_up": False,
    }

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        result["error"] = str(e)
        return result

    original = content

    # Fix wikilinks
    wl_fixes = find_wikilinks_in_frontmatter(content)
    for old, new in wl_fixes:
        content = content.replace(old, new, 1)
    result["wikilinks_fixed"] = len(wl_fixes)

    # Fix template variables
    tv_fixes = find_template_vars_in_frontmatter(content)
    for old, new in tv_fixes:
        content = content.replace(old, new, 1)
    result["templates_fixed"] = len(tv_fixes)

    # Add provenance if requested
    if add_provenance:
        new_content = add_provenance_frontmatter(content)
        if new_content != content:
            result["provenance_added"] = True
            content = new_content

    if content != original and not dry_run:
        # Backup
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        shutil.copy2(file_path, backup_path)
        result["backed_up"] = True

        # Write fix
        file_path.write_text(content, encoding="utf-8")
        result["fixed"] = True

    return result


def scan_and_report(vault_path: str, dry_run: bool = True):
    """Scan vault and report fixable issues."""
    vault = Path(vault_path)
    files = list(vault.rglob("*.md"))

    total_wikilinks = 0
    total_templates = 0
    fixable_files = []

    for f in sorted(files):
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        wl = find_wikilinks_in_frontmatter(content)
        tv = find_template_vars_in_frontmatter(content)

        if wl or tv:
            fixable_files.append({
                "file": str(f.relative_to(vault)),
                "wikilinks": len(wl),
                "templates": len(tv),
            })
            total_wikilinks += len(wl)
            total_templates += len(tv)

    mode = "DRY RUN" if dry_run else "FIX MODE"
    print(f"\n{'=' * 60}")
    print(f"  FRONTMATTER REPAIR SCAN — {mode}")
    print(f"{'=' * 60}")
    print(f"  Files with Wikilink issues: {len([x for x in fixable_files if x['wikilinks'] > 0])}")
    print(f"  Files with template issues: {len([x for x in fixable_files if x['templates'] > 0])}")
    print(f"  Total fixable files: {len(fixable_files)}")
    print(f"  Total Wikilinks to quote: {total_wikilinks}")
    print(f"  Total templates to quote: {total_templates}")
    print()

    if fixable_files:
        print("  ── FIXABLE FILES ──")
        for ff in fixable_files[:20]:
            issues = []
            if ff["wikilinks"]: issues.append(f"{ff['wikilinks']} wikilinks")
            if ff["templates"]: issues.append(f"{ff['templates']} templates")
            print(f"  📄 {ff['file']} ({', '.join(issues)})")
        if len(fixable_files) > 20:
            print(f"  ... and {len(fixable_files) - 20} more")

    return fixable_files


def repair_all(vault_path: str, dry_run: bool = True, add_provenance: bool = False):
    """Scan and repair all fixable files."""
    fixable = scan_and_report(vault_path, dry_run=dry_run)

    if dry_run:
        print(f"\n  Run with --fix to apply changes (backups created as .md.bak)")
        return

    vault = Path(vault_path)
    fixed_count = 0
    wl_total = 0
    tv_total = 0
    pv_total = 0

    for ff in fixable:
        file_path = vault / ff["file"]
        result = repair_file(file_path, dry_run=False, add_provenance=add_provenance)
        if result.get("fixed"):
            fixed_count += 1
        wl_total += result.get("wikilinks_fixed", 0)
        tv_total += result.get("templates_fixed", 0)
        if result.get("provenance_added"):
            pv_total += 1

    print(f"\n  Fixed: {fixed_count} files")
    print(f"  Wikilinks quoted: {wl_total}")
    print(f"  Templates quoted: {tv_total}")
    if add_provenance:
        print(f"  Provenance added: {pv_total}")
    print(f"  Backups: .md.bak files created")


# --- CLI ---

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Repair YAML frontmatter issues in Obsidian vault")
    parser.add_argument("vault_path", help="Path to vault root")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Scan only, don't modify files (default)")
    parser.add_argument("--fix", action="store_true",
                        help="Apply fixes (creates .bak backups)")
    parser.add_argument("--add-provenance", action="store_true",
                        help="Add provenance_status: incomplete to notes missing it")
    parser.add_argument("--dir", default=None,
                        help="Limit to specific directory within vault")
    parser.add_argument("--file", default=None,
                        help="Repair a single file")
    args = parser.parse_args()

    vault_path = args.vault_path
    is_dry_run = not args.fix

    if args.file:
        file_path = Path(vault_path) / args.file
        result = repair_file(file_path, dry_run=is_dry_run, add_provenance=args.add_provenance)
        print(json.dumps(result, indent=2, default=str))
    elif args.dir:
        vault = Path(vault_path) / args.dir
        fixable = []
        for f in sorted(vault.rglob("*.md")):
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            wl = find_wikilinks_in_frontmatter(content)
            tv = find_template_vars_in_frontmatter(content)
            if wl or tv:
                fixable.append({"file": str(f.relative_to(Path(vault_path))), "wikilinks": len(wl), "templates": len(tv)})

        scan_and_report(vault_path, dry_run=is_dry_run)

        if not is_dry_run:
            for ff in fixable:
                file_path = Path(vault_path) / ff["file"]
                result = repair_file(file_path, dry_run=False, add_provenance=args.add_provenance)
                if result.get("fixed"):
                    print(f"  Fixed: {ff['file']} ({result.get('wikilinks_fixed', 0)} wikilinks, {result.get('templates_fixed', 0)} templates)")

        if is_dry_run and args.add_provenance:
            print("\n  Note: --add-provenance only applies with --fix")
    else:
        repair_all(vault_path, dry_run=is_dry_run, add_provenance=args.add_provenance)


if __name__ == "__main__":
    import json
    main()
