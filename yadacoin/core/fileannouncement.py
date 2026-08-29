"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""
File announcements — on-chain metadata for files stored on pluggable backends.

On-chain format: {"file": <to_dict()>}

The blob itself lives on a storage backend (currently sia.storage).  This
announcement publishes a searchable title, description, keywords, and the
backend file identifier so peers can discover and retrieve the object.
"""

from typing import List

MAX_TITLE_LEN = 200
MAX_DESCRIPTION_LEN = 2000
MAX_KEYWORDS = 32
MAX_KEYWORD_LEN = 64
MAX_FILE_ID_LEN = 128
KNOWN_BACKENDS = frozenset({"sia", "memory"})


def _normalize_keywords(keywords) -> List[str]:
    if keywords is None:
        return []
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",")]
    if not isinstance(keywords, (list, tuple)):
        raise ValueError("keywords must be a list of strings")
    seen = set()
    out = []
    for raw in keywords:
        word = str(raw).strip().lower()
        if not word:
            continue
        if len(word) > MAX_KEYWORD_LEN:
            raise ValueError(
                f"keyword exceeds {MAX_KEYWORD_LEN} characters: {word[:20]!r}..."
            )
        if word not in seen:
            seen.add(word)
            out.append(word)
    if len(out) > MAX_KEYWORDS:
        raise ValueError(f"at most {MAX_KEYWORDS} keywords are allowed")
    return out


class FileAnnouncement:
    """File metadata stored in a transaction relationship field.

    Instructs nodes that a file identified by ``file_id`` is available on
    ``backend``.  Title, description, and keywords are application-defined
    and used for search.

    Fields
    ------
    backend      : storage backend name (e.g. ``sia``)
    file_id      : identifier returned by the backend (Sia Object ID)
    title        : human-readable title
    description  : longer description
    keywords     : list of search keywords
    filename     : original filename (optional)
    mime_type    : MIME type (optional)
    size         : size in bytes (optional)
    supersedes   : transaction id of a previous FileAnnouncement (optional)
    """

    RELATIONSHIP_KEY = "file"

    def __init__(
        self,
        file_id: str,
        title: str,
        backend: str = "sia",
        description: str = "",
        keywords=None,
        filename: str = "",
        mime_type: str = "",
        size=None,
        supersedes: str = "",
        **kwargs,
    ):
        if not file_id or not isinstance(file_id, str):
            raise ValueError("file_id is required and must be a string")
        file_id = file_id.strip()
        if not file_id:
            raise ValueError("file_id is required and must not be blank")
        if len(file_id) > MAX_FILE_ID_LEN:
            raise ValueError(f"file_id exceeds {MAX_FILE_ID_LEN} characters")

        if not title or not str(title).strip():
            raise ValueError("title is required and must not be blank")
        title = str(title).strip()
        if len(title) > MAX_TITLE_LEN:
            raise ValueError(f"title exceeds {MAX_TITLE_LEN} characters")

        backend = str(backend or "sia").strip().lower()
        if not backend:
            raise ValueError("backend is required")

        description = str(description or "")
        if len(description) > MAX_DESCRIPTION_LEN:
            raise ValueError(f"description exceeds {MAX_DESCRIPTION_LEN} characters")

        if size is not None:
            try:
                size = int(size)
            except (TypeError, ValueError):
                raise ValueError("size must be an integer")
            if size < 0:
                raise ValueError("size cannot be negative")

        self.file_id = file_id
        self.title = title
        self.backend = backend
        self.description = description
        self.keywords = _normalize_keywords(keywords)
        self.filename = str(filename or "")
        self.mime_type = str(mime_type or "")
        self.size = size
        self.supersedes = str(supersedes or "")
        self.extra_fields = {k: v for k, v in kwargs.items()}

    @staticmethod
    def from_dict(data: dict) -> "FileAnnouncement":
        """Create from the inner dict (value of relationship["file"])."""
        if not isinstance(data, dict):
            raise ValueError("data must be a dict")
        for field in ("file_id", "title"):
            if field not in data:
                raise ValueError(f"{field} is required")
        return FileAnnouncement(**data)

    @staticmethod
    def from_relationship(relationship: dict) -> "FileAnnouncement":
        """Create from the top-level relationship dict {"file": ...}."""
        if (
            not isinstance(relationship, dict)
            or FileAnnouncement.RELATIONSHIP_KEY not in relationship
        ):
            raise ValueError("relationship must contain a 'file' key")
        return FileAnnouncement.from_dict(
            relationship[FileAnnouncement.RELATIONSHIP_KEY]
        )

    def to_dict(self) -> dict:
        """Serialise for on-chain storage."""
        result = {
            "backend": self.backend,
            "file_id": self.file_id,
            "title": self.title,
            "description": self.description,
            "keywords": list(self.keywords),
        }
        if self.filename:
            result["filename"] = self.filename
        if self.mime_type:
            result["mime_type"] = self.mime_type
        if self.size is not None:
            result["size"] = self.size
        if self.supersedes:
            result["supersedes"] = self.supersedes
        if self.extra_fields:
            result.update(self.extra_fields)
        return result

    def get_string(self, p) -> str:
        return "" if p is None else str(p)

    def to_string(self) -> str:
        """Deterministic preimage for the relationship_hash."""
        return (
            self.get_string(self.backend)
            + self.get_string(self.file_id)
            + self.get_string(self.title)
            + self.get_string(self.description)
            + ",".join(self.keywords)
            + self.get_string(self.supersedes)
        )

    def matches_query(self, query: str) -> bool:
        """Return True if query matches title, description, keywords, or file_id."""
        if not query:
            return True
        q = query.strip().lower()
        if not q:
            return True
        haystacks = [
            self.title.lower(),
            self.description.lower(),
            self.file_id.lower(),
            self.filename.lower(),
            " ".join(self.keywords),
        ]
        return any(q in h for h in haystacks)

    def __repr__(self) -> str:
        return (
            f"FileAnnouncement("
            f"backend={self.backend!r}, "
            f"file_id={self.file_id!r}, "
            f"title={self.title!r})"
        )
