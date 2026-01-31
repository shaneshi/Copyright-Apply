#!/usr/bin/env python3
"""
AI Bridge for Software Copyright Application

This module provides automatic content generation by detecting pending
tasks and using the VSCode extension's AI capabilities.
"""

import os
import time
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

# Paths
PROJECT_ROOT = Path(__file__).parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"
PROCESS_DIR = PROJECT_ROOT / "process"
REQUEST_FILE = PROMPTS_DIR / ".generation_request"


class GenerationRequest:
    """Represents a content generation request."""

    def __init__(self, task_type: str, prompt: str, output_file: str, context: Dict = None):
        self.task_type = task_type
        self.prompt = prompt
        self.output_file = output_file
        self.context = context or {}

    def to_dict(self) -> Dict:
        return {
            "task_type": self.task_type,
            "prompt": self.prompt,
            "output_file": self.output_file,
            "context": self.context
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'GenerationRequest':
        return cls(
            task_type=data["task_type"],
            prompt=data["prompt"],
            output_file=data["output_file"],
            context=data.get("context", {})
        )


class AIBridge:
    """
    Bridge between Python script and VSCode extension for AI generation.

    The Python script writes generation requests to a file, and the
    VSCode extension reads and processes them automatically.
    """

    def __init__(self):
        self.ensure_directories()

    def ensure_directories(self):
        """Ensure required directories exist."""
        PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
        PROCESS_DIR.mkdir(parents=True, exist_ok=True)

    def request_generation(self, task_type: str, prompt: str, output_file: str, context: Dict = None) -> str:
        """
        Request content generation.

        Creates a request file and waits for the output to be generated.

        Args:
            task_type: Type of content (srs, html_code, etc.)
            prompt: The prompt for generation
            output_file: Name of the output file
            context: Additional context (e.g., software_name, module_name)

        Returns:
            The generated content
        """
        request = GenerationRequest(task_type, prompt, output_file, context)

        # Write request to file
        with open(REQUEST_FILE, 'w', encoding='utf-8') as f:
            json.dump(request.to_dict(), f, ensure_ascii=False, indent=2)

        output_path = PROCESS_DIR / output_file

        print(f"\n  📋 生成请求已创建: {REQUEST_FILE}")
        print(f"  📄 期望输出: {output_path}")
        print(f"  🤖 等待自动生成...")

        # Wait for output file to be created
        max_wait = 600  # 10 minutes
        waited = 0
        check_interval = 1

        try:
            while waited < max_wait:
                if output_path.exists():
                    file_size = output_path.stat().st_size
                    if file_size > 0:
                        print(f"  ✓ 检测到输出文件! ({file_size} 字节)")
                        # Clean up request file
                        if REQUEST_FILE.exists():
                            REQUEST_FILE.unlink()
                        with open(output_path, 'r', encoding='utf-8') as f:
                            return f.read()
                time.sleep(check_interval)
                waited += check_interval
                if waited % 5 == 0 and waited > 0:
                    print(f"  等待中... ({waited}s)")

            print(f"\n  ⚠️  等待超时")
            if not output_path.exists():
                raise FileNotFoundError(
                    f"输出文件未找到: {output_path}\n"
                    f"自动生成未能完成，请检查 VSCode 扩展是否正在运行"
                )
            with open(output_path, 'r', encoding='utf-8') as f:
                return f.read()

        except KeyboardInterrupt:
            print(f"\n  用户中断")
            if output_path.exists():
                if REQUEST_FILE.exists():
                    REQUEST_FILE.unlink()
                with open(output_path, 'r', encoding='utf-8') as f:
                    return f.read()
            raise FileNotFoundError(f"输出文件未找到: {output_path}")

    def check_request(self) -> Optional[GenerationRequest]:
        """Check if there's a pending generation request."""
        if REQUEST_FILE.exists():
            try:
                with open(REQUEST_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return GenerationRequest.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                return None
        return None

    def complete_request(self, content: str):
        """Complete the current request by saving content."""
        request = self.check_request()
        if request:
            output_path = PROCESS_DIR / request.output_file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✓ 已保存生成内容: {output_path}")
            # Remove request file
            if REQUEST_FILE.exists():
                REQUEST_FILE.unlink()
            return True
        return False

    def call_claude_cli(self, prompt: str, json_mode: bool = False) -> str:
        """
        Call Claude CLI directly to generate content.

        Args:
            prompt: The prompt to send to Claude
            json_mode: Whether to expect JSON output

        Returns:
            The generated content
        """
        cmd = ["claude", "-p", prompt, "--dangerously-skip-permissions"]

        if json_mode:
            cmd.extend(["--output-format", "json"])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes timeout
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Claude CLI 调用失败: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Claude CLI 调用超时")
        except FileNotFoundError:
            raise RuntimeError("未找到 claude 命令，请确保已安装 Claude Code CLI")


# Pre-defined generators for common tasks

def generate_srs_auto(software_name: str, industry: str, module_count: int = 10) -> str:
    """
    Auto-generate SRS using Claude CLI.

    Args:
        software_name: Name of the software
        industry: Target industry
        module_count: Number of modules to generate (default: 10)

    Calls Claude CLI to generate a Software Requirements Specification
    with the specified number of functional modules.
    """
    bridge = AIBridge()

    prompt = f"""Generate a Software Requirements Specification (SRS) for the following software:

Software Name: {software_name}
Industry: {industry}
Target OS: Linux
Development Tool: VSCode

IMPORTANT: Design modules SPECIFICALLY for "{software_name}" in the {industry} industry.
Each module must be relevant to the software's purpose and target users.
Think about what functions this software actually needs based on its name and industry.

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

IMPORTANT: Return ONLY a valid JSON array with exactly {module_count} modules.
The array structure must be:
[
  {{
    "name": "模块名称",
    "description": "模块描述",
    "features": ["功能1", "功能2", "功能3"]
  }}
]

Do not include any other text or explanation - just the JSON array."""

    print(f"\n  🤖 调用 Claude CLI 生成 SRS ({module_count} 个模块)...")

    try:
        result = bridge.call_claude_cli(prompt, json_mode=True)

        # Parse the result - claude CLI returns JSON with "result" field
        if result.strip().startswith("{"):
            try:
                response_data = json.loads(result)
                # Extract the result field from CLI response
                if "result" in response_data:
                    result = response_data["result"]
            except json.JSONDecodeError:
                pass

        # Clean up the result - extract JSON array from markdown code blocks
        result = result.strip()

        # Remove markdown code blocks (```json ... ```)
        if result.startswith("```json"):
            result = result[7:]
        elif result.startswith("```"):
            result = result[3:]

        if result.endswith("```"):
            result = result[:-3]

        result = result.strip()

        # Try to find JSON array in the response
        if result.startswith("[") and result.endswith("]"):
            return result

        # Look for JSON array within text
        json_match = re.search(r'\[\s*\{.*\}\s*\]', result, re.DOTALL)
        if json_match:
            return json_match.group(0)

        # If we can't find JSON, return the raw result
        return result

    except RuntimeError as e:
        raise RuntimeError(
            f"Claude CLI 调用失败，无法生成 SRS。\n"
            f"错误信息: {e}\n"
            f"请确保：\n"
            f"  1. Claude Code CLI 已正确安装\n"
            f"  2. 网络连接正常\n"
            f"  3. API 密钥有效"
        )


def generate_html_code_auto(module_name: str, software_name: str,
                              target_lines: int = None, module_info: Dict = None) -> str:
    """
    Auto-generate HTML/CSS code for a module using Claude CLI.

    Args:
        module_name: Name of the module (in Chinese)
        software_name: Name of the software
        target_lines: Target line count for the HTML file (None for unlimited)
        module_info: Dictionary with 'description' and 'features'

    Returns:
        Generated HTML code
    """
    bridge = AIBridge()

    # Build module context
    description = module_info.get('description', '') if module_info else f'{module_name}的功能实现页面'
    features = module_info.get('features', []) if module_info else []

    features_text = '\n'.join([f'        - {f}' for f in features])

    # Build prompt based on whether target_lines is specified
    if target_lines:
        line_requirement = f"4. Target approximately {target_lines} lines of code (including blank lines and comments)"
    else:
        line_requirement = "4. Generate sufficient code to fully implement all features with proper styling and functionality"

    prompt = f"""Generate a complete HTML/CSS page for a software module with the following specifications:

Software Name: {software_name}
Module Name: {module_name}
Module Description: {description}
Module Features:
{features_text}

Requirements:
1. Create a professional, clean UI with modern design
2. Use blue (#3498db) as the primary color
3. Include all necessary CSS styles in a <style> tag
{line_requirement}
5. The page should be a functional UI for this module
6. Include:
   - Header with module name and breadcrumbs
   - Main content area with relevant UI elements
   - Sidebar with navigation options
   - Footer with copyright info
   - Appropriate buttons, forms, tables, or other elements based on module type

CRITICAL: Your response must contain ONLY the HTML code. Start with <!DOCTYPE html> and end with </html>.
Do NOT include any explanation, introduction, or summary.
Do NOT use markdown code blocks (```html).
Do NOT say things like "Here's the HTML" or "I've created".
Just output the raw HTML code directly."""

    print(f"\n  🤖 调用 Claude CLI 生成 HTML 代码...")

    try:
        result = bridge.call_claude_cli(prompt, json_mode=True)

        # Parse the result - claude CLI returns JSON with "result" field
        if result.strip().startswith("{"):
            try:
                response_data = json.loads(result)
                # Extract the result field from CLI response
                if "result" in response_data:
                    result = response_data["result"]
            except json.JSONDecodeError:
                pass

        # Clean up the result - remove markdown code blocks if present
        result = result.strip()

        # Remove ```html and ``` markers
        if result.startswith("```html"):
            result = result[7:]
        elif result.startswith("```"):
            result = result[3:]

        if result.endswith("```"):
            result = result[:-3]

        result = result.strip()

        # Ensure it starts with <!DOCTYPE html>
        if not result.startswith("<!DOCTYPE") and not result.startswith("<html"):
            # Try to find HTML content - look for <!DOCTYPE or <html tag
            html_match = re.search(r'<!DOCTYPE html>.*|<html[^>]*>.*', result, re.DOTALL | re.IGNORECASE)
            if html_match:
                result = html_match.group(0)
            else:
                # If still no HTML found, this might be descriptive text only
                # Raise error to trigger fallback
                raise ValueError("返回内容不包含有效 HTML 代码")

        # Validate the result looks like HTML
        if not ("<html" in result.lower() and "<body" in result.lower() and "</html>" in result.lower()):
            raise ValueError("返回内容不是完整的 HTML 文档")

        return result

    except (RuntimeError, ValueError) as e:
        print(f"  ⚠️  Claude CLI 生成失败: {e}")
        print(f"  📋 使用内置模板作为备用方案...")
        return _generate_html_fallback(module_name, software_name, target_lines, module_info)


def _generate_html_fallback(module_name: str, software_name: str,
                             target_lines: int = None, module_info: Dict = None) -> str:
    """Fallback HTML generation with a basic template."""
    # This is a simplified version - generates content based on actual functionality
    description = module_info.get('description', '') if module_info else ''
    features = module_info.get('features', []) if module_info else []

    lines = []
    lines.append(f"<!-- {module_name} - {software_name} -->")
    lines.append(f"<!-- {description} -->")
    lines.append(f"<!DOCTYPE html>")
    lines.append(f'<html lang="zh-CN">')
    lines.append(f"<head>")
    lines.append(f'    <meta charset="UTF-8">')
    lines.append(f'    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
    lines.append(f'    <title>{module_name} - {software_name}</title>')
    lines.append(f"    <style>")
    lines.append(f"        /* CSS Styles */")
    lines.append(f"        * {{ margin: 0; padding: 0; box-sizing: border-box; }}")
    lines.append(f"        body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; background: #f5f5f5; }}")
    lines.append(f"        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}")
    lines.append(f"        header {{ background: #3498db; color: white; padding: 20px; }}")
    lines.append(f"        main {{ background: white; padding: 30px; margin-top: 20px; }}")
    lines.append(f"        .feature {{ padding: 10px; margin: 10px 0; background: #f9f9f9; }}")
    lines.append(f"        footer {{ text-align: center; padding: 20px; color: #666; }}")
    lines.append(f"    </style>")
    lines.append(f"</head>")
    lines.append(f"<body>")
    lines.append(f"    <div class='container'>")
    lines.append(f"        <header><h1>{module_name}</h1></header>")
    lines.append(f"        <main>")
    lines.append(f"            <h2>功能概述</h2>")
    lines.append(f"            <p>{description}</p>")
    lines.append(f"            <h2>主要功能</h2>")

    for feature in features:
        lines.append(f"            <div class='feature'>✓ {feature}</div>")

    lines.append(f"        </main>")
    lines.append(f"        <footer>&copy; 2024 {software_name}</footer>")
    lines.append(f"    </div>")
    lines.append(f"</body>")
    lines.append(f"</html>")

    # No padding - return actual content only
    return '\n'.join(lines)


def expand_document_template(template_content: str, variables: Dict[str, str],
                              doc_type: str = "manual") -> str:
    """
    Expand document template using Claude CLI to add detailed content.

    Args:
        template_content: The template with variables already replaced
        variables: Dictionary of variables used in the template
        doc_type: Type of document ("function_manual", "install_manual", "registration_form")

    Returns:
        Expanded document content
    """
    bridge = AIBridge()

    software_name = variables.get("software_name", "")
    industry = variables.get("industry", "")

    # Build context-specific prompts
    prompts = {
        "function_manual": f"""请对以下软件功能说明书模板进行扩写，添加详细的内容：

软件名称: {software_name}
面向行业: {industry}

要求：
1. 保持模板的整体结构和格式
2. **章节层级规范**：一级章节使用 markdown 一级标题（#），二级章节使用 markdown 二级标题（##），三级章节使用 markdown 三级标题（###）。确保层级关系正确，不要混用。
3. 对每个功能模块进行详细描述（300-500字/模块）
4. 添加具体的功能说明、使用方法、操作步骤
5. 使用专业的技术文档语言
6. 内容要符合软件著作权申请的要求

模板内容如下：
```
{template_content}
```

请直接返回扩写后的完整文档内容，不要添加任何解释说明。""",

        "install_manual": f"""请对以下软件安装说明书模板进行扩写，添加详细的安装配置内容：

软件名称: {software_name}
面向行业: {industry}
目标操作系统: Linux
开发工具: VSCode

要求：
1. 保持模板的整体结构和格式
2. **章节层级规范**：一级章节使用 markdown 一级标题（#），二级章节使用 markdown 二级标题（##），三级章节使用 markdown 三级标题（###）。文档标题使用一级标题，主要章节（如环境准备、安装说明等）使用二级标题，子章节使用三级标题。确保层级关系正确。
3. 添加详细的环境要求、安装步骤、配置说明
4. 包含常见问题和解决方案
5. 使用专业的技术文档语言
6. 内容要符合软件著作权申请的要求
7. **重要**：不要添加"测试报告模板"章节，只保留安装相关的内容

模板内容如下：
```
{template_content}
```

请直接返回扩写后的完整文档内容，不要添加任何解释说明。""",

        "registration_form": f"""请对以下软件著作权登记信息表模板进行完善和扩写：

软件名称: {software_name}
面向行业: {industry}
版本号: {variables.get("version", "V1.0")}
完成日期: {variables.get("comp_date", "")}

要求：
1. 保持表格的整体格式
2. 对各项内容进行详细、准确的填写
3. **字数限制**：
   - "开发目的"部分不超过50字
   - "软件的技术特点"部分不超过100字
4. **程序量处理**：如果模板中显示的行数是X，则在最终输出中写为{{X}}0（例如：1000行写为10000）
5. 使用规范的著作权申请语言
6. 确保内容符合软件著作权登记要求
7. 只保留一个"软件的主要功能"条目，删除重复的条目

模板内容如下：
```
{template_content}
```

请直接返回完善后的完整表格内容，不要添加任何解释说明。"""
    }

    prompt = prompts.get(doc_type, prompts["function_manual"])

    print(f"\n  🤖 调用 Claude CLI 扩写 {doc_type}...")

    try:
        result = bridge.call_claude_cli(prompt, json_mode=True)

        # Parse the result - claude CLI returns JSON with "result" field
        if result.strip().startswith("{"):
            try:
                response_data = json.loads(result)
                if "result" in response_data:
                    result = response_data["result"]
            except json.JSONDecodeError:
                pass

        # Clean up the result - remove markdown code blocks if present
        result = result.strip()

        if result.startswith("```"):
            result = result.split("\n", 1)[1] if "\n" in result else result[3:]
        if result.endswith("```"):
            result = result[:-3].rstrip()

        result = result.strip()

        # Validate result is not empty and longer than template
        if len(result) < len(template_content) * 0.5:
            raise ValueError("扩写内容过短")

        print(f"  ✓ 扩写完成 ({len(result)} 字符)")
        return result

    except (RuntimeError, ValueError) as e:
        print(f"  ⚠️  Claude CLI 扩写失败: {e}")
        print(f"  📋 使用原始模板...")
        return template_content


if __name__ == "__main__":
    # Test the bridge
    bridge = AIBridge()

    # Check for pending request
    request = bridge.check_request()
    if request:
        print(f"检测到请求: {request.task_type}")
        print(f"输出文件: {request.output_file}")

        # Auto-generate SRS if that's the request
        if request.task_type == "srs":
            software_name = request.context.get("software_name", "")
            industry = request.context.get("industry", "")
            content = generate_srs_auto(software_name, industry)
            bridge.complete_request(content)
            print("✓ SRS 生成完成!")
    else:
        print("没有待处理的请求")
