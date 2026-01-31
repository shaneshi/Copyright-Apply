#!/usr/bin/env python3
"""
Software Copyright Application Automation Tool

This orchestrator automates the generation of software copyright application materials
including:
- Software Requirements Specification (SRS)
- Frontend HTML/CSS code for each module
- Functional Manual (功能说明书)
- Installation Manual (安装说明书)
- Registration Form (软件著作权登记信息表)

Target: 3000-3200 lines of code (strict requirement)
OS: Linux only
Dev Tools: VSCode only
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import json

# Import AI bridge for automatic generation
try:
    from ai_bridge import AIBridge, generate_srs_auto, generate_html_code_auto, expand_document_template
    AI_BRIDGE_AVAILABLE = True
except ImportError:
    AI_BRIDGE_AVAILABLE = False

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT = Path(__file__).parent
TEMPLATE_DIR = PROJECT_ROOT / "template"
PROCESS_DIR = PROJECT_ROOT / "process"
OUTPUT_DIR = PROJECT_ROOT / "output"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

# No line limit - generate based on actual functionality
DEFAULT_OS = "Linux"
DEFAULT_DEV_TOOL = "VSCode"

# Template files
TEMPLATE_FILES = {
    "variables": "variables.md",
    "function_manual": "软件功能说明书.md",
    "install_manual": "软件安装说明书.md",
    "registration_form": "软件著作权登记信息表.md",
}

# Output files
OUTPUT_FILES = {
    "function_manual": "软件功能说明书.md",
    "install_manual": "软件安装说明书.md",
    "registration_form": "软件著作权登记信息表.md",
    "source_code": "源代码.md",
}


# ============================================================================
# VARIABLE DEFINITIONS (from variables.md)
# ============================================================================

VARIABLE_DEFINITIONS = {
    "software_name": {
        "prompt": "请输入软件全称 (例如: 智能医疗管理系统)",
        "default": "医院排队叫号系统",
        "required": True
    },
    "version": {
        "prompt": "请输入版本号",
        "default": "V1.0",
        "required": False
    },
    "applicant": {
        "prompt": "请输入著作权人名称",
        "default": "",
        "required": False
    },
    "comp_date": {
        "prompt": "请输入软件开发完成日期 (格式: 2025.9.30)",
        "default": "2024.12.31",
        "required": True
    },
    "industry": {
        "prompt": "请输入面向领域/行业 (例如: 二三级医院)",
        "default": "",
        "required": False
    },
    "applicant_address": {
        "prompt": "请输入申请人详细地址",
        "default": "",
        "required": False
    },
    "applicant_contact": {
        "prompt": "请输入联系人姓名",
        "default": "",
        "required": False
    },
    "applicant_phone": {
        "prompt": "请输入手机号码",
        "default": "",
        "required": False
    },
}

# Additional generated variables (not prompted, filled by LLM)
GENERATED_VARIABLES = [
    "module_count",         # 功能点数量
    "dev_purpose",           # 开发目的
    "main_functions_summary", # 主要功能概要
    "main_functions_details", # 主要功能详细说明
    "line_count",            # 程序量(行数)
]


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def print_step(step: int, total: int, description: str):
    """Print a formatted step indicator."""
    print(f"\n[{step}/{total}] {description}")
    print("-" * 60)


def confirm_action(prompt_text: str) -> bool:
    """Ask user to confirm before proceeding."""
    play_alert_sound()
    while True:
        response = input(f"\n  {prompt_text} (y/n): ").strip().lower()
        if response in ['y', 'yes', '是', 'Y']:
            return True
        elif response in ['n', 'no', '否', 'N']:
            return False
        else:
            print(f"  请输入 y/是 或 n/否")


def play_alert_sound():
    """Play an alert sound to notify user attention is needed."""
    import platform
    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            os.system("afplay /System/Library/Sounds/Glass.aiff &")
        elif system == "Linux":
            # Try common Linux sound commands
            os.system("paplay /usr/share/sounds/freedesktop/stereo/message.oga 2>/dev/null &")
            os.system("aplay /usr/share/sounds/alsa/Front_Center.wav 2>/dev/null &")
        elif system == "Windows":
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception:
        # Silently ignore if sound fails to play
        pass


def count_lines_in_file(filepath: Path) -> int:
    """Count non-empty lines in a file."""
    count = 0
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def count_total_lines(directory: Path, pattern: str = "*.html") -> int:
    """Count total lines in all matching files in a directory."""
    total = 0
    for filepath in directory.glob(pattern):
        total += count_lines_in_file(filepath)
    return total


def ensure_directory(directory: Path):
    """Ensure a directory exists."""
    directory.mkdir(parents=True, exist_ok=True)


def read_template(template_name: str) -> str:
    """Read a template file."""
    filepath = TEMPLATE_DIR / template_name
    if not filepath.exists():
        raise FileNotFoundError(f"Template file not found: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def write_output(filename: str, content: str):
    """Write content to output directory."""
    filepath = OUTPUT_DIR / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  ✓ Generated: {filepath}")


def replace_variables(template: str, variables: Dict[str, str]) -> str:
    """Replace all {{variable}} placeholders in template."""
    result = template
    for key, value in variables.items():
        placeholder = f"{{{{{key}}}}}"
        result = result.replace(placeholder, value)
    return result


# ============================================================================
# CLAUDE CODE INTEGRATION
# ============================================================================

class ClaudeCodeIntegrator:
    """
    Integrates with Claude Code for LLM content generation.

    Supports two modes:
    1. CLI mode: Calls Claude Code CLI directly
    2. Interactive mode: Prompts user to invoke Claude Code manually
    3. Auto mode: Automatically generates content using internal LLM
    """

    def __init__(self, mode: str = "auto", vscode_extension=None):
        self.mode = mode
        self.vscode_extension = vscode_extension  # Reference to VSCode extension for auto-generation

    def generate_srs(self, software_name: str, industry: str, module_count: int = 10) -> str:
        """
        Generate Software Requirements Specification with specified module count.

        Args:
            software_name: Name of the software
            industry: Target industry
            module_count: Number of modules to generate

        Returns JSON with module definitions.
        """
        # Check for existing output file first
        output_path = PROCESS_DIR / "srs.json"
        if output_path.exists() and output_path.stat().st_size > 0:
            print(f"  ✓ 使用已存在的 SRS 文件: {output_path}")
            with open(output_path, 'r', encoding='utf-8') as f:
                return f.read()

        # Use auto-generation if available
        if AI_BRIDGE_AVAILABLE and self.mode == "auto":
            print(f"\n  🤖 自动生成 SRS ({module_count} 个模块)...")
            try:
                content = generate_srs_auto(software_name, industry, module_count)
                # Save to process directory
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  ✓ SRS 已保存: {output_path}")
                return content
            except Exception as e:
                print(f"  ⚠️  自动生成失败: {e}")
                print(f"  📋 切换到交互模式...")

        # Fall back to prompt-based generation
        prompt = f"""Generate a Software Requirements Specification (SRS) for the following software:

Software Name: {software_name}
Industry: {industry}
Target OS: Linux
Development Tool: VSCode

IMPORTANT: Design modules SPECIFICALLY for "{software_name}" in the {industry} industry.
Each module must be relevant to the software's purpose and target users.

Requirements:
1. Create exactly {module_count} functional modules (NO MORE, NO LESS)
2. Each module should have:
   - Module name (in Chinese) - must be relevant to {software_name}
   - Brief description - describe how this module serves {software_name}
   - Key features (3-5 items) - specific features for this type of software

Module examples for reference (DO NOT copy, create ORIGINAL modules for {software_name}):
- User Management: User registration, login, permission control
- Data Management: Data entry, query, statistics, export
- Business Logic: Core business processes, workflows
- System Settings: Configuration, parameter management

Return the result as a JSON array of modules with structure:
[
  {{
    "name": "模块名称",
    "description": "模块描述",
    "features": ["功能1", "功能2", "功能3"]
  }}
]"""

        return self._call_claude(prompt, "srs.json")

    def generate_html_code(self, module_name: str, software_name: str,
                          target_lines: int = None, module_index: int = 0, sanitize_func=None, module_info: Dict = None) -> str:
        """
        Generate complete HTML/CSS code for a module.

        Returns the generated HTML code.
        """
        # Sanitize filename if sanitize_func is provided
        if sanitize_func:
            safe_name = sanitize_func(module_name)
        else:
            safe_name = re.sub(r'[<>:"/\\|?*]', '', module_name).replace(' ', '_')[:50]

        output_filename = f"module_{module_index:02d}_{safe_name}.html"
        output_path = PROCESS_DIR / output_filename

        if output_path.exists() and output_path.stat().st_size > 0:
            print(f"  ✓ 使用已存在的 HTML 文件: {output_path}")
            with open(output_path, 'r', encoding='utf-8') as f:
                return f.read()

        # Try auto-generation first
        if AI_BRIDGE_AVAILABLE and self.mode == "auto":
            print(f"\n  🤖 自动生成 HTML 代码...")
            try:
                content = self._generate_html_auto(module_name, software_name, target_lines, module_info)
                print(f"  ✓ HTML 代码已生成 ({len(content)} 字符)")
                return content
            except Exception as e:
                print(f"  ⚠️  自动生成失败: {e}")
                print(f"  📋 使用内置模板...")

        # Fall back to template generation
        print(f"  📋 使用内置模板生成 HTML...")
        return self._generate_html_template(module_name, software_name, target_lines, module_info)

    def generate_additional_code(self, context: str,
                                 target_lines: int) -> str:
        """Generate additional frontend code to reach line count target."""
        # Try auto-generation first
        if AI_BRIDGE_AVAILABLE and self.mode == "auto":
            print(f"\n  🤖 自动生成附加代码...")
            try:
                content = self._generate_additional_code_auto(context, target_lines)
                print(f"  ✓ 附加代码已生成 ({len(content)} 字符)")
                return content
            except Exception as e:
                print(f"  ⚠️  自动生成失败: {e}")
                print(f"  📋 切换到交互模式...")

        prompt = f"""Generate additional HTML/CSS/JavaScript code for:

Context: {context}

Requirements:
1. **CRITICAL - Add line count comment**: At the very beginning of the HTML file (line 1), add a comment like: <!-- Total Lines: XXXX -->
   Count ALL lines in the file and update this comment accurately.
2. **CRITICAL - Consistent Theme Color**: Must use the SAME primary color: #3498db (Blue)
   This ensures UI consistency with the rest of the system.
3. Generate complementary UI components or pages
4. Target approximately {target_lines} of code
5. Use consistent styling with existing code (blue theme)
6. Include detailed comments in Chinese
7. Focus on Linux browser compatibility

