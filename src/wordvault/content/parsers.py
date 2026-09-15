from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ParseError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ParsedContent:
    text: str
    paragraphs: tuple[str, ...]


class DocumentParser(Protocol):
    def parse(self, path: Path) -> ParsedContent: ...


class DocxParser:
    DOCUMENT_XML = "word/document.xml"
    MAX_DOCUMENT_XML_BYTES = 50 * 1024 * 1024
    WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    def parse(self, path: Path) -> ParsedContent:
        try:
            with zipfile.ZipFile(path) as package:
                info = package.getinfo(self.DOCUMENT_XML)
                if info.file_size > self.MAX_DOCUMENT_XML_BYTES:
                    raise ParseError("DOCX_TOO_LARGE", "文档正文结构超过安全处理上限")
                xml = package.read(info)
            root = ET.fromstring(xml)
        except ParseError:
            raise
        except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as error:
            raise ParseError("DOCX_INVALID", "DOCX 文件损坏、加密或格式不受支持") from error

        paragraph_tag = f"{{{self.WORD_NAMESPACE}}}p"
        text_tag = f"{{{self.WORD_NAMESPACE}}}t"
        paragraphs = []
        for paragraph in root.iter(paragraph_tag):
            text = "".join(node.text or "" for node in paragraph.iter(text_tag)).strip()
            if text:
                paragraphs.append(text)
        return ParsedContent("\n".join(paragraphs), tuple(paragraphs))


class LegacyDocParser:
    """Extract legacy Word text using an available local, non-network tool."""

    def __init__(self, commands: tuple[str, ...] = ("antiword", "catdoc")) -> None:
        self.commands = commands

    def parse(self, path: Path) -> ParsedContent:
        executable = next(
            (shutil.which(command) for command in self.commands if shutil.which(command)), None
        )
        if executable is None:
            raise ParseError("DOC_PARSER_UNAVAILABLE", "当前系统没有可用的旧版 Word 解析组件")
        try:
            completed = subprocess.run(
                [executable, str(path)],
                check=False,
                capture_output=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ParseError("DOC_PARSE_FAILED", "旧版 Word 文档解析失败") from error
        if completed.returncode != 0:
            raise ParseError("DOC_PARSE_FAILED", "旧版 Word 文档解析失败")
        text = self._decode(completed.stdout)
        paragraphs = tuple(line.strip() for line in text.splitlines() if line.strip())
        return ParsedContent("\n".join(paragraphs), paragraphs)

    @staticmethod
    def _decode(content: bytes) -> str:
        for encoding in ("utf-8", "gb18030"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="replace")
