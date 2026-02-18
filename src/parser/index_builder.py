"""
Builds a structured index and LLM-friendly summary from scan results.
"""

from .scanner import FileInfo


def build_index(files: list[FileInfo]) -> dict:
    """
    Build a structured index: file tree (text), file list with metadata,
    and by-extension grouping for retrieval.
    """
    tree = _build_tree(files)
    by_ext: dict[str, list[str]] = {}
    file_list = []
    for f in files:
        file_entry = {
            "path": f.relative_path,
            "ext": f.extension,
            "lines": f.line_count,
            "language": f.language_hint,
            # New enhanced fields
            "role": f.role_hint,
            "framework": f.framework_hint,
            "symbols": f.top_level_symbols,
        }
        file_list.append(file_entry)
        key = f.extension or "(no ext)"
        if key not in by_ext:
            by_ext[key] = []
        by_ext[key].append(f.relative_path)
    return {
        "file_tree": tree,
        "files": file_list,
        "by_extension": by_ext,
        "total_files": len(files),
    }


def _build_tree(files: list[FileInfo]) -> str:
    """Produce a simple ASCII file tree (directories and files)."""
    root: dict = {}
    for f in files:
        parts = f.relative_path.replace("\\", "/").split("/")
        node = root
        for i, name in enumerate(parts):
            is_file = i == len(parts) - 1
            if name not in node:
                node[name] = {} if not is_file else None
            if not is_file:
                node = node[name]
    lines: list[str] = []

    def walk(d: dict, prefix: str) -> None:
        keys = sorted(d.keys())
        for i, k in enumerate(keys):
            last = i == len(keys) - 1
            branch = "└── " if last else "├── "
            child = d[k]
            if child is None:
                lines.append(prefix + branch + k)
            else:
                lines.append(prefix + branch + k + "/")
                ext = "    " if last else "│   "
                walk(child, prefix + ext)

    walk(root, "")
    return "\n".join(lines) if lines else "(no files)"


def format_index_for_llm(index: dict, max_files: int = 500) -> str:
    """
    Format the index as a single text block for LLM context.
    Truncate file list if too long.
    """
    parts = [
        "# Codebase structure",
        "",
        "## File tree",
        "```",
        index["file_tree"],
        "```",
        "",
        f"## File list (total: {index['total_files']} files)",
        "",
    ]
    files = index["files"]
    if len(files) > max_files:
        files = files[:max_files]
        parts.append(f"(Showing first {max_files} files; total {index['total_files']})")
        parts.append("")
    for f in files:
        line_info = f" ({f['lines']} lines)" if f.get("lines") else ""
        # Add enhanced metadata
        role = f.get("role", "")
        framework = f.get("framework", "")
        symbols = f.get("symbols", [])
        
        # Build metadata string
        meta_parts = []
        if role and role != "generic":
            meta_parts.append(f"role:{role}")
        if framework:
            meta_parts.append(f"framework:{framework}")
        if symbols:
            symbol_str = ", ".join(symbols[:5])
            if len(symbols) > 5:
                symbol_str += "..."
            meta_parts.append(f"exports:{symbol_str}")
        
        meta_str = f" [{', '.join(meta_parts)}]" if meta_parts else ""
        
        parts.append(f"- {f['path']} [{f['language'] or f['ext']}]{line_info}{meta_str}")
    parts.append("")
    parts.append("## By extension (for retrieval)")
    for ext, paths in sorted(index["by_extension"].items()):
        count = len(paths)
        sample = paths[:10] if count > 10 else paths
        sample_str = ", ".join(sample)
        if count > 10:
            sample_str += f" ... (+{count - 10} more)"
        parts.append(f"- {ext}: {sample_str}")
    return "\n".join(parts)