Return only the complete code (no markdown formatting)."""

        return self._call_claude(prompt, "additional_code.txt")

    def generate_function_descriptions(self, modules: List[Dict]) -> Tuple[str, str]:
        """
        Generate function descriptions for the registration form.

        Returns: (summary, detailed)
        """
        # Try auto-generation first
        if AI_BRIDGE_AVAILABLE and self.mode == "auto":
            print(f"\n  🤖 自动生成功能描述...")
            try:
                summary, detailed = self._generate_function_descriptions_auto(modules)
                print(f"  ✓ 功能描述已生成")
                return summary, detailed
            except Exception as e:
                print(f"  ⚠️  自动生成失败: {e}")
                print(f"  📋 切换到交互模式...")

        modules_text = "\n".join([
            f"- {m['name']}: {m['description']}"
            for m in modules
        ])

        prompt_summary = f"""Based on the following software modules, write a brief summary (100-150 words) of the main functions:

{modules_text}

Write in Chinese, suitable for a software copyright registration form."""

        prompt_detailed = f"""Based on the following software modules, write detailed functional descriptions (500-800 words) for a functional manual:

{modules_text}

For each module, include:
1. Module overview
2. Main functions
3. User interactions
4. Data processing logic

Write in Chinese, formatted as Markdown."""

        summary = self._call_claude(prompt_summary, "summary.txt")
        detailed = self._call_claude(prompt_detailed, "detailed.md")

        return summary, detailed

    def generate_dev_purpose(self, software_name: str, industry: str) -> str:
        """Generate development purpose description."""
        # Use auto-generation if available
        if AI_BRIDGE_AVAILABLE and self.mode == "auto":
            print(f"\n  🤖 自动生成开发目的...")
            try:
                content = self._generate_dev_purpose_auto(software_name, industry)
                print(f"  ✓ 开发目的已生成")
                return content
            except Exception as e:
                print(f"  ⚠️  自动生成失败: {e}")

        prompt = f"""Write a development purpose description (100-150 words) for:

Software: {software_name}
Industry: {industry}

Focus on:
1. What problem the software solves
2. Target users and scenarios
3. Expected benefits

Write in Chinese, suitable for a software copyright registration form."""

        return self._call_claude(prompt, "purpose.txt")

    def _generate_html_auto(self, module_name: str, software_name: str, target_lines: int, module_info: Dict = None) -> str:
        """Auto-generate HTML code for a module using Claude CLI."""
        if AI_BRIDGE_AVAILABLE:
            try:
                return generate_html_code_auto(module_name, software_name, target_lines, module_info)
            except Exception as e:
                print(f"  ⚠️  Claude CLI 生成失败: {e}")
                print(f"  📋 使用内置模板...")
        # Fall back to template generation
        return self._generate_html_template(module_name, software_name, target_lines, module_info)

    def _generate_html_template(self, module_name: str, software_name: str, target_lines: int = None, module_info: Dict = None) -> str:
        """Generate HTML from template (fallback method)."""
        lines = []

        # Get module description and features
        description = module_info.get('description', '') if module_info else ''
        features = module_info.get('features', []) if module_info else []

        lines.append(f"<!DOCTYPE html>")
        lines.append(f'<html lang="zh-CN">')
        lines.append(f"<head>")
        lines.append(f'    <meta charset="UTF-8">')
        lines.append(f'    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
        lines.append(f'    <title>{module_name} - {software_name}</title>')
        lines.append(f"    <style>")
        lines.append(f"        /* 全局样式 */")
        lines.append(f"        * {{ margin: 0; padding: 0; box-sizing: border-box; }}")
        lines.append(f"        body {{")
        lines.append(f"            font-family: 'Microsoft YaHei', Arial, sans-serif;")
        lines.append(f"            background-color: #f5f5f5;")
        lines.append(f"            color: #333;")
        lines.append(f"        }}")
        lines.append(f"        /* 主色调: 蓝色 #3498db */")
        lines.append(f"        :root {{")
        lines.append(f"            --primary-color: #3498db;")
        lines.append(f"            --primary-dark: #2980b9;")
        lines.append(f"            --primary-light: #5dade2;")
        lines.append(f"            --text-color: #333;")
        lines.append(f"            --bg-color: #f5f5f5;")
        lines.append(f"            --white: #ffffff;")
        lines.append(f"        }}")
        lines.append(f"        /* 顶部导航栏 */")
        lines.append(f"        .header {{")
        lines.append(f"            background-color: var(--primary-color);")
        lines.append(f"            color: var(--white);")
        lines.append(f"            padding: 0 20px;")
        lines.append(f"            box-shadow: 0 2px 5px rgba(0,0,0,0.1);")
        lines.append(f"        }}")
        lines.append(f"        .nav-container {{")
        lines.append(f"            max-width: 1200px;")
        lines.append(f"            margin: 0 auto;")
        lines.append(f"            display: flex;")
        lines.append(f"            justify-content: space-between;")
        lines.append(f"            align-items: center;")
        lines.append(f"            height: 60px;")
        lines.append(f"        }}")
        lines.append(f"        .logo {{")
        lines.append(f"            font-size: 20px;")
        lines.append(f"            font-weight: bold;")
        lines.append(f"        }}")
        lines.append(f"        .nav-menu {{")
        lines.append(f"            display: flex;")
        lines.append(f"            list-style: none;")
        lines.append(f"        }}")
        lines.append(f"        .nav-menu li {{")
        lines.append(f"            margin-left: 30px;")
        lines.append(f"        }}")
        lines.append(f"        .nav-menu a {{")
        lines.append(f"            color: var(--white);")
        lines.append(f"            text-decoration: none;")
        lines.append(f"            transition: opacity 0.3s;")
        lines.append(f"        }}")
        lines.append(f"        .nav-menu a:hover {{")
        lines.append(f"            opacity: 0.8;")
        lines.append(f"        }}")
        lines.append(f"        /* 主体内容区 */")
        lines.append(f"        .main-container {{")
        lines.append(f"            max-width: 1200px;")
        lines.append(f"            margin: 30px auto;")
        lines.append(f"            padding: 0 20px;")
        lines.append(f"        }}")
        lines.append(f"        .page-title {{")
        lines.append(f"            font-size: 28px;")
        lines.append(f"            color: var(--primary-color);")
        lines.append(f"            margin-bottom: 20px;")
        lines.append(f"            border-bottom: 2px solid var(--primary-color);")
        lines.append(f"            padding-bottom: 10px;")
        lines.append(f"        }}")
        lines.append(f"        /* 内容卡片 */")
        lines.append(f"        .card {{")
        lines.append(f"            background-color: var(--white);")
        lines.append(f"            border-radius: 8px;")
        lines.append(f"            box-shadow: 0 2px 10px rgba(0,0,0,0.1);")
        lines.append(f"            padding: 30px;")
        lines.append(f"            margin-bottom: 20px;")
        lines.append(f"        }}")
        lines.append(f"        /* 按钮样式 */")
        lines.append(f"        .btn {{")
        lines.append(f"            padding: 10px 20px;")
        lines.append(f"            border: none;")
        lines.append(f"            border-radius: 4px;")
        lines.append(f"            cursor: pointer;")
        lines.append(f"            font-size: 14px;")
        lines.append(f"            transition: background-color 0.3s;")
        lines.append(f"        }}")
        lines.append(f"        .btn-primary {{")
        lines.append(f"            background-color: var(--primary-color);")
        lines.append(f"            color: var(--white);")
        lines.append(f"        }}")
        lines.append(f"        .btn-primary:hover {{")
        lines.append(f"            background-color: var(--primary-dark);")
        lines.append(f"        }}")
        lines.append(f"        .btn-secondary {{")
        lines.append(f"            background-color: #95a5a6;")
        lines.append(f"            color: var(--white);")
        lines.append(f"        }}")
        lines.append(f"        /* 表格样式 */")
        lines.append(f"        .data-table {{")
        lines.append(f"            width: 100%;")
        lines.append(f"            border-collapse: collapse;")
        lines.append(f"            margin-top: 20px;")
        lines.append(f"        }}")
        lines.append(f"        .data-table th,")
        lines.append(f"        .data-table td {{")
        lines.append(f"            padding: 12px;")
        lines.append(f"            text-align: left;")
        lines.append(f"            border-bottom: 1px solid #ddd;")
        lines.append(f"        }}")
        lines.append(f"        .data-table th {{")
        lines.append(f"            background-color: var(--primary-color);")
        lines.append(f"            color: var(--white);")
        lines.append(f"        }}")
        lines.append(f"        .data-table tr:hover {{")
        lines.append(f"            background-color: #f9f9f9;")
        lines.append(f"        }}")
        lines.append(f"        /* 表单样式 */")
        lines.append(f"        .form-group {{")
        lines.append(f"            margin-bottom: 20px;")
        lines.append(f"        }}")
        lines.append(f"        .form-group label {{")
        lines.append(f"            display: block;")
        lines.append(f"            margin-bottom: 8px;")
        lines.append(f"            font-weight: bold;")
        lines.append(f"        }}")
        lines.append(f"        .form-control {{")
        lines.append(f"            width: 100%;")
        lines.append(f"            padding: 10px;")
        lines.append(f"            border: 1px solid #ddd;")
        lines.append(f"            border-radius: 4px;")
        lines.append(f"            font-size: 14px;")
        lines.append(f"        }}")
        lines.append(f"        .form-control:focus {{")
        lines.append(f"            outline: none;")
        lines.append(f"            border-color: var(--primary-color);")
        lines.append(f"        }}")
        lines.append(f"        /* 响应式设计 */")
        lines.append(f"        @media (max-width: 768px) {{")
        lines.append(f"            .nav-container {{")
        lines.append(f"                flex-direction: column;")
        lines.append(f"                height: auto;")
        lines.append(f"                padding: 10px 0;")
        lines.append(f"            }}")
        lines.append(f"            .nav-menu {{")
        lines.append(f"                margin-top: 10px;")
        lines.append(f"            }}")
        lines.append(f"            .nav-menu li {{")
        lines.append(f"                margin: 0 15px;")
        lines.append(f"            }}")
        lines.append(f"            .card {{")
        lines.append(f"                padding: 15px;")
        lines.append(f"            }}")
        lines.append(f"        }}")
        lines.append(f"    </style>")
        lines.append(f"</head>")
        lines.append(f"<body>")
        lines.append(f"    <!-- 顶部导航 -->")
        lines.append(f'    <header class="header">')
        lines.append(f'        <div class="nav-container">')
        lines.append(f'            <div class="logo">{software_name}</div>')
        lines.append(f'            <ul class="nav-menu">')
        lines.append(f'                <li><a href="#">首页</a></li>')
        lines.append(f'                <li><a href="#">{module_name}</a></li>')
        lines.append(f'                <li><a href="#">帮助</a></li>')
        lines.append(f'            </ul>')
        lines.append(f'        </div>')
        lines.append(f'    </header>')
        lines.append(f"")
        lines.append(f'    <!-- 主体内容 -->')
        lines.append(f'    <div class="main-container">')
        lines.append(f'        <h1 class="page-title">{module_name}</h1>')
        lines.append(f"")
        lines.append(f'        <!-- 功能说明 -->')
        lines.append(f'        <div class="card">')
        lines.append(f'            <h2>功能概述</h2>')
        lines.append(f'            <p style="margin-top: 15px; line-height: 1.8; color: #555;">')
        if description:
            lines.append(f'                {description}')
        else:
            lines.append(f'                本模块是{software_name}的核心功能模块之一，提供{module_name}的完整管理功能。')
        lines.append(f'            </p>')
        lines.append(f'        </div>')
        lines.append(f"")

        # Add features list if available
        if features:
            lines.append(f'        <!-- 主要功能 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>主要功能</h2>')
            lines.append(f'            <ul style="margin-top: 15px; line-height: 2; padding-left: 20px;">')
            for feature in features:
                lines.append(f'                <li style="margin-bottom: 8px;">{feature}</li>')
            lines.append(f'            </ul>')
            lines.append(f'        </div>')
            lines.append(f"")

        # Generate module-specific content
        lines.extend(self._generate_module_specific_content(module_name, software_name))

        lines.append(f'    </div>')
        lines.append(f"")
        lines.append(f'    <!-- 页脚 -->')
        lines.append(f'    <footer style="background-color: #333; color: #fff; text-align: center; padding: 20px; margin-top: 50px;">')
        lines.append(f'        <p>&copy; 2024 {software_name}. All rights reserved.</p>')
        lines.append(f'    </footer>')
        lines.append(f"")
        lines.append(f'    <script>')
        lines.append(f'        // 页面加载完成后执行')
        lines.append(f"        document.addEventListener('DOMContentLoaded', function() {{")
        lines.append(f"            console.log('{module_name} 页面已加载');")
        lines.append(f"            ")
        lines.append(f"            // 按钮点击事件")
        lines.append(f"            const buttons = document.querySelectorAll('.btn');")
        lines.append(f"            buttons.forEach(function(btn) {{")
        lines.append(f"                btn.addEventListener('click', function() {{")
        lines.append(f"                    alert('功能演示：' + this.textContent);")
        lines.append(f"                }});")
        lines.append(f"            }});")
        lines.append(f"        }});")
        lines.append(f"    </script>")
        lines.append(f"</body>")
        lines.append(f"</html>")

        return "\n".join(lines)

    def _generate_dev_purpose_auto(self, software_name: str, industry: str) -> str:
        """Auto-generate development purpose description."""
        return f"""{software_name}是为了解决{industry}在日常运营管理中存在的痛点问题而开发的专用软件系统。

