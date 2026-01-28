"""
Automated Script to Replace print() Statements with logger Calls

This script automatically replaces print() statements with appropriate logger calls
based on the message content.

Usage:
    python scripts/replace_prints.py

Mapping:
    - print("[ERROR]", ...) → logger.error(...)
    - print("[WARNING]", ...) → logger.warning(...)
    - print("[DEBUG]", ...) → logger.debug(...)
    - print("[INFO]", ...) → logger.info(...)
    - print(...) → logger.info(...)  # Default
"""

import re
import os
from pathlib import Path
from typing import List, Tuple


class PrintReplacer:
    """Replaces print() statements with logger calls"""

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir)
        self.stats = {
            "files_processed": 0,
            "prints_replaced": 0,
            "errors": 0
        }

    def should_process_file(self, file_path: Path) -> bool:
        """Check if file should be processed"""
        # Skip test files, migrations, and specific directories
        skip_dirs = {"tests", "venv", ".git", "__pycache__", "node_modules"}
        skip_files = {"replace_prints.py", "setup.py"}

        if file_path.name in skip_files:
            return False

        for part in file_path.parts:
            if part in skip_dirs:
                return False

        return file_path.suffix == ".py"

    def detect_log_level(self, print_content: str) -> str:
        """Detect appropriate log level from print content"""
        content_lower = print_content.lower()

        if any(keyword in content_lower for keyword in ["error", "fail", "exception", "critical"]):
            return "error"
        elif any(keyword in content_lower for keyword in ["warn", "warning"]):
            return "warning"
        elif any(keyword in content_lower for keyword in ["debug", "trace"]):
            return "debug"
        else:
            return "info"

    def replace_print_in_line(self, line: str) -> Tuple[str, bool]:
        """
        Replace print() in a single line with logger call.

        Returns:
            (modified_line, was_replaced)
        """
        # Match print(...) statements
        pattern = r'(\s*)print\((.*?)\)(\s*#.*)?$'
        match = re.match(pattern, line)

        if not match:
            return line, False

        indent, content, comment = match.groups()
        comment = comment or ""

        # Detect log level
        level = self.detect_log_level(content)

        # Clean up content
        # Remove common prefixes like "[ERROR]", "[INFO]", etc.
        content = re.sub(r'^\s*[\'"]?\[(ERROR|WARNING|INFO|DEBUG)\]\s*[\'"]\s*[,+]\s*', '', content)

        # Convert f-strings if needed
        if content.strip().startswith('f"') or content.strip().startswith("f'"):
            pass  # f-strings work with logger
        elif content.strip().startswith('"') or content.strip().startswith("'"):
            pass  # Regular strings work too
        else:
            # Might be expression, wrap in f-string
            content = f'f"{{{content}}}"'

        # Generate logger call
        new_line = f'{indent}logger.{level}({content}){comment}\n'

        return new_line, True

    def add_logger_import(self, content: str) -> str:
        """Add logger import if not present"""
        # Check if already has logger import
        if 'from utils.logging_config import' in content or 'logger = get_logger' in content:
            return content

        # Find best place to add import (after other imports)
        lines = content.split('\n')
        insert_index = 0

        # Find last import statement
        for i, line in enumerate(lines):
            if line.strip().startswith('import ') or line.strip().startswith('from '):
                insert_index = i + 1

        # Add logger import and get_logger call
        logger_import = "from utils.logging_config import get_logger"
        logger_init = "\nlogger = get_logger(__name__)\n"

        lines.insert(insert_index, logger_import)
        lines.insert(insert_index + 1, logger_init)

        return '\n'.join(lines)

    def process_file(self, file_path: Path) -> int:
        """
        Process a single file, replacing print() statements.

        Returns:
            Number of replacements made
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            original_content = content
            lines = content.split('\n')
            new_lines = []
            replacements = 0

            for line in lines:
                new_line, replaced = self.replace_print_in_line(line)
                new_lines.append(new_line.rstrip('\n'))
                if replaced:
                    replacements += 1

            if replacements > 0:
                # Add logger import if needed
                new_content = '\n'.join(new_lines)
                new_content = self.add_logger_import(new_content)

                # Write back
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)

                print(f"✓ {file_path}: {replacements} print() replaced")

            return replacements

        except Exception as e:
            print(f"✗ {file_path}: Error - {e}")
            self.stats["errors"] += 1
            return 0

    def process_directory(self):
        """Process all Python files in directory"""
        print("Starting print() replacement...")
        print(f"Root directory: {self.root_dir.absolute()}\n")

        for py_file in self.root_dir.rglob("*.py"):
            if not self.should_process_file(py_file):
                continue

            replacements = self.process_file(py_file)
            if replacements > 0:
                self.stats["files_processed"] += 1
                self.stats["prints_replaced"] += replacements

        # Print summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Files processed: {self.stats['files_processed']}")
        print(f"Print statements replaced: {self.stats['prints_replaced']}")
        print(f"Errors: {self.stats['errors']}")
        print("=" * 60)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Replace print() with logger calls")
    parser.add_argument(
        "--root",
        default=".",
        help="Root directory to process (default: current directory)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files"
    )

    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN MODE - No files will be modified\n")

    replacer = PrintReplacer(root_dir=args.root)

    if not args.dry_run:
        replacer.process_directory()
    else:
        print("Dry run not yet implemented. Remove --dry-run to execute.")


if __name__ == "__main__":
    main()
