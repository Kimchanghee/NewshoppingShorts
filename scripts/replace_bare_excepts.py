"""
Automated Script to Replace Bare except: Blocks

This script finds and replaces bare except: blocks with specific exception types.

Usage:
    python scripts/replace_bare_excepts.py

Safety:
    - Creates backup before modifying files
    - Only replaces simple cases
    - Complex cases are flagged for manual review
"""

import re
import os
import shutil
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime


class BareExceptReplacer:
    """Replaces bare except: blocks with specific exceptions"""

    # Common exception patterns based on context
    CONTEXT_PATTERNS = {
        "import": "(ImportError, ModuleNotFoundError)",
        "file": "(FileNotFoundError, PermissionError, OSError)",
        "network": "(ConnectionError, TimeoutError, OSError)",
        "json": "(json.JSONDecodeError, ValueError, KeyError)",
        "api": "(requests.RequestException, ValueError, KeyError)",
        "ocr": "(OCRInitializationError, RuntimeError, ImportError)",
        "video": "(cv2.error, ValueError, RuntimeError)",
    }

    def __init__(self, root_dir: str = ".", create_backup: bool = True):
        self.root_dir = Path(root_dir)
        self.create_backup = create_backup
        self.stats = {
            "files_scanned": 0,
            "bare_excepts_found": 0,
            "auto_fixed": 0,
            "manual_review_needed": 0,
            "errors": 0
        }
        self.manual_review_cases = []

    def should_process_file(self, file_path: Path) -> bool:
        """Check if file should be processed"""
        skip_dirs = {"tests", "venv", ".git", "__pycache__", "node_modules", "backup"}
        skip_files = {"replace_bare_excepts.py", "setup.py"}

        if file_path.name in skip_files:
            return False

        for part in file_path.parts:
            if part in skip_dirs:
                return False

        return file_path.suffix == ".py"

    def detect_exception_type(self, try_block_content: str) -> Optional[str]:
        """
        Detect appropriate exception type based on try block content.

        Returns:
            Exception type string or None if cannot determine
        """
        content_lower = try_block_content.lower()

        # Check for import statements
        if "import " in content_lower:
            return self.CONTEXT_PATTERNS["import"]

        # Check for file operations
        if any(keyword in content_lower for keyword in ["open(", "read", "write", "file", "path"]):
            return self.CONTEXT_PATTERNS["file"]

        # Check for network operations
        if any(keyword in content_lower for keyword in ["request", "http", "socket", "urllib"]):
            return self.CONTEXT_PATTERNS["network"]

        # Check for JSON operations
        if "json" in content_lower:
            return self.CONTEXT_PATTERNS["json"]

        # Check for OCR operations
        if any(keyword in content_lower for keyword in ["ocr", "tesseract", "rapidocr"]):
            return self.CONTEXT_PATTERNS["ocr"]

        # Check for video operations
        if any(keyword in content_lower for keyword in ["cv2", "video", "capture", "frame"]):
            return self.CONTEXT_PATTERNS["video"]

        # Default to general exceptions
        return "(Exception,)"

    def find_bare_excepts(self, content: str) -> List[Tuple[int, str, str]]:
        """
        Find all bare except: blocks in content.

        Returns:
            List of (line_number, except_line, try_block_content)
        """
        lines = content.split('\n')
        bare_excepts = []
        current_try_block = []
        in_try_block = False
        try_start_line = -1

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Detect try: block
            if stripped.startswith('try:'):
                in_try_block = True
                try_start_line = i
                current_try_block = []
                continue

            # Collect try block content
            if in_try_block:
                if stripped.startswith('except:') or stripped == 'except:':
                    # Found bare except
                    try_content = '\n'.join(current_try_block)
                    bare_excepts.append((i, line, try_content))
                    in_try_block = False
                elif stripped.startswith('except ') or stripped.startswith('finally:') or stripped.startswith('else:'):
                    # End of try block
                    in_try_block = False
                else:
                    current_try_block.append(line)

        return bare_excepts

    def replace_bare_except(self, content: str, file_path: Path) -> Tuple[str, int, int]:
        """
        Replace bare except: blocks in content.

        Returns:
            (modified_content, auto_fixed_count, manual_review_count)
        """
        lines = content.split('\n')
        bare_excepts = self.find_bare_excepts(content)

        auto_fixed = 0
        manual_review = 0

        for line_num, except_line, try_content in reversed(bare_excepts):
            # Detect exception type
            exception_type = self.detect_exception_type(try_content)

            # Get indentation
            indent = except_line[:len(except_line) - len(except_line.lstrip())]

            if exception_type and exception_type != "(Exception,)":
                # Can auto-fix with specific exception
                new_except_line = f"{indent}except {exception_type} as e:"
                lines[line_num] = new_except_line
                auto_fixed += 1
            else:
                # Needs manual review
                new_except_line = f"{indent}except Exception as e:  # TODO: Specify exception type"
                lines[line_num] = new_except_line
                manual_review += 1

                self.manual_review_cases.append({
                    "file": str(file_path),
                    "line": line_num + 1,
                    "try_content": try_content[:100],  # First 100 chars
                })

        modified_content = '\n'.join(lines)
        return modified_content, auto_fixed, manual_review

    def create_backup_file(self, file_path: Path):
        """Create backup of file before modifying"""
        backup_dir = self.root_dir / "backup" / "before_except_replacement"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        relative_path = file_path.relative_to(self.root_dir)
        backup_path = backup_dir / f"{relative_path.stem}_{timestamp}{relative_path.suffix}"

        shutil.copy2(file_path, backup_path)
        return backup_path

    def process_file(self, file_path: Path) -> Tuple[int, int]:
        """
        Process a single file.

        Returns:
            (auto_fixed_count, manual_review_count)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Find bare excepts
            bare_excepts = self.find_bare_excepts(content)
            if not bare_excepts:
                return 0, 0

            self.stats["bare_excepts_found"] += len(bare_excepts)

            # Create backup if needed
            if self.create_backup:
                self.create_backup_file(file_path)

            # Replace bare excepts
            modified_content, auto_fixed, manual_review = self.replace_bare_except(content, file_path)

            # Write back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)

            if auto_fixed > 0 or manual_review > 0:
                print(f"✓ {file_path}: {auto_fixed} auto-fixed, {manual_review} need manual review")

            return auto_fixed, manual_review

        except Exception as e:
            print(f"✗ {file_path}: Error - {e}")
            self.stats["errors"] += 1
            return 0, 0

    def process_directory(self):
        """Process all Python files in directory"""
        print("Starting bare except: replacement...")
        print(f"Root directory: {self.root_dir.absolute()}\n")

        for py_file in self.root_dir.rglob("*.py"):
            if not self.should_process_file(py_file):
                continue

            self.stats["files_scanned"] += 1
            auto_fixed, manual_review = self.process_file(py_file)

            self.stats["auto_fixed"] += auto_fixed
            self.stats["manual_review_needed"] += manual_review

        # Print summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Files scanned: {self.stats['files_scanned']}")
        print(f"Bare except: blocks found: {self.stats['bare_excepts_found']}")
        print(f"Auto-fixed: {self.stats['auto_fixed']}")
        print(f"Need manual review: {self.stats['manual_review_needed']}")
        print(f"Errors: {self.stats['errors']}")
        print("=" * 60)

        # Print manual review cases
        if self.manual_review_cases:
            print("\nMANUAL REVIEW NEEDED:")
            print("=" * 60)
            for case in self.manual_review_cases[:10]:  # Show first 10
                print(f"\nFile: {case['file']}")
                print(f"Line: {case['line']}")
                print(f"Try block preview: {case['try_content']}...")
            if len(self.manual_review_cases) > 10:
                print(f"\n... and {len(self.manual_review_cases) - 10} more cases")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Replace bare except: blocks")
    parser.add_argument(
        "--root",
        default=".",
        help="Root directory to process (default: current directory)"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Don't create backup files"
    )

    args = parser.parse_args()

    replacer = BareExceptReplacer(
        root_dir=args.root,
        create_backup=not args.no_backup
    )

    replacer.process_directory()


if __name__ == "__main__":
    main()
