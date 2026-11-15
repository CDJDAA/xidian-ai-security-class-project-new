"""Export selected project 04 academic notes for use in a learning tool."""

import argparse
import re
from pathlib import Path
from urllib.parse import urlsplit


def format_note(path: Path) -> tuple[str, str]:
    if path.suffix.lower() != ".md":
        raise ValueError(f"{path.name}：请选择项目 04 导出的 Markdown 学术笔记")
    content = path.read_text(encoding="utf-8-sig")
    if not content.startswith("---\n"):
        raise ValueError(f"{path.name}：缺少项目 04 学术笔记的元数据")
    metadata, divider, body = content[4:].partition("\n---\n")
    title = re.search(r"^# (.+)$", body, flags=re.MULTILINE)
    summary = re.search(r"^## 自动摘要\s*\n(.*?)(?=^## |\Z)", body, flags=re.MULTILINE | re.DOTALL)
    link = re.search(r"^## 原始链接\s*\n- (\S+)\s*$", body, flags=re.MULTILINE)
    if not divider or 'type: "literature"' not in metadata.splitlines() or not title or not summary or not link:
        raise ValueError(f"{path.name}：缺少学术笔记标题、自动摘要或原始链接")
    source = link[1]
    parsed = urlsplit(source)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"{path.name}：原始链接需要是有效的 HTTP(S) 地址")
    excerpt = summary[1].strip()
    if not excerpt:
        raise ValueError(f"{path.name}：自动摘要为空")
    return source, f"## {title[1].strip()}\n\n- 原文链接：<{source}>\n\n{excerpt}"


def export_notes(notes: list[Path], output: Path) -> int:
    if not notes or output.suffix.lower() != ".md":
        raise ValueError("请选择至少一份笔记，并使用 .md 作为输出文件扩展名")
    entries: dict[str, str] = {}
    for note in notes:
        source, section = format_note(note)
        entries.setdefault(source, section)
    with output.open("x", encoding="utf-8", newline="\n") as file:
        file.write("# 公开文献学习资料\n\n以下内容来自项目 04 归档的自动摘要或摘录。查阅论文全文请打开各条原文链接。\n\n")
        file.write("\n\n".join(entries.values()) + "\n")
    return len(entries)


def main() -> None:
    parser = argparse.ArgumentParser(description="合并选定的学术笔记，生成供 DeepTutor 导入的 Markdown")
    parser.add_argument("notes", type=Path, nargs="+", help="从项目 04 学术知识库选定的 Markdown 笔记路径")
    parser.add_argument("--output", type=Path, required=True, help="待创建的 Markdown 路径")
    args = parser.parse_args()
    try:
        count = export_notes(args.notes, args.output)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"导出失败：{exc}\n")
    print(f"已导出 {count} 篇文献：{args.output}")


if __name__ == "__main__":
    main()