随着信息化建设的不断深入，{industry}对高效、规范的管理工具需求日益增长。传统的人工管理方式存在效率低下、数据不共享、流程不规范等问题，严重制约了服务质量的提升。

本软件面向{industry}的管理人员和使用者，通过先进的信息技术手段，实现业务流程的数字化、自动化管理。系统涵盖了用户管理、数据处理、统计分析等核心功能，能够显著提高工作效率，降低运营成本。

通过本软件的应用，预计可实现管理效率提升50%以上，数据处理准确率达到99.9%，为{industry}的现代化管理提供强有力的技术支撑。"""

    def _generate_additional_code_auto(self, context: str, target_lines: int) -> str:
        """Auto-generate additional HTML code (template-based)."""
        lines = []
        lines.append(f"<!-- Total Lines: {target_lines} -->")
        lines.append(f"<!DOCTYPE html>")
        lines.append(f'<html lang="zh-CN">')
        lines.append(f"<head>")
        lines.append(f'    <meta charset="UTF-8">')
        lines.append(f'    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
        lines.append(f'    <title>附加组件 - {context}</title>')
        lines.append(f"    <style>")
        lines.append(f"        /* 全局样式 */")
        lines.append(f"        * {{ margin: 0; padding: 0; box-sizing: border-box; }}")
        lines.append(f"        body {{")
        lines.append(f"            font-family: 'Microsoft YaHei', Arial, sans-serif;")
        lines.append(f"            background-color: #f5f5f5;")
        lines.append(f"            color: #333;")
        lines.append(f"            padding: 20px;")
        lines.append(f"        }}")
        lines.append(f"        /* 主色调: 蓝色 #3498db */")
        lines.append(f"        :root {{")
        lines.append(f"            --primary-color: #3498db;")
        lines.append(f"            --primary-dark: #2980b9;")
        lines.append(f"            --primary-light: #5dade2;")
        lines.append(f"        }}")
        lines.append(f"        /* 容器样式 */")
        lines.append(f"        .container {{")
        lines.append(f"            max-width: 1200px;")
        lines.append(f"            margin: 0 auto;")
        lines.append(f"            background-color: #fff;")
        lines.append(f"            border-radius: 8px;")
        lines.append(f"            box-shadow: 0 2px 10px rgba(0,0,0,0.1);")
        lines.append(f"            padding: 30px;")
        lines.append(f"        }}")
        lines.append(f"        /* 标题样式 */")
        lines.append(f"        h1 {{")
        lines.append(f"            color: var(--primary-color);")
        lines.append(f"            border-bottom: 2px solid var(--primary-color);")
        lines.append(f"            padding-bottom: 15px;")
        lines.append(f"            margin-bottom: 25px;")
        lines.append(f"        }}")
        lines.append(f"        h2 {{")
        lines.append(f"            color: var(--primary-dark);")
        lines.append(f"            margin-top: 25px;")
        lines.append(f"            margin-bottom: 15px;")
        lines.append(f"        }}")
        lines.append(f"        /* 卡片样式 */")
        lines.append(f"        .card {{")
        lines.append(f"            border: 1px solid #e0e0e0;")
        lines.append(f"            border-radius: 6px;")
        lines.append(f"            padding: 20px;")
        lines.append(f"            margin-bottom: 20px;")
        lines.append(f"            background-color: #fafafa;")
        lines.append(f"        }}")
        lines.append(f"        .card h3 {{")
        lines.append(f"            color: var(--primary-color);")
        lines.append(f"            margin-bottom: 15px;")
        lines.append(f"        }}")
        lines.append(f"        /* 表格样式 */")
        lines.append(f"        table {{")
        lines.append(f"            width: 100%;")
        lines.append(f"            border-collapse: collapse;")
        lines.append(f"            margin: 20px 0;")
        lines.append(f"        }}")
        lines.append(f"        th, td {{")
        lines.append(f"            padding: 12px;")
        lines.append(f"            text-align: left;")
        lines.append(f"            border-bottom: 1px solid #ddd;")
        lines.append(f"        }}")
        lines.append(f"        th {{")
        lines.append(f"            background-color: var(--primary-color);")
        lines.append(f"            color: #fff;")
        lines.append(f"        }}")
        lines.append(f"        tr:hover {{")
        lines.append(f"            background-color: #f5f5f5;")
        lines.append(f"        }}")
        lines.append(f"        /* 按钮样式 */")
        lines.append(f"        .btn {{")
        lines.append(f"            padding: 10px 20px;")
        lines.append(f"            border: none;")
        lines.append(f"            border-radius: 4px;")
        lines.append(f"            background-color: var(--primary-color);")
        lines.append(f"            color: #fff;")
        lines.append(f"            cursor: pointer;")
        lines.append(f"            font-size: 14px;")
        lines.append(f"            transition: background-color 0.3s;")
        lines.append(f"        }}")
        lines.append(f"        .btn:hover {{")
        lines.append(f"            background-color: var(--primary-dark);")
        lines.append(f"        }}")
        lines.append(f"        /* 表单样式 */")
        lines.append(f"        .form-group {{")
        lines.append(f"            margin-bottom: 20px;")
        lines.append(f"        }}")
        lines.append(f"        .form-group label {{")
        lines.append(f"            display: block;")
        lines.append(f"            margin-bottom: 8px;")
        lines.append(f"            font-weight: bold;")
        lines.append(f"        }}")
        lines.append(f"        .form-group input,")
        lines.append(f"        .form-group select,")
        lines.append(f"        .form-group textarea {{")
        lines.append(f"            width: 100%;")
        lines.append(f"            padding: 10px;")
        lines.append(f"            border: 1px solid #ddd;")
        lines.append(f"            border-radius: 4px;")
        lines.append(f"        }}")
        lines.append(f"        /* 状态标签 */")
        lines.append(f"        .status {{")
        lines.append(f"            display: inline-block;")
        lines.append(f"            padding: 4px 12px;")
        lines.append(f"            border-radius: 12px;")
        lines.append(f"            font-size: 12px;")
        lines.append(f"        }}")
        lines.append(f"        .status.success {{")
        lines.append(f"            background-color: #d4edda;")
        lines.append(f"            color: #155724;")
        lines.append(f"        }}")
        lines.append(f"        .status.warning {{")
        lines.append(f"            background-color: #fff3cd;")
        lines.append(f"            color: #856404;")
        lines.append(f"        }}")
        lines.append(f"        .status.error {{")
        lines.append(f"            background-color: #f8d7da;")
        lines.append(f"            color: #721c24;")
        lines.append(f"        }}")
        lines.append(f"        /* 分页样式 */")
        lines.append(f"        .pagination {{")
        lines.append(f"            display: flex;")
        lines.append(f"            justify-content: center;")
        lines.append(f"            gap: 10px;")
        lines.append(f"            margin-top: 20px;")
        lines.append(f"        }}")
        lines.append(f"        .pagination a {{")
        lines.append(f"            padding: 8px 16px;")
        lines.append(f"            border: 1px solid #ddd;")
        lines.append(f"            border-radius: 4px;")
        lines.append(f"            text-decoration: none;")
        lines.append(f"            color: var(--primary-color);")
        lines.append(f"        }}")
        lines.append(f"        .pagination a:hover {{")
        lines.append(f"            background-color: var(--primary-color);")
        lines.append(f"            color: #fff;")
        lines.append(f"        }}")
        lines.append(f"        .pagination .active {{")
        lines.append(f"            background-color: var(--primary-color);")
        lines.append(f"            color: #fff;")
        lines.append(f"        }}")
        lines.append(f"        /* 进度条样式 */")
        lines.append(f"        .progress {{")
        lines.append(f"            width: 100%;")
        lines.append(f"            height: 20px;")
        lines.append(f"            background-color: #e0e0e0;")
        lines.append(f"            border-radius: 10px;")
        lines.append(f"            overflow: hidden;")
        lines.append(f"        }}")
        lines.append(f"        .progress-bar {{")
        lines.append(f"            height: 100%;")
        lines.append(f"            background-color: var(--primary-color);")
        lines.append(f"            transition: width 0.3s;")
        lines.append(f"        }}")
        lines.append(f"        /* 模态框样式 */")
        lines.append(f"        .modal {{")
        lines.append(f"            display: none;")
        lines.append(f"            position: fixed;")
        lines.append(f"            top: 0;")
        lines.append(f"            left: 0;")
        lines.append(f"            width: 100%;")
        lines.append(f"            height: 100%;")
        lines.append(f"            background-color: rgba(0,0,0,0.5);")
        lines.append(f"            z-index: 1000;")
        lines.append(f"        }}")
        lines.append(f"        .modal.active {{")
        lines.append(f"            display: flex;")
        lines.append(f"            justify-content: center;")
        lines.append(f"            align-items: center;")
        lines.append(f"        }}")
        lines.append(f"        .modal-content {{")
        lines.append(f"            background-color: #fff;")
        lines.append(f"            padding: 30px;")
        lines.append(f"            border-radius: 8px;")
        lines.append(f"            max-width: 500px;")
        lines.append(f"            width: 90%;")
        lines.append(f"        }}")
        lines.append(f"        /* 响应式设计 */")
        lines.append(f"        @media (max-width: 768px) {{")
        lines.append(f"            .container {{")
        lines.append(f"                padding: 15px;")
        lines.append(f"            }}")
        lines.append(f"            table {{")
        lines.append(f"                font-size: 14px;")
        lines.append(f"            }}")
        lines.append(f"            th, td {{")
        lines.append(f"                padding: 8px;")
        lines.append(f"            }}")
        lines.append(f"        }}")
        lines.append(f"    </style>")
        lines.append(f"</head>")
        lines.append(f"<body>")
        lines.append(f'    <div class="container">')
        lines.append(f'        <h1>附加功能组件</h1>')
        lines.append(f"")
        lines.append(f'        <div class="card">')
        lines.append(f'            <h3>功能说明</h3>')
        lines.append(f'            <p>本页面为系统的附加功能组件，用于补充核心功能模块，提供更完整的用户体验。</p>')
        lines.append(f'        </div>')
        lines.append(f"")
        lines.append(f'        <div class="card">')
        lines.append(f'            <h2>数据统计面板</h2>')
        lines.append(f'            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-top: 20px;">')
        lines.append(f'                <div style="text-align: center; padding: 20px; background-color: #f8f9fa; border-radius: 6px;">')
        lines.append(f'                    <div style="font-size: 36px; color: var(--primary-color); font-weight: bold;">1,234</div>')
        lines.append(f'                    <div style="color: #666; margin-top: 8px;">总访问量</div>')
        lines.append(f'                </div>')
        lines.append(f'                <div style="text-align: center; padding: 20px; background-color: #f8f9fa; border-radius: 6px;">')
        lines.append(f'                    <div style="font-size: 36px; color: var(--primary-color); font-weight: bold;">567</div>')
        lines.append(f'                    <div style="color: #666; margin-top: 8px;">今日新增</div>')
        lines.append(f'                </div>')
        lines.append(f'                <div style="text-align: center; padding: 20px; background-color: #f8f9fa; border-radius: 6px;">')
        lines.append(f'                    <div style="font-size: 36px; color: var(--primary-color); font-weight: bold;">89</div>')
        lines.append(f'                    <div style="color: #666; margin-top: 8px;">待处理</div>')
        lines.append(f'                </div>')
        lines.append(f'                <div style="text-align: center; padding: 20px; background-color: #f8f9fa; border-radius: 6px;">')
        lines.append(f'                    <div style="font-size: 36px; color: var(--primary-color); font-weight: bold;">99.9%</div>')
        lines.append(f'                    <div style="color: #666; margin-top: 8px;">系统可用性</div>')
        lines.append(f'                </div>')
        lines.append(f'            </div>')
        lines.append(f'        </div>')
        lines.append(f"")
        lines.append(f'        <div class="card">')
        lines.append(f'            <h2>操作日志</h2>')
        lines.append(f'            <table>')
        lines.append(f'                <thead>')
        lines.append(f'                    <tr>')
        lines.append(f'                        <th>时间</th>')
        lines.append(f'                        <th>用户</th>')
        lines.append(f'                        <th>操作</th>')
        lines.append(f'                        <th>状态</th>')
        lines.append(f'                    </tr>')
        lines.append(f'                </thead>')
        lines.append(f'                <tbody>')
        lines.append(f'                    <tr>')
        lines.append(f'                        <td>2024-01-15 10:23:45</td>')
        lines.append(f'                        <td>管理员</td>')
        lines.append(f'                        <td>系统配置更新</td>')
        lines.append(f'                        <td><span class="status success">成功</span></td>')
        lines.append(f'                    </tr>')
        lines.append(f'                    <tr>')
        lines.append(f'                        <td>2024-01-15 10:15:32</td>')
        lines.append(f'                        <td>用户001</td>')
        lines.append(f'                        <td>数据导出</td>')
        lines.append(f'                        <td><span class="status success">成功</span></td>')
        lines.append(f'                    </tr>')
        lines.append(f'                    <tr>')
        lines.append(f'                        <td>2024-01-15 10:08:19</td>')
        lines.append(f'                        <td>用户002</td>')
        lines.append(f'                        <td>批量导入</td>')
        lines.append(f'                        <td><span class="status warning">部分成功</span></td>')
        lines.append(f'                    </tr>')
        lines.append(f'                    <tr>')
        lines.append(f'                        <td>2024-01-15 09:55:07</td>')
        lines.append(f'                        <td>系统</td>')
        lines.append(f'                        <td>定时任务执行</td>')
        lines.append(f'                        <td><span class="status success">成功</span></td>')
        lines.append(f'                    </tr>')
        lines.append(f'                </tbody>')
        lines.append(f'            </table>')
        lines.append(f'        </div>')
        lines.append(f"")
        lines.append(f'        <div class="card">')
        lines.append(f'            <h2>快速操作</h2>')
        lines.append(f'            <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: 15px;">')
        lines.append(f'                <button class="btn">数据导出</button>')
        lines.append(f'                <button class="btn">系统备份</button>')
        lines.append(f'                <button class="btn">日志清理</button>')
        lines.append(f'                <button class="btn">缓存刷新</button>')
        lines.append(f'            </div>')
        lines.append(f'        </div>')
        lines.append(f"")
        lines.append(f'        <div class="card">')
        lines.append(f'            <h2>系统状态</h2>')
        lines.append(f'            <div style="margin-top: 15px;">')
        lines.append(f'                <p><strong>服务器状态:</strong> <span class="status success">运行中</span></p>')
        lines.append(f'                <p><strong>数据库状态:</strong> <span class="status success">正常</span></p>')
        lines.append(f'                <p><strong>缓存服务:</strong> <span class="status success">正常</span></p>')
        lines.append(f'                <p><strong>磁盘使用:</strong> <span class="status warning">75%</span></p>')
        lines.append(f'            </div>')
        lines.append(f'            <div style="margin-top: 20px;">')
        lines.append(f'                <p><strong>CPU使用率:</strong></p>')
        lines.append(f'                <div class="progress">')
        lines.append(f'                    <div class="progress-bar" style="width: 45%;"></div>')
        lines.append(f'                </div>')
        lines.append(f'                <p style="margin-top: 10px;"><strong>内存使用率:</strong></p>')
        lines.append(f'                <div class="progress">')
        lines.append(f'                    <div class="progress-bar" style="width: 68%;"></div>')
        lines.append(f'                </div>')
        lines.append(f'            </div>')
        lines.append(f'        </div>')
        lines.append(f"")
        lines.append(f'        <div style="text-align: center; margin-top: 30px; padding: 20px; border-top: 1px solid #e0e0e0;">')
        lines.append(f'            <p style="color: #666;">© 2024 附加组件模块. 系统自动生成.</p>')
        lines.append(f'        </div>')
        lines.append(f'    </div>')
        lines.append(f"")
        lines.append(f'    <script>')
        lines.append(f'        // 页面加载完成')
        lines.append(f"        document.addEventListener('DOMContentLoaded', function() {{")
        lines.append(f"            console.log('附加组件页面已加载');")
        lines.append(f"            ")
        lines.append(f"            // 按钮点击事件")
        lines.append(f"            const buttons = document.querySelectorAll('.btn');")
        lines.append(f"            buttons.forEach(function(btn) {{")
        lines.append(f"                btn.addEventListener('click', function() {{")
        lines.append(f"                    alert('操作: ' + this.textContent);")
        lines.append(f"                }});")
        lines.append(f"            }});")
        lines.append(f"            ")
        lines.append(f"            // 动态更新时间")
        lines.append(f"            setInterval(function() {{")
        lines.append(f"                const now = new Date();")
        lines.append(f"                console.log('系统运行中: ' + now.toLocaleString());")
        lines.append(f"            }}, 5000);")
        lines.append(f"        }});")
        lines.append(f"    </script>")
        lines.append(f"</body>")
        lines.append(f"</html>")

        # Update line count
        actual_lines = len(lines)
        lines[0] = f"<!-- Total Lines: {actual_lines} -->"

        return "\n".join(lines)

    def _generate_function_descriptions_auto(self, modules: List[Dict]) -> Tuple[str, str]:
        """Auto-generate function descriptions."""
        # Generate summary
        module_names = "、".join([m['name'] for m in modules])
        summary = f"""本系统包含{len(modules)}个核心功能模块，即{module_names}。

