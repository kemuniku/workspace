#!/usr/bin/env python3
import argparse
import os
import shutil
import string
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse


def index_to_label(index: int) -> str:
    """Convert 0-based index to spreadsheet-like label: 0->A, 25->Z, 26->AA."""
    if index < 0:
        raise ValueError("index must be non-negative")

    label = ""
    n = index
    while True:
        label = string.ascii_uppercase[n % 26] + label
        n = n // 26 - 1
        if n < 0:
            break
    return label


def label_to_index(label: str) -> int:
    """Convert label to 0-based index: A->0, Z->25, AA->26."""
    if not label or not label.isalpha() or not label.isupper():
        raise ValueError(f"Invalid problem label: {label}")

    index = 0
    for ch in label:
        index = index * 26 + (ord(ch) - ord("A") + 1)
    return index - 1


def resolve_contest_dir(script_dir: Path, contest_dir: str) -> Path:
    contest_path = Path(contest_dir)

    if contest_path.is_absolute():
        candidate = contest_path
    else:
        candidate = (Path.cwd() / contest_path).resolve()
        if not candidate.exists():
            candidate = (script_dir / contest_path).resolve()
        if not candidate.exists():
            candidate = (script_dir / "contests" / contest_path).resolve()

    if not candidate.exists() or not candidate.is_dir():
        raise FileNotFoundError(f"Contest directory not found: {candidate}")

    return candidate


def is_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")


def infer_problem_name_from_url(problem_url: str) -> str | None:
    """Infer folder name from the last URL path segment."""
    parsed = urlparse(problem_url)
    if not parsed.scheme or not parsed.netloc:
        return None

    segments = [s for s in parsed.path.split("/") if s]
    if not segments:
        return None

    last_segment = unquote(segments[-1]).strip()
    return last_segment or None


def is_auto_label_name(name: str) -> bool:
    return bool(name) and name.isalpha() and name.isupper()


def existing_problem_labels(contest_dir: Path) -> set[str]:
    labels: set[str] = set()
    for child in contest_dir.iterdir():
        if child.is_dir() and child.name.isalpha() and child.name.isupper():
            labels.add(child.name)
    return labels


def create_problem_dir(template_dir: Path, contest_dir: Path, problem_label: str) -> Path | None:
    target_dir = contest_dir / problem_label
    if target_dir.exists():
        print(f"Skipped: '{problem_label}' already exists.")
        return None

    shutil.copytree(template_dir, target_dir)

    old_file = target_dir / "Main.nim"
    new_filename = f"{problem_label}.nim"
    new_file = target_dir / new_filename
    if old_file.exists():
        old_file.rename(new_file)

    for root, _, files in os.walk(target_dir):
        for file_name in files:
            file_path = Path(root) / file_name
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception:
                # Skip unreadable/binary files.
                continue

            if "__mainname__" in content:
                file_path.write_text(content.replace("__mainname__", new_filename), encoding="utf-8")

    print(f"Created: {target_dir}")
    return target_dir


def download_testcases(problem_dir: Path, problem_url: str) -> None:
    """Run `oj d <url>` in the created problem directory."""
    try:
        proc = subprocess.run(["oj", "d", problem_url], cwd=str(problem_dir), check=False)
    except FileNotFoundError:
        print("Warning: 'oj' command not found. Skipped downloading testcases.")
        return

    if proc.returncode != 0:
        print(f"Warning: oj download failed for {problem_url} (exit code {proc.returncode})")


def choose_next_labels(existing: set[str], count: int) -> list[str]:
    if count <= 0:
        raise ValueError("--count must be >= 1")

    used = {label_to_index(lbl) for lbl in existing}
    next_labels: list[str] = []

    idx = 0
    while len(next_labels) < count:
        if idx not in used:
            next_labels.append(index_to_label(idx))
            used.add(idx)
        idx += 1

    return next_labels


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Add problem folders to an existing contest directory."
        )
    )
    parser.add_argument(
        "items",
        nargs="*",
        help=(
            "Problem labels or problem URLs (e.g. G H AA https://atcoder.jp/.../tasks/abc449_g)."
        ),
    )
    parser.add_argument(
        "-C",
        "--contest-dir",
        default=".",
        help=(
            "Contest directory to add problems to. Defaults to current directory "
            "(intended usage: run inside workspace/contests/<contest_id>)."
        ),
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=0,
        help="Create this many next available labels automatically.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    template_dir = script_dir / "template"

    if not template_dir.exists():
        print(f"Error: template directory not found: {template_dir}")
        return 1

    try:
        contest_dir = resolve_contest_dir(script_dir, args.contest_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    planned_items: list[tuple[str, str | None]] = []
    used_auto_labels = existing_problem_labels(contest_dir)

    if args.items:
        for raw in args.items:
            if is_url(raw):
                problem_url = raw
                inferred = infer_problem_name_from_url(raw)
                if inferred:
                    label = inferred
                else:
                    # If URL format does not carry letter info, assign next available label.
                    label = choose_next_labels(used_auto_labels, 1)[0]
                    print(f"Info: could not infer label from URL, assigned '{label}' for {raw}")
            else:
                problem_url = None
                label = raw.strip().upper()
                if not label or not label.isalpha():
                    print(f"Error: invalid problem label '{raw}'. Use A-Z style names only.")
                    return 1

            planned_items.append((label, problem_url))
            if is_auto_label_name(label):
                used_auto_labels.add(label)

    if args.count > 0:
        for label in choose_next_labels(used_auto_labels, args.count):
            planned_items.append((label, None))
            used_auto_labels.add(label)

    if not planned_items:
        print("Error: specify labels/URLs or --count.")
        return 1

    # Preserve order and merge duplicates. If any occurrence has URL, keep that URL.
    planned_by_label: dict[str, str | None] = {}
    for label, problem_url in planned_items:
        if label not in planned_by_label:
            planned_by_label[label] = problem_url
        elif planned_by_label[label] is None and problem_url is not None:
            planned_by_label[label] = problem_url

    for label, problem_url in planned_by_label.items():
        created_dir = create_problem_dir(template_dir, contest_dir, label)
        if created_dir is not None and problem_url is not None:
            print(f"Downloading testcases for '{label}' from {problem_url}")
            download_testcases(created_dir, problem_url)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
