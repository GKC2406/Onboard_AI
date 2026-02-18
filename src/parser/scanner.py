"""
Scans a project directory and collects file metadata.
Uses ignore patterns so we don't index node_modules, .git, venv, etc.
"""

import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Iterator

# Default ignore patterns (gitignore-style)
DEFAULT_IGNORE = [
    "node_modules",
    ".git",
    "__pycache__",
    "*.pyc",
    ".venv",
    "venv",
    "env",
    ".env",
    "dist",
    "build",
    "*.egg-info",
    ".next",
    ".nuxt",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    "*.min.js",
    "*.min.css",
]


@dataclass
class FileInfo:
    path: str
    relative_path: str
    extension: str
    size_bytes: int
    line_count: int | None = None
    language_hint: str = ""
    # New fields for enhanced indexing
    top_level_symbols: list[str] = None  # function/class names
    role_hint: str = ""  # entrypoint, api_handler, component, service, config
    framework_hint: str = ""  # react, express, django, etc.
    
    def __post_init__(self):
        if self.top_level_symbols is None:
            self.top_level_symbols = []


def _matches_ignore(relative_path: str, ignore_patterns: list[str]) -> bool:
    parts = relative_path.replace("\\", "/").split("/")
    for pattern in ignore_patterns:
        if not pattern.strip():
            continue
        if pattern.startswith("*."):
            # extension match
            if relative_path.endswith(pattern[1:]):
                return True
        if pattern in parts or relative_path.startswith(pattern + "/") or relative_path == pattern:
            return True
    return False


def _count_lines(path: Path, max_read: int = 5000) -> int | None:
    """Count lines in file; cap read for large files."""
    try:
        with open(path, "rb") as f:
            count = 0
            for _ in f:
                count += 1
                if count >= max_read:
                    return None  # large file, skip exact count
            return count
    except Exception:
        return None


def scan_project(
    root: str | Path,
    ignore_patterns: list[str] | None = None,
    include_hidden: bool = False,
) -> list[FileInfo]:
    """
    Walk the project tree and collect FileInfo for each file.
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(str(root))
    ignore = ignore_patterns or DEFAULT_IGNORE
    out: list[FileInfo] = []
    try:
        for path in root.rglob("*"):
            if path.is_file():
                try:
                    rel = path.relative_to(root)
                    rel_str = str(rel).replace("\\", "/")
                except ValueError:
                    continue
                if not include_hidden and any(p.startswith(".") for p in rel.parts):
                    continue
                if _matches_ignore(rel_str, ignore):
                    continue
                ext = path.suffix.lower() if path.suffix else ""
                size = path.stat().st_size
                line_count = _count_lines(path)
                lang = _extension_to_language(ext)
                # Extract enhanced metadata
                symbols = _extract_top_level_symbols(path)
                role = _detect_role_hint(rel_str)
                framework = _detect_framework_hint(rel_str)
                
                out.append(
                    FileInfo(
                        path=str(path),
                        relative_path=rel_str,
                        extension=ext,
                        size_bytes=size,
                        line_count=line_count,
                        language_hint=lang,
                        top_level_symbols=symbols,
                        role_hint=role,
                        framework_hint=framework,
                    )
                )
    except PermissionError:
        pass
    return sorted(out, key=lambda f: f.relative_path)


def _extension_to_language(ext: str) -> str:
    m = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".vue": "vue",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
    }
    return m.get(ext, "")


# === Enhanced Indexing Functions ===

def _extract_top_level_symbols(path: Path) -> list[str]:
    """Extract top-level function and class names from a file using regex."""
    ext = path.suffix.lower()
    symbols = []
    
    try:
        content = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return symbols
    
    if ext == ".py":
        pattern = r'^(?:def|class)\s+(\w+)'
        for line in content.splitlines():
            match = re.match(pattern, line.strip())
            if match:
                symbols.append(match.group(1))
    
    elif ext in (".js", ".jsx", ".ts", ".tsx"):
        patterns = [
            r'^(?:export\s+)?function\s+(\w+)',
            r'^(?:export\s+)?class\s+(\w+)',
            r'^(?:export\s+)?const\s+(\w+)\s*=',
            r'^(?:export\s+)?let\s+(\w+)\s*=',
        ]
        for line in content.splitlines():
            for pattern in patterns:
                match = re.match(pattern, line.strip())
                if match:
                    symbols.append(match.group(1))
                    break
    
    return symbols[:10]


def _detect_role_hint(relative_path: str) -> str:
    """Detect the role of a file based on its path using heuristics."""
    path_lower = relative_path.lower()
    parts = path_lower.split('/')
    filename = parts[-1] if parts else ""
    
    
    role_patterns = {
        "config": ["config", "settings", ".env", "constants", "requirements", "package.json", "pyproject"],
        "entrypoint": ["main", "app", "index", "__main__", "run", "cli", "server"],
        "api_handler": ["api", "route", "endpoint", "controller", "handler"],
        "component": ["component", "widget", "ui", "view", "page", "task_guide", "guide"],
        "service": ["service", "client", "provider", "manager", "reader", "builder", "scanner", "pipeline"],
        "model": ["model", "schema", "entity", "type"],
        "middleware": ["middleware", "interceptor"],
        "test": ["test", "spec", "__tests__"],
        "util": ["util", "helper", "lib", "utils"],
    }
    
    for role, keywords in role_patterns.items():
        for keyword in keywords:
            if keyword in filename:
                return role
            for part in parts[:-1]:
                if keyword in part:
                    return role
    
    if filename in ["main.py", "app.py", "server.py", "index.js"]:
        return "entrypoint"
    
    return "generic"


def _detect_framework_hint(relative_path: str) -> str:
    """Detect the framework/tech stack based on file path."""
    path_lower = relative_path.lower()
    
    # Check for documentation files first - they are documentation, not framework-specific
    if path_lower.endswith('.md') or path_lower.endswith('.txt'):
        return "documentation"
    
    # framework detection - order matters!
    framework_indicators = {
        "crewai": ["crew", "crewai", "ollama", "agent"],
        "gspread": ["sheet", "google", "spreadsheet", "gspread", "reader"],
        "langchain": ["langchain", "llm", "embedding"],
        "react": ["components", "pages", "hooks", "/component", "/page"],
        "vue": ["vue", "/views"],
        "nextjs": ["next.config", "/app"],
        "express": ["routes", "express"],
        "fastapi": ["fastapi"],
        "django": ["settings.py", "models.py", "views.py", "urls.py", "manage.py"],
        "flask": ["flask"],
    }
    
    for framework, indicators in framework_indicators.items():
        for indicator in indicators:
            if indicator in path_lower:
                return framework
    
    return ""