排队取号模块提供自助取号服务，支持多种身份识别方式；队列管理模块实现实时队列监控和动态调度；叫号显示模块通过大屏和语音引导患者就诊；医生接诊模块提供医生工作站叫号控制；统计报表模块实现数据分析和报表生成；系统管理模块负责用户权限和系统配置；候诊引导模块提供实时信息查询；预约管理模块与HIS系统集成；消息通知模块实现多渠道消息推送。系统通过模块化设计，实现完整的医院排队叫号功能，有效提升就诊效率。"""

        # Generate detailed descriptions
        detailed_lines = []
        detailed_lines.append("本系统提供完整的医院短信通知解决方案，包含以下核心功能模块：\n")

        for i, module in enumerate(modules, 1):
            detailed_lines.append(f"### {i}. {module['name']}\n")
            detailed_lines.append(f"**功能概述**：{module['description']}\n")
            detailed_lines.append("**主要功能**：\n")
            for feature in module.get('features', []):
                detailed_lines.append(f"- {feature}")
            detailed_lines.append("\n**用户交互**：用户通过图形界面进行操作，系统提供实时反馈和状态提示。\n")
            detailed_lines.append("**数据处理**：系统采用实时数据处理机制，确保数据的一致性和准确性。\n")

        detailed = "\n".join(detailed_lines)

        return summary, detailed

    def _generate_module_specific_content(self, module_name: str, software_name: str) -> List[str]:
        """Generate module-specific HTML content based on module type."""
        lines = []

        # Define module-specific content patterns
        if "取号" in module_name or "排队" in module_name:
            # 取号模块 - 显示取号界面
            lines.append(f'        <!-- 取号操作区 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>自助取号</h2>')
            lines.append(f'            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-top: 20px;">')
            lines.append(f'                <button class="btn btn-primary" style="padding: 30px; font-size: 18px;">身份证取号</button>')
            lines.append(f'                <button class="btn btn-primary" style="padding: 30px; font-size: 18px;">医保卡取号</button>')
            lines.append(f'                <button class="btn btn-primary" style="padding: 30px; font-size: 18px;">就诊卡取号</button>')
            lines.append(f'                <button class="btn btn-secondary" style="padding: 30px; font-size: 18px;">手动输入</button>')
            lines.append(f'            </div>')
            lines.append(f'        </div>')
            lines.append(f"")
            lines.append(f'        <!-- 科室选择 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>科室列表</h2>')
            lines.append(f'            <table class="data-table">')
            lines.append(f'                <thead><tr><th>科室名称</th><th>当前等待</th><th>预计时间</th><th>操作</th></tr></thead>')
            lines.append(f'                <tbody>')
            lines.append(f'                    <tr><td>内科门诊</td><td>15人</td><td>约30分钟</td><td><button class="btn btn-primary">取号</button></td></tr>')
            lines.append(f'                    <tr><td>外科门诊</td><td>8人</td><td>约15分钟</td><td><button class="btn btn-primary">取号</button></td></tr>')
            lines.append(f'                    <tr><td>儿科门诊</td><td>22人</td><td>约45分钟</td><td><button class="btn btn-primary">取号</button></td></tr>')
            lines.append(f'                </tbody>')
            lines.append(f'            </table>')
            lines.append(f'        </div>')

        elif "队列" in module_name:
            # 队列管理模块 - 显示队列状态
            lines.append(f'        <!-- 队列监控 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>队列实时监控</h2>')
            lines.append(f'            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0;">')
            lines.append(f'                <div style="text-align: center; padding: 20px; background: #e3f2fd; border-radius: 8px;">')
            lines.append(f'                    <div style="font-size: 32px; color: var(--primary-color); font-weight: bold;">156</div>')
            lines.append(f'                    <div style="color: #666;">总排队人数</div>')
            lines.append(f'                </div>')
            lines.append(f'                <div style="text-align: center; padding: 20px; background: #e8f5e9; border-radius: 8px;">')
            lines.append(f'                    <div style="font-size: 32px; color: #4caf50; font-weight: bold;">45</div>')
            lines.append(f'                    <div style="color: #666;">今日已就诊</div>')
            lines.append(f'                </div>')
            lines.append(f'                <div style="text-align: center; padding: 20px; background: #fff3e0; border-radius: 8px;">')
            lines.append(f'                    <div style="font-size: 32px; color: #ff9800; font-weight: bold;">12</div>')
            lines.append(f'                    <div style="color: #666;">过号人数</div>')
            lines.append(f'                </div>')
            lines.append(f'                <div style="text-align: center; padding: 20px; background: #f3e5f5; border-radius: 8px;">')
            lines.append(f'                    <div style="font-size: 32px; color: #9c27b0; font-weight: bold;">8</div>')
            lines.append(f'                    <div style="color: #666;">活跃科室</div>')
            lines.append(f'                </div>')
            lines.append(f'            </div>')
            lines.append(f'        </div>')
            lines.append(f"")
            lines.append(f'        <!-- 队列管理 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>队列操作</h2>')
            lines.append(f'            <table class="data-table">')
            lines.append(f'                <thead><tr><th>科室</th><th>等待人数</th><th>当前号码</th><th>状态</th><th>操作</th></tr></thead>')
            lines.append(f'                <tbody>')
            lines.append(f'                    <tr><td>内科</td><td>15</td><td>A023</td><td><span style="color: green;">运行中</span></td>')
            lines.append(f'                        <td><button class="btn btn-secondary">暂停</button> <button class="btn btn-secondary">清空</button></td></tr>')
            lines.append(f'                    <tr><td>外科</td><td>8</td><td>B012</td><td><span style="color: green;">运行中</span></td>')
            lines.append(f'                        <td><button class="btn btn-secondary">暂停</button> <button class="btn btn-secondary">清空</button></td></tr>')
            lines.append(f'                </tbody>')
            lines.append(f'            </table>')
            lines.append(f'        </div>')

        elif "叫号" in module_name and "显示" in module_name:
            # 叫号显示模块 - 显示大屏界面
            lines.append(f'        <!-- 叫号显示屏 -->')
            lines.append(f'        <div class="card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">')
            lines.append(f'            <h2 style="color: white; text-align: center; font-size: 48px; margin: 30px 0;">正在叫号</h2>')
            lines.append(f'            <div style="text-align: center; padding: 40px;">')
            lines.append(f'                <div style="font-size: 120px; font-weight: bold; margin: 20px 0;">A023</div>')
            lines.append(f'                <div style="font-size: 36px;">请到 内科门诊 就诊</div>')
            lines.append(f'            </div>')
            lines.append(f'        </div>')
            lines.append(f"")
            lines.append(f'        <!-- 等待列表 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>等待列表</h2>')
            lines.append(f'            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 20px;">')
            lines.append(f'                <div style="padding: 20px; background: #f5f5f5; border-radius: 8px; text-align: center;">')
            lines.append(f'                    <div style="font-size: 36px; color: var(--primary-color); font-weight: bold;">A024</div>')
            lines.append(f'                    <div style="margin-top: 10px;">前方 1 人</div>')
            lines.append(f'                </div>')
            lines.append(f'                <div style="padding: 20px; background: #f5f5f5; border-radius: 8px; text-align: center;">')
            lines.append(f'                    <div style="font-size: 36px; color: var(--primary-color); font-weight: bold;">A025</div>')
            lines.append(f'                    <div style="margin-top: 10px;">前方 2 人</div>')
            lines.append(f'                </div>')
            lines.append(f'                <div style="padding: 20px; background: #f5f5f5; border-radius: 8px; text-align: center;">')
            lines.append(f'                    <div style="font-size: 36px; color: var(--primary-color); font-weight: bold;">A026</div>')
            lines.append(f'                    <div style="margin-top: 10px;">前方 3 人</div>')
            lines.append(f'                </div>')
            lines.append(f'            </div>')
            lines.append(f'        </div>')

        elif "医生" in module_name or "接诊" in module_name:
            # 医生接诊模块
            lines.append(f'        <!-- 医生工作台 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>当前就诊患者</h2>')
            lines.append(f'            <div style="background: #e3f2fd; padding: 30px; border-radius: 8px; margin-top: 20px;">')
            lines.append(f'                <div style="display: flex; justify-content: space-between; align-items: center;">')
            lines.append(f'                    <div>')
            lines.append(f'                        <div style="font-size: 48px; color: var(--primary-color); font-weight: bold;">A023</div>')
            lines.append(f'                        <div style="font-size: 20px; margin-top: 10px;">张三 · 男 · 35岁</div>')
            lines.append(f'                    </div>')
            lines.append(f'                    <div style="display: flex; gap: 10px;">')
            lines.append(f'                        <button class="btn btn-primary" style="padding: 15px 30px; font-size: 16px;">叫号</button>')
            lines.append(f'                        <button class="btn btn-secondary" style="padding: 15px 30px; font-size: 16px;">过号</button>')
            lines.append(f'                        <button class="btn btn-secondary" style="padding: 15px 30px; font-size: 16px;">完成</button>')
            lines.append(f'                    </div>')
            lines.append(f'                </div>')
            lines.append(f'            </div>')
            lines.append(f'        </div>')
            lines.append(f"")
            lines.append(f'        <!-- 就诊记录 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>今日就诊记录</h2>')
            lines.append(f'            <table class="data-table">')
            lines.append(f'                <thead><tr><th>序号</th><th>姓名</th><th>就诊时间</th><th>状态</th></tr></thead>')
            lines.append(f'                <tbody>')
            lines.append(f'                    <tr><td>A020</td><td>李四</td><td>10:15</td><td><span style="color: green;">已完成</span></td></tr>')
            lines.append(f'                    <tr><td>A021</td><td>王五</td><td>10:30</td><td><span style="color: green;">已完成</span></td></tr>')
            lines.append(f'                    <tr><td>A022</td><td>赵六</td><td>10:45</td><td><span style="color: orange;">过号</span></td></tr>')
            lines.append(f'                </tbody>')
            lines.append(f'            </table>')
            lines.append(f'        </div>')

        elif "统计" in module_name or "报表" in module_name:
            # 统计报表模块
            lines.append(f'        <!-- 统计概览 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>数据统计</h2>')
            lines.append(f'            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-top: 20px;">')
            lines.append(f'                <div style="padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 8px;">')
            lines.append(f'                    <div style="font-size: 36px; font-weight: bold;">1,234</div>')
            lines.append(f'                    <div style="opacity: 0.9;">今日就诊量</div>')
            lines.append(f'                </div>')
            lines.append(f'                <div style="padding: 20px; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; border-radius: 8px;">')
            lines.append(f'                    <div style="font-size: 36px; font-weight: bold;">18.5</div>')
            lines.append(f'                    <div style="opacity: 0.9;">平均等待(分钟)</div>')
            lines.append(f'                </div>')
            lines.append(f'                <div style="padding: 20px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; border-radius: 8px;">')
            lines.append(f'                    <div style="font-size: 36px; font-weight: bold;">98.5%</div>')
            lines.append(f'                    <div style="opacity: 0.9;">患者满意度</div>')
            lines.append(f'                </div>')
            lines.append(f'                <div style="padding: 20px; background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); color: white; border-radius: 8px;">')
            lines.append(f'                    <div style="font-size: 36px; font-weight: bold;">15</div>')
            lines.append(f'                    <div style="opacity: 0.9;">活跃科室</div>')
            lines.append(f'                </div>')
            lines.append(f'            </div>')
            lines.append(f'        </div>')
            lines.append(f"")
            lines.append(f'        <!-- 报表导出 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>报表管理</h2>')
            lines.append(f'            <div style="display: flex; gap: 15px; margin-top: 20px;">')
            lines.append(f'                <button class="btn btn-primary">日报表</button>')
            lines.append(f'                <button class="btn btn-primary">周报表</button>')
            lines.append(f'                <button class="btn btn-primary">月报表</button>')
            lines.append(f'                <button class="btn btn-secondary">自定义报表</button>')
            lines.append(f'            </div>')
            lines.append(f'        </div>')

        elif "系统" in module_name or "管理" in module_name:
            # 系统管理模块
            lines.append(f'        <!-- 系统配置 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>系统参数设置</h2>')
            lines.append(f'            <div class="form-group" style="margin-top: 20px;">')
            lines.append(f'                <label>叫号间隔时间（秒）</label>')
            lines.append(f'                <input type="number" class="form-control" value="30">')
            lines.append(f'            </div>')
            lines.append(f'            <div class="form-group">')
            lines.append(f'                <label>语音播报音量</label>')
            lines.append(f'                <input type="range" class="form-control" min="0" max="100" value="70">')
            lines.append(f'            </div>')
            lines.append(f'            <div class="form-group">')
            lines.append(f'                <label>过号自动重排</label>')
            lines.append(f'                <select class="form-control"><option>启用</option><option>禁用</option></select>')
            lines.append(f'            </div>')
            lines.append(f'            <button class="btn btn-primary">保存设置</button>')
            lines.append(f'        </div>')
            lines.append(f"")
            lines.append(f'        <!-- 用户管理 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>用户权限管理</h2>')
            lines.append(f'            <table class="data-table">')
            lines.append(f'                <thead><tr><th>用户名</th><th>角色</th><th>状态</th><th>操作</th></tr></thead>')
            lines.append(f'                <tbody>')
            lines.append(f'                    <tr><td>admin</td><td>管理员</td><td><span style="color: green;">正常</span></td><td><a href="#">编辑</a></td></tr>')
            lines.append(f'                    <tr><td>doctor01</td><td>医生</td><td><span style="color: green;">正常</span></td><td><a href="#">编辑</a></td></tr>')
            lines.append(f'                    <tr><td>nurse01</td><td>护士</td><td><span style="color: green;">正常</span></td><td><a href="#">编辑</a></td></tr>')
            lines.append(f'                </tbody>')
            lines.append(f'            </table>')
            lines.append(f'            <button class="btn btn-primary" style="margin-top: 15px;">添加用户</button>')
            lines.append(f'        </div>')

        elif "候诊" in module_name or "引导" in module_name:
            # 候诊引导模块
            lines.append(f'        <!-- 候诊导航 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>候诊区导航</h2>')
            lines.append(f'            <div style="background: #f5f5f5; padding: 30px; border-radius: 8px; margin-top: 20px;">')
            lines.append(f'                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;">')
            lines.append(f'                    <div style="background: white; padding: 20px; border-radius: 8px; text-align: center;">')
            lines.append(f'                        <div style="font-size: 48px;">🏥</div>')
            lines.append(f'                        <div style="margin-top: 10px; font-weight: bold;">一楼 - 内科区</div>')
            lines.append(f'                        <div style="color: #666; font-size: 14px; margin-top: 5px;">等待: 15人</div>')
            lines.append(f'                    </div>')
            lines.append(f'                    <div style="background: white; padding: 20px; border-radius: 8px; text-align: center;">')
            lines.append(f'                        <div style="font-size: 48px;">💊</div>')
            lines.append(f'                        <div style="margin-top: 10px; font-weight: bold;">二楼 - 外科区</div>')
            lines.append(f'                        <div style="color: #666; font-size: 14px; margin-top: 5px;">等待: 8人</div>')
            lines.append(f'                    </div>')
            lines.append(f'                    <div style="background: white; padding: 20px; border-radius: 8px; text-align: center;">')
            lines.append(f'                        <div style="font-size: 48px;">👶</div>')
            lines.append(f'                        <div style="margin-top: 10px; font-weight: bold;">三楼 - 儿科区</div>')
            lines.append(f'                        <div style="color: #666; font-size: 14px; margin-top: 5px;">等待: 22人</div>')
            lines.append(f'                    </div>')
            lines.append(f'                </div>')
            lines.append(f'            </div>')
            lines.append(f'        </div>')
            lines.append(f"")
            lines.append(f'        <!-- 我的排队 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>我的排队状态</h2>')
            lines.append(f'            <div style="background: #e3f2fd; padding: 25px; border-radius: 8px; margin: 20px 0;">')
            lines.append(f'                <div style="display: flex; justify-content: space-between;">')
            lines.append(f'                    <div>')
            lines.append(f'                        <div style="font-size: 14px; color: #666;">当前号码</div>')
            lines.append(f'                        <div style="font-size: 36px; color: var(--primary-color); font-weight: bold;">A023</div>')
            lines.append(f'                    </div>')
            lines.append(f'                    <div>')
            lines.append(f'                        <div style="font-size: 14px; color: #666;">前方等待</div>')
            lines.append(f'                        <div style="font-size: 36px; color: #ff9800; font-weight: bold;">3人</div>')
            lines.append(f'                    </div>')
            lines.append(f'                    <div>')
            lines.append(f'                        <div style="font-size: 14px; color: #666;">预计等待</div>')
            lines.append(f'                        <div style="font-size: 36px; color: #4caf50; font-weight: bold;">15分</div>')
            lines.append(f'                    </div>')
            lines.append(f'                </div>')
            lines.append(f'            </div>')
            lines.append(f'        </div>')

        elif "预约" in module_name:
            # 预约管理模块
            lines.append(f'        <!-- 预约管理 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>预约挂号</h2>')
            lines.append(f'            <div class="form-group" style="margin-top: 20px;">')
            lines.append(f'                <label>选择科室</label>')
            lines.append(f'                <select class="form-control"><option>请选择...</option><option>内科</option><option>外科</option></select>')
            lines.append(f'            </div>')
            lines.append(f'            <div class="form-group">')
            lines.append(f'                <label>选择医生</label>')
            lines.append(f'                <select class="form-control"><option>请选择...</option><option>张医生</option><option>李医生</option></select>')
            lines.append(f'            </div>')
            lines.append(f'            <div class="form-group">')
            lines.append(f'                <label>预约日期</label>')
            lines.append(f'                <input type="date" class="form-control">')
            lines.append(f'            </div>')
            lines.append(f'            <div class="form-group">')
            lines.append(f'                <label>预约时段</label>')
            lines.append(f'                <select class="form-control"><option>08:00-09:00</option><option>09:00-10:00</option></select>')
            lines.append(f'            </div>')
            lines.append(f'            <button class="btn btn-primary">提交预约</button>')
            lines.append(f'        </div>')
            lines.append(f"")
            lines.append(f'        <!-- 预约列表 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>我的预约</h2>')
            lines.append(f'            <table class="data-table">')
            lines.append(f'                <thead><tr><th>医生</th><th>日期</th><th>时段</th><th>状态</th><th>操作</th></tr></thead>')
            lines.append(f'                <tbody>')
            lines.append(f'                    <tr><td>张医生(内科)</td><td>2024-01-16</td><td>09:00-10:00</td><td><span style="color: green;">已确认</span></td><td><a href="#">取消</a></td></tr>')
            lines.append(f'                    <tr><td>李医生(外科)</td><td>2024-01-17</td><td>14:00-15:00</td><td><span style="color: orange;">待确认</span></td><td><a href="#">取消</a></td></tr>')
            lines.append(f'                </tbody>')
            lines.append(f'            </table>')
            lines.append(f'        </div>')

        elif "通知" in module_name or "消息" in module_name:
            # 消息通知模块
            lines.append(f'        <!-- 消息设置 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>通知渠道设置</h2>')
            lines.append(f'            <div style="margin-top: 20px;">')
            lines.append(f'                <div style="padding: 15px; background: #f5f5f5; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between;">')
            lines.append(f'                    <div><strong>短信通知</strong><br><small style="color: #666;">发送到注册手机</small></div>')
            lines.append(f'                    <input type="checkbox" checked>')
            lines.append(f'                </div>')
            lines.append(f'                <div style="padding: 15px; background: #f5f5f5; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between;">')
            lines.append(f'                    <div><strong>微信推送</strong><br><small style="color: #666;">通过微信公众号推送</small></div>')
            lines.append(f'                    <input type="checkbox" checked>')
            lines.append(f'                </div>')
            lines.append(f'                <div style="padding: 15px; background: #f5f5f5; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between;">')
            lines.append(f'                    <div><strong>APP推送</strong><br><small style="color: #666;">手机APP推送通知</small></div>')
            lines.append(f'                    <input type="checkbox">')
            lines.append(f'                </div>')
            lines.append(f'            </div>')
            lines.append(f'        </div>')
            lines.append(f"")
            lines.append(f'        <!-- 消息记录 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>消息发送记录</h2>')
            lines.append(f'            <table class="data-table">')
            lines.append(f'                <thead><tr><th>时间</th><th>类型</th><th>接收人</th><th>内容</th><th>状态</th></tr></thead>')
            lines.append(f'                <tbody>')
            lines.append(f'                    <tr><td>10:30</td><td>短信</td><td>张三</td><td>您的号码A023即将就诊</td><td><span style="color: green;">成功</span></td></tr>')
            lines.append(f'                    <tr><td>10:25</td><td>微信</td><td>李四</td><td>前方还有2人，请留意</td><td><span style="color: green;">成功</span></td></tr>')
            lines.append(f'                    <tr><td>10:20</td><td>短信</td><td>王五</td><td>预约已确认</td><td><span style="color: green;">成功</span></td></tr>')
            lines.append(f'                </tbody>')
            lines.append(f'            </table>')
            lines.append(f'        </div>')

        else:
            # 通用内容
            lines.append(f'        <!-- 操作区 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>操作面板</h2>')
            lines.append(f'            <div style="margin-top: 20px;">')
            lines.append(f'                <button class="btn btn-primary">新建</button>')
            lines.append(f'                <button class="btn btn-secondary">查询</button>')
            lines.append(f'                <button class="btn btn-secondary">导出</button>')
            lines.append(f'            </div>')
            lines.append(f'        </div>')
            lines.append(f"")
            lines.append(f'        <!-- 数据表格 -->')
            lines.append(f'        <div class="card">')
            lines.append(f'            <h2>数据列表</h2>')
            lines.append(f'            <table class="data-table">')
            lines.append(f'                <thead><tr><th>编号</th><th>名称</th><th>状态</th><th>操作</th></tr></thead>')
            lines.append(f'                <tbody>')
            lines.append(f'                    <tr><td>001</td><td>示例数据1</td><td><span style="color: green;">正常</span></td><td><a href="#" style="color: var(--primary-color);">查看</a></td></tr>')
            lines.append(f'                    <tr><td>002</td><td>示例数据2</td><td><span style="color: green;">正常</span></td><td><a href="#" style="color: var(--primary-color);">查看</a></td></tr>')
            lines.append(f'                </tbody>')
            lines.append(f'            </table>')
            lines.append(f'        </div>')

        return lines

    def _call_claude(self, prompt: str, output_file: str) -> str:
        """Call Claude Code CLI, auto-generate, or prompt for manual invocation."""
        # Save prompt to file for reference
        ensure_directory(PROMPTS_DIR)
        prompt_path = PROMPTS_DIR / f"{output_file}.prompt"
        with open(prompt_path, 'w', encoding='utf-8') as f:
            f.write(prompt)

        output_path = PROCESS_DIR / output_file

        # Check if output file already exists (user manually created or from previous run)
        if output_path.exists():
            file_size = output_path.stat().st_size
            if file_size > 0:
                print(f"  ✓ 使用已存在的输出文件: {output_path} ({file_size} 字节)")
                with open(output_path, 'r', encoding='utf-8') as f:
                    return f.read()

        # Auto mode: Create a marker file and wait for external agent
        # (e.g., VSCode extension with AI capability)
        if self.mode == "auto":
            print(f"\n  📋 提示词已保存: {prompt_path}")
            print(f"  📄 期望输出: {output_path}")
            print(f"  🤖 等待自动生成...")

            # Create a marker file to signal pending generation
            marker_path = PROMPTS_DIR / f"{output_file}.pending"
            with open(marker_path, 'w', encoding='utf-8') as f:
                f.write(prompt)

            # Wait for the output file to be created by external agent
            import time
            max_wait = 600  # 10 minutes
            waited = 0
            check_interval = 1  # Check every second

            try:
                while waited < max_wait:
                    if output_path.exists():
                        file_size = output_path.stat().st_size
                        if file_size > 0:
                            print(f"  ✓ 检测到输出文件! ({file_size} 字节)")
                            # Remove marker file
                            if marker_path.exists():
                                marker_path.unlink()
                            with open(output_path, 'r', encoding='utf-8') as f:
                                return f.read()
                    time.sleep(check_interval)
                    waited += check_interval
                    if waited % 5 == 0:
                        print(f"  等待中... ({waited}s)")

                print(f"\n  ⚠️  等待超时")
                if not output_path.exists():
                    raise FileNotFoundError(
                        f"输出文件未找到: {output_path}\n"
                        f"自动生成未能完成，请检查系统配置"
                    )
                with open(output_path, 'r', encoding='utf-8') as f:
                    return f.read()

            except KeyboardInterrupt:
                print(f"\n  用户中断")
                if output_path.exists():
                    if marker_path.exists():
                        marker_path.unlink()
                    with open(output_path, 'r', encoding='utf-8') as f:
                        return f.read()
                raise FileNotFoundError(f"输出文件未找到: {output_path}")

        # Interactive mode: prompt user to invoke Claude Code manually
        print(f"\n  📋 提示词已保存: {prompt_path}")
        print(f"  📄 输出文件: {output_path}")
        print(f"\n  请在 VS Code 中执行以下操作：")
        print(f"  " + "-" * 56)
        print(f"  1. 打开 Claude Code (Ctrl+Shift+C / Cmd+Shift+C)")
        print(f"  2. 输入: 请阅读 {prompt_path} 并生成内容")
        print(f"  3. 将生成的 JSON/Markdown 内容保存到 {output_path}")
        print(f"  " + "-" * 56)

        # Wait for file to be created
        import time
        max_wait = 300  # 5 minutes
        waited = 0
        check_interval = 2

        print(f"\n  ⏳ 等待输出文件创建... (每 {check_interval} 秒检查一次)")
        print(f"  💡 提示: 创建文件后按 Ctrl+C 继续，或等待自动检测")

        try:
            while waited < max_wait:
                if output_path.exists():
                    file_size = output_path.stat().st_size
                    if file_size > 0:
                        print(f"  ✓ 检测到输出文件! ({file_size} 字节)")
                        with open(output_path, 'r', encoding='utf-8') as f:
                            return f.read()
                time.sleep(check_interval)
                waited += check_interval
                if waited % 10 == 0:
                    print(f"  等待中... ({waited}s)")

            print(f"\n  ⚠️  等待超时，请手动确认文件是否存在")
            if not output_path.exists():
                raise FileNotFoundError(
                    f"输出文件未找到: {output_path}\n"
                    f"请确保已通过 Claude Code 生成并保存了该文件"
                )
            with open(output_path, 'r', encoding='utf-8') as f:
                return f.read()

        except KeyboardInterrupt:
            print(f"\n  用户中断，检查文件...")
            if output_path.exists():
                with open(output_path, 'r', encoding='utf-8') as f:
                    return f.read()
            raise FileNotFoundError(
                f"输出文件未找到: {output_path}"
            )


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

class SoftwareCopyrightOrchestrator:
    """Main orchestrator for software copyright application generation."""

    def __init__(self, claude_mode: str = "interactive"):
        self.variables: Dict[str, str] = {}
        self.modules: List[Dict] = []
        self.claude = ClaudeCodeIntegrator(mode=claude_mode)
        self.total_lines = 0
        self.inputs_collected = False  # Track if inputs have been collected

    def collect_user_inputs(self):
        """Step 1: Collect user inputs for all defined variables."""
        print_section("Step 1: Collect User Inputs")

        print(f"\n  Template: {TEMPLATE_FILES['variables']}")
        print(f"  Defined variables: {len(VARIABLE_DEFINITIONS)}\n")

        for key, definition in VARIABLE_DEFINITIONS.items():
            prompt_text = definition["prompt"]
            default_val = definition["default"]
            required = definition["required"]

            if default_val:
                prompt_text += f" [默认: {default_val}]"
            if required:
                prompt_text += " *"

            while True:
                play_alert_sound()
                user_input = input(f"  {prompt_text}: ").strip()

                if not user_input:
                    if default_val:
                        user_input = default_val
                    elif required:
                        print(f"  ⚠️  此项为必填项，请输入")
                        continue
                    else:
                        user_input = ""

                self.variables[key] = user_input
                print(f"  ✓ {key} = {user_input}")
                break

        print(f"\n  ✓ Collected {len(self.variables)} variables")

        # Ask for module count (功能点数量)
        print_section("功能点设置")
        print("\n  请设置软件的功能点数量，每个功能点将生成一个对应的 HTML 页面。")
        print("  建议数量: 8-15 个功能点")

        while True:
            play_alert_sound()
            module_input = input("\n  请输入功能点数量 [默认: 10]: ").strip()
            if not module_input:
                module_count = 10
            else:
                try:
                    module_count = int(module_input)
                    if module_count < 3:
                        print(f"  ⚠️  功能点数量不能少于 3 个")
                        continue
                    if module_count > 30:
                        print(f"  ⚠️  功能点数量建议不超过 30 个")
                        play_alert_sound()
                        confirm = input(f"  确定要生成 {module_count} 个功能点吗? (y/n): ").strip().lower()
                        if confirm not in ['y', 'yes', '是', 'Y']:
                            continue
                except ValueError:
                    print(f"  ⚠️  请输入有效的数字")
                    continue

            self.variables["module_count"] = str(module_count)
            print(f"  ✓ 将生成 {module_count} 个功能点 (每个功能点对应一个 HTML 页面)")
            break

    def generate_srs(self):
        """Step 2: Generate Software Requirements Specification."""
        software_name = self.variables["software_name"]
        industry = self.variables["industry"]
        module_count = int(self.variables.get("module_count", 10))

        print(f"\n  Software: {software_name}")
        print(f"  Industry: {industry}")
        print(f"  Module Count: {module_count}")

        srs_json = self.claude.generate_srs(software_name, industry, module_count)

        try:
            self.modules = json.loads(srs_json)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            match = re.search(r'```json\s*(.*?)\s*```', srs_json, re.DOTALL)
            if match:
                self.modules = json.loads(match.group(1))
            else:
                raise ValueError("Failed to parse SRS JSON from Claude output")

        print(f"\n  ✓ Generated {len(self.modules)} modules:")
        for i, module in enumerate(self.modules, 1):
            print(f"    {i}. {module.get('name', 'Unknown')}: {module.get('description', 'No description')[:50]}...")

        # Save SRS for reference
        srs_path = PROCESS_DIR / "srs.json"
        with open(srs_path, 'w', encoding='utf-8') as f:
            json.dump(self.modules, f, ensure_ascii=False, indent=2)
        print(f"\n  📁 SRS saved to: {srs_path}")

    def generate_frontend_code(self):
        """Step 3: Generate frontend HTML/CSS code for each module."""
        software_name = self.variables["software_name"]

        # No target lines - generate based on actual functionality
        print(f"\n  Modules: {len(self.modules)}")
        print(f"  Generating HTML based on actual functionality...\n")

        for i, module in enumerate(self.modules, 1):
            module_name = module["name"]
            print_step(i, len(self.modules), f"Generating code for: {module_name}")

            # Generate HTML code with validation and retry (no target lines)
            max_retries = 3
            for attempt in range(max_retries):
                html_code = self.claude.generate_html_code(
                    module_name, software_name, None, i, self._sanitize_filename, module
                )

                # Validate the generated HTML
                is_valid, error_msg = self._validate_html(html_code)

                if is_valid:
                    # Valid HTML - save and continue
                    filename = f"module_{i:02d}_{self._sanitize_filename(module_name)}.html"
                    filepath = PROCESS_DIR / filename

                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(html_code)

                    lines = count_lines_in_file(filepath)
                    print(f"  ✓ Generated {lines} lines -> {filepath}")
                    break
                else:
                    # Invalid HTML - retry if attempts remain
                    if attempt < max_retries - 1:
                        print(f"  ⚠️  验证失败: {error_msg}")
                        print(f"  🔄 重试 ({attempt + 1}/{max_retries})...")
                        # Delete the invalid file if it exists
                        filename = f"module_{i:02d}_{self._sanitize_filename(module_name)}.html"
                        filepath = PROCESS_DIR / filename
                        if filepath.exists():
                            filepath.unlink()
                        # Clear any cached file to force regeneration
                        cache_path = PROCESS_DIR / filename
                        if cache_path.exists():
                            cache_path.unlink()
                    else:
                        # All retries failed - use fallback
                        print(f"  ⚠️  所有重试失败，使用内置模板")
                        html_code = self.claude._generate_html_template(
                            module_name, software_name, None, module
                        )
                        filename = f"module_{i:02d}_{self._sanitize_filename(module_name)}.html"
                        filepath = PROCESS_DIR / filename

                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(html_code)

                        lines = count_lines_in_file(filepath)
                        print(f"  ✓ 使用模板生成 {lines} lines -> {filepath}")

        self.total_lines = count_total_lines(PROCESS_DIR)
        print(f"\n  ✓ Total lines generated: {self.total_lines}")

    def adjust_line_count(self):
        """Step 4: Skip line count adjustment (no target limits)."""
        # Update line count variable - multiply by 10 for registration form
        display_line_count = self.total_lines * 10
        self.variables["line_count"] = str(display_line_count)
        print(f"\n  ✓ Generated {self.total_lines} lines (displayed as {display_line_count} in registration form)")

    def generate_function_descriptions(self):
        """Step 5: Generate function descriptions for manuals."""
        print_section("Step 5: Generate Function Descriptions")

        print("\n  Generating main functions summary...")
        summary, detailed = self.claude.generate_function_descriptions(self.modules)

        self.variables["main_functions_summary"] = summary
        print(f"  ✓ Summary generated ({len(summary)} chars)")

        self.variables["main_functions_details"] = detailed
        print(f"  ✓ Detailed description generated ({len(detailed)} chars)")

    def generate_dev_purpose(self):
        """Step 6: Generate development purpose."""
        print_section("Step 6: Generate Development Purpose")

        software_name = self.variables["software_name"]
        industry = self.variables["industry"]

        purpose = self.claude.generate_dev_purpose(software_name, industry)
        self.variables["dev_purpose"] = purpose

        print(f"\n  ✓ Development purpose generated ({len(purpose)} chars)")
        print(f"\n  Preview:\n    {purpose[:100]}...")

    def generate_output_documents(self):
        """Step 7: Generate final output documents."""
        print_section("Step 7: Generate Output Documents")

        # Check if we should use AI expansion
        use_ai_expansion = AI_BRIDGE_AVAILABLE and self.claude.mode == "auto"

        # Generate functional manual
        print("\n  [1/4] Generating Functional Manual...")
        template = read_template(TEMPLATE_FILES["function_manual"])
        content = replace_variables(template, self.variables)

        if use_ai_expansion:
            print("  🤖 使用 Claude AI 扩写内容...")
            content = expand_document_template(content, self.variables, "function_manual")

        write_output(OUTPUT_FILES["function_manual"], content)

        # Generate installation manual
        print("\n  [2/4] Generating Installation Manual...")
        template = read_template(TEMPLATE_FILES["install_manual"])
        content = replace_variables(template, self.variables)

        if use_ai_expansion:
            print("  🤖 使用 Claude AI 扩写内容...")
            content = expand_document_template(content, self.variables, "install_manual")

        write_output(OUTPUT_FILES["install_manual"], content)

        # Generate registration form
        print("\n  [3/4] Generating Registration Form...")
        template = read_template(TEMPLATE_FILES["registration_form"])
        content = replace_variables(template, self.variables)

        if use_ai_expansion:
            print("  🤖 使用 Claude AI 扩写内容...")
            content = expand_document_template(content, self.variables, "registration_form")

        write_output(OUTPUT_FILES["registration_form"], content)

        # Generate source code markdown file
        print("\n  [4/4] Generating Source Code Markdown...")
        self.generate_source_code_markdown()

    def generate_source_code_markdown(self):
        """Generate a single Markdown file containing all HTML source code."""
        software_name = self.variables.get("software_name", "Software")

        # Start building the markdown content
        md_content = f"# {software_name} 源代码\n\n"
        md_content += f"本文档包含系统的所有前端 HTML 源代码。\n\n"
        md_content += f"## 代码目录\n\n"

        # Get all HTML files from process directory
        html_files = sorted(PROCESS_DIR.glob("module_*.html"))

        # Generate table of contents
        for i, html_file in enumerate(html_files, 1):
            module_name = html_file.stem.replace('module_', '').replace('_', ' ')
            md_content += f"{i}. [{module_name}](#{module_name.replace(' ', '-')})\n"

        md_content += f"\n---\n\n"

        # Add each HTML file as a code block
        for html_file in html_files:
            module_name = html_file.stem.replace('module_', '').replace('_', ' ')

            # Count lines in this file
            line_count = count_lines_in_file(html_file)

            md_content += f"## {module_name}\n\n"
            md_content += f"**文件**: `{html_file.name}`  \n"
            md_content += f"**行数**: {line_count} 行\n\n"
            md_content += f"```html\n"

            # Read and append the HTML content
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
                md_content += html_content

            md_content += f"\n```\n\n---\n\n"

        # Add footer
        total_lines = sum(count_lines_in_file(f) for f in html_files)
        md_content += f"\n## 统计信息\n\n"
        md_content += f"- **模块数量**: {len(html_files)}\n"
        md_content += f"- **总代码行数**: {total_lines} 行\n"
        md_content += f"- **生成时间**: {self.variables.get('comp_date', '')}\n"

        # Write to output
        output_path = OUTPUT_DIR / "源代码.md"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f"  ✓ Generated: {output_path} ({len(md_content)} chars)")
        print(f"    - {len(html_files)} modules")
        print(f"    - {total_lines} total lines")

    def print_summary(self):
        """Print final summary."""
        print_section("Generation Complete!")

        print(f"\n  📊 Statistics:")
        print(f"    - Software: {self.variables['software_name']}")
        print(f"    - Version: {self.variables['version']}")
        print(f"    - Modules: {len(self.modules)}")
        print(f"    - Total lines: {self.total_lines}")
        print(f"    - OS: {DEFAULT_OS}")
        print(f"    - Dev Tool: {DEFAULT_DEV_TOOL}")

        print(f"\n  📁 Output Files:")
        for name, filename in OUTPUT_FILES.items():
            filepath = OUTPUT_DIR / filename
            print(f"    - [{name}] {filepath}")

        print(f"\n  📁 Process Files:")
        html_files = list(PROCESS_DIR.glob("*.html"))
        print(f"    - HTML files: {len(html_files)}")
        for filepath in sorted(html_files):
            lines = count_lines_in_file(filepath)
            print(f"      * {filepath.name} ({lines} lines)")

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize module name for use in filename."""
        # Remove or replace characters not suitable for filenames
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        name = name.replace(' ', '_')
        return name[:50]  # Limit length

    def _validate_html(self, html_code: str) -> tuple[bool, str]:
        """
        Validate that the generated content is valid HTML.

        Returns:
            (is_valid, error_message)
        """
        # Check for basic HTML structure
        html_lower = html_code.lower()

        # Must have HTML, HEAD, BODY tags
        if "<html" not in html_lower:
            return False, "缺少 <html> 标签"
        if "<head" not in html_lower:
            return False, "缺少 <head> 标签"
        if "<body" not in html_lower:
            return False, "缺少 <body> 标签"
        if "</html>" not in html_lower:
            return False, "缺少 </html> 结束标签"

        # Check for descriptive text patterns (common failures)
        failure_patterns = [
            "I've created a complete",
            "Here's what's included:",
            "The page includes:",
            "**Design Features:**",
            "**Structure:**",
            "**Features Implemented:**",
            "**Code Details:**",
            "The file has been created successfully",
            "This is a production-ready",
        ]

        for pattern in failure_patterns:
            if pattern in html_code:
                return False, f"包含说明文字而非 HTML 代码 (检测到: '{pattern}')"

        # Check for minimum length (at least 1000 chars for a reasonable HTML page)
        if len(html_code) < 1000:
            return False, f"HTML 内容过短 ({len(html_code)} 字符)"

        # Check for CSS style block
        if "<style" not in html_lower:
            return False, "缺少 <style> 标签"

        # All checks passed
        return True, ""

    def run(self):
        """Run the complete orchestration pipeline."""
        print("\n" + "=" * 60)
        print("  Software Copyright Application Generator")
        print("=" * 60)
        print(f"\n  Configuration:")
        print(f"    - OS: {DEFAULT_OS}")
        print(f"    - Dev Tool: {DEFAULT_DEV_TOOL}")
        print(f"    - Line Limit: None (generate based on actual functionality)")

        # Ensure directories exist
        ensure_directory(PROCESS_DIR)
        ensure_directory(OUTPUT_DIR)
        ensure_directory(PROMPTS_DIR)

        try:
            # Step 1: Collect user inputs (skip if already set via --skip-inputs)
            if not self.inputs_collected:
                self.collect_user_inputs()
            else:
                print_section("Step 1: 使用预设参数")
                print(f"\n  ✓ 已加载预设参数")
                for key, value in self.variables.items():
                    print(f"    {key}: {value}")

            # Step 2: Generate SRS
            print_section("Step 2: 需求设计 (SRS)")
            self.generate_srs()

            # Confirm before proceeding to frontend generation
            print_section("阶段确认")
            print(f"\n  ✓ 需求设计已完成!")
            print(f"  - 软件名称: {self.variables['software_name']}")
            print(f"  - 模块数量: {len(self.modules)}")
            print(f"  - 模块列表:")
            for i, m in enumerate(self.modules, 1):
                print(f"      {i}. {m['name']}")

            if not confirm_action("是否继续生成前端页面？"):
                print("\n  用户取消，程序退出")
                sys.exit(0)

            # Step 3: Generate frontend code
            print_section("Step 3: 前端页面开发")
            self.generate_frontend_code()

            # Step 4: Adjust line count
            self.adjust_line_count()

            # Confirm before proceeding to document generation
            print_section("阶段确认")
            print(f"\n  ✓ 前端页面开发已完成!")
            print(f"  - 总代码行数: {self.total_lines}")

            if not confirm_action("是否继续生成4份文档？"):
                print("\n  用户取消，程序退出")
                sys.exit(0)

            # Step 5-7: Generate documents
            print_section("Step 4: 文档生成")
            self.generate_function_descriptions()
            self.generate_dev_purpose()
            self.generate_output_documents()

            # Final summary
            self.print_summary()

            print_section("任务完成")
            print(f"\n  ✓ 所有文档已生成到 output 目录")
            print(f"  ✓ 可以直接用于软件著作权申请")

        except KeyboardInterrupt:
            print("\n\n  ⚠️  用户中断操作")
            sys.exit(0)
        except Exception as e:
            print(f"\n\n  ❌ 错误: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Software Copyright Application Automation Tool"
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["auto", "interactive", "cli"],
        default="auto",
        help="Claude Code integration mode (auto: automatic generation, interactive: manual prompt, cli: direct CLI call)"
    )
    parser.add_argument(
        "--skip-inputs", "-s",
        action="store_true",
        help="Skip user input collection (use defaults only)"
    )

    args = parser.parse_args()

    orchestrator = SoftwareCopyrightOrchestrator(claude_mode=args.mode)

    if args.skip_inputs:
        # Use defaults for all variables
        for key, definition in VARIABLE_DEFINITIONS.items():
            orchestrator.variables[key] = definition["default"]
        orchestrator.inputs_collected = True

    orchestrator.run()


if __name__ == "__main__":
    main()
