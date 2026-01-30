#!/usr/bin/env python3
"""
Auto Generator for Software Copyright Application

Watches the prompts directory for .pending files and automatically
generates content using the VSCode extension's AI capability.
"""

import os
import sys
import time
import json
import re
from pathlib import Path
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from main import PROMPTS_DIR, PROCESS_DIR, ensure_directory


class AutoGenerator:
    """Automatically generates content when .pending files are detected."""

    def __init__(self):
        self.running = True

    def check_pending_files(self) -> List[Path]:
        """Check for any .pending files in prompts directory."""
        ensure_directory(PROMPTS_DIR)
        pending_files = list(PROMPTS_DIR.glob("*.pending"))
        return pending_files

    def read_prompt(self, pending_file: Path) -> str:
        """Read the prompt content from a .pending file."""
        with open(pending_file, 'r', encoding='utf-8') as f:
            return f.read()

    def get_output_filename(self, pending_file: Path) -> str:
        """Get the output filename from a .pending file."""
        return pending_file.stem.replace('.prompt', '')

    def generate_srs_content(self, prompt: str) -> str:
        """
        Generate SRS JSON content based on the prompt.

        This is called when a .pending file is detected for SRS generation.
        The actual AI generation will be handled by the VSCode extension.
        """
        # Parse the prompt to extract software info
        software_name = ""
        industry = ""

        for line in prompt.split('\n'):
            if line.startswith("Software Name:"):
                software_name = line.split(":", 1)[1].strip()
            elif line.startswith("Industry:"):
                industry = line.split(":", 1)[1].strip()

        # Return a placeholder - actual generation by AI
        raise NotImplementedError(
            "This function should be called by VSCode extension's AI. "
            "The extension should detect .pending files and generate content automatically."
        )

    def process_pending_file(self, pending_file: Path):
        """Process a single .pending file and generate output."""
        print(f"\n{'='*60}")
        print(f"  检测到待生成任务: {pending_file.name}")
        print(f"{'='*60}")

        prompt = self.read_prompt(pending_file)
        output_filename = self.get_output_filename(pending_file)
        output_path = PROCESS_DIR / output_filename

        print(f"\n  提示词内容预览:")
        print(f"  {prompt[:200]}...")

        print(f"\n  ⏳ 等待 AI 生成内容...")
        print(f"  💡 请在 VSCode 中通知 Claude Code 生成内容")
        print(f"  📁 保存到: {output_path}")

        # Wait for output file to be created
        max_wait = 600  # 10 minutes
        waited = 0
        check_interval = 1

        while waited < max_wait:
            if output_path.exists():
                file_size = output_path.stat().st_size
                if file_size > 0:
                    print(f"  ✓ 内容已生成! ({file_size} 字节)")
                    # Remove the .pending file
                    pending_file.unlink()
                    print(f"  ✓ 已清理标记文件: {pending_file.name}")
                    return True
            time.sleep(check_interval)
            waited += check_interval
            if waited % 10 == 0 and waited > 0:
                print(f"  等待中... ({waited}s)")

        print(f"  ⚠️  超时: 未能生成内容")
        return False

    def run(self):
        """Main loop to watch for .pending files."""
        print("\n" + "="*60)
        print("  自动生成器已启动")
        print("="*60)
        print(f"\n  监听目录: {PROMPTS_DIR}")
        print(f"  输出目录: {PROCESS_DIR}")
        print(f"\n  监听 *.pending 文件... (按 Ctrl+C 退出)")
        print("-"*60)

        try:
            while self.running:
                pending_files = self.check_pending_files()

                if pending_files:
                    for pending_file in pending_files:
                        self.process_pending_file(pending_file)
                else:
                    # No pending files, wait before next check
                    time.sleep(1)

        except KeyboardInterrupt:
            print("\n\n  ⚠️  收到中断信号，退出...")
            sys.exit(0)


def main():
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Auto Generator for Software Copyright Application"
    )
    parser.add_argument(
        "--once", "-o",
        action="store_true",
        help="Check once and exit (don't loop)"
    )

    args = parser.parse_args()

    generator = AutoGenerator()

    if args.once:
        # Check once and exit
        pending_files = generator.check_pending_files()
        if pending_files:
            for pending_file in pending_files:
                generator.process_pending_file(pending_file)
        else:
            print("  没有检测到待处理文件")
    else:
        # Run in continuous loop
        generator.run()


if __name__ == "__main__":
    main()
