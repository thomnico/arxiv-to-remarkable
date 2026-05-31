"""
Pure Python reMarkable Cloud API client.

Replaces both rmapi (Go CLI) and rm-bridge.mjs (Node.js) with a native
Python implementation using httpx, porting the rmapi-js raw API.

API endpoints:
- Auth: POST https://webapp-prod.cloud.remarkable.engineering/token/json/2/user/new
- Sync (v4 root): GET https://eu.tectonic.remarkable.com/sync/v4/root
- Files (v3): GET/PUT https://eu.tectonic.remarkable.com/sync/v3/files/{hash}
- Root (v3): PUT https://eu.tectonic.remarkable.com/sync/v3/root
- Upload: POST https://internal.cloud.remarkable.com/doc/v2/files
"""

import base64
import hashlib
import json
import os
import re
import struct
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx

# --- Constants ---

AUTH_HOST = "https://webapp-prod.cloud.remarkable.engineering"
RAW_HOST = "https://eu.tectonic.remarkable.com"
UPLOAD_HOST = "https://internal.cloud.remarkable.com"

HASH_RE = re.compile(r"^[0-9a-f]{64}$")


# --- Data types ---


@dataclass
class RawEntry:
    """A low-level entry in the reMarkable file system."""

    hash: str
    type: int  # 80000000 for schema 3 collections, 0 for schema 4 / files
    id: str
    subfiles: int
    size: int


@dataclass
class Entries:
    """Parsed entries file."""

    entries: List[RawEntry]
    id: Optional[str] = None
    size: Optional[int] = None


@dataclass
class DocumentInfo:
    """High-level document information."""

    id: str
    name: str
    type: str  # DocumentType, CollectionType
    parent: str = ""
    last_modified: str = ""
    pinned: bool = False


# --- CRC32C ---

try:
    import crcmod

    _crc32c_fn = crcmod.predefined.mkCrcFun("crc-32c")

    def crc32c(data: bytes) -> int:
        """Compute CRC32C checksum."""
        return _crc32c_fn(data)

except ImportError:
    import zlib

    def crc32c(data: bytes) -> int:  # type: ignore[misc]
        """Compute CRC32 checksum (fallback when crcmod unavailable)."""
        return zlib.crc32(data) & 0xFFFFFFFF


# --- Auth ---


def get_device_token() -> Optional[str]:
    """
    Find the reMarkable device token from known locations.

    Search order:
    1. rmapi config (~Library/Application Support/rmapi/rmapi.conf)
    2. RMAPI_DEVICE_TOKEN environment variable
    3. ~/.local/inkan-doc-rm.token file
    """
    home = Path.home()

    conf_path = home / "Library" / "Application Support" / "rmapi" / "rmapi.conf"
    if conf_path.exists():
        conf_text = conf_path.read_text()
        match = re.search(r"^devicetoken:\s*(.+)$", conf_text, re.MULTILINE)
        if match:
            token = match.group(1).strip()
            if token:
                return token

    env_token = os.environ.get("RMAPI_DEVICE_TOKEN")
    if env_token:
        return env_token

    token_path = home / ".local" / "inkan-doc-rm.token"
    if token_path.exists():
        return token_path.read_text().strip()

    return None


def authenticate(device_token: Optional[str] = None) -> str:
    """
    Exchange a device token for a session token.

    Args:
        device_token: The device token. If None, auto-detected.

    Returns:
        Session token string.

    Raises:
        RuntimeError: If no device token found or auth fails.
    """
    if device_token is None:
        device_token = get_device_token()
    if not device_token:
        raise RuntimeError(
            "No reMarkable device token found. Configure via:\n"
            "  - rmapi config (~Library/Application Support/rmapi/rmapi.conf)\n"
            "  - RMAPI_DEVICE_TOKEN environment variable\n"
            "  - ~/.local/inkan-doc-rm.token file"
        )

    resp = httpx.post(
        f"{AUTH_HOST}/token/json/2/user/new",
        headers={"Authorization": f"Bearer {device_token}"},
        timeout=30.0,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Auth failed ({resp.status_code}): {resp.text}")
    return resp.text


# --- Raw API helpers ---


def _sha256_hex(data: bytes) -> str:
    """Compute SHA-256 hash of data, returned as hex string."""
    return hashlib.sha256(data).hexdigest()


def _crc32c_base64(data: bytes) -> str:
    """Compute CRC32C of data, returned as base64 for x-goog-hash header."""
    crc_val = crc32c(data)
    crc_bytes = struct.pack(">I", crc_val & 0xFFFFFFFF)
    return base64.b64encode(crc_bytes).decode("ascii")


def _parse_entry_line(line: str) -> RawEntry:
    """Parse a single entry line from an entries file."""
    parts = line.split(":")
    if len(parts) != 5:
        raise ValueError(f"Entry line '{line}' not formatted correctly")

    hash_val, type_str, entry_id, subfiles, size = parts

    if type_str == "80000000":
        entry_type = 80000000
    elif type_str == "0":
        entry_type = 0
    else:
        raise ValueError(f"Entry line '{line}' has unknown type '{type_str}'")

    return RawEntry(
        hash=hash_val,
        type=entry_type,
        id=entry_id,
        subfiles=int(subfiles),
        size=int(size),
    )


class RemarkableCloud:
    """
    Pure Python reMarkable Cloud API client.

    Implements the same raw API as rmapi-js RawRemarkable class.
    Uses an immutable hash-addressed file system where each file is
    referenced by its SHA-256 hash.
    """

    def __init__(
        self,
        session_token: str,
        raw_host: str = RAW_HOST,
        upload_host: str = UPLOAD_HOST,
    ) -> None:
        self._session_token = session_token
        self._raw_host = raw_host
        self._upload_host = upload_host
        self._cache: Dict[str, Optional[str]] = {}
        self._cache_lock = threading.Lock()
        self._client = httpx.Client(
            timeout=60.0,
            limits=httpx.Limits(
                max_connections=30,
                max_keepalive_connections=20,
            ),
            headers={"Authorization": f"Bearer {session_token}"},
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "RemarkableCloud":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _request(
        self,
        method: str,
        url: str,
        body: Union[bytes, str, None] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Make an authenticated request to the reMarkable API."""
        req_headers: Dict[str, str] = {}
        if headers:
            req_headers.update(headers)

        content: Optional[bytes] = None
        if isinstance(body, str):
            content = body.encode("utf-8")
        elif isinstance(body, bytes):
            content = body

        resp = self._client.request(
            method, url, content=content, headers=req_headers,
        )

        if not resp.is_success:
            msg = resp.text
            if msg.strip() == '{"message":"precondition failed"}':
                raise RuntimeError(
                    "Generation conflict: root generation was stale; retry"
                )
            raise RuntimeError(
                f"reMarkable API error ({resp.status_code}): {msg}"
            )
        return resp

    # --- Read operations ---

    def get_root_hash(self) -> Tuple[str, int, int]:
        """Get the root hash and current generation.

        Returns:
            Tuple of (hash, generation, schema_version).
        """
        resp = self._request("GET", f"{self._raw_host}/sync/v4/root")
        data = resp.json()
        hash_val = data["hash"]
        generation = data["generation"]
        schema_version = data.get("schemaVersion", 3)

        if schema_version not in (3, 4):
            raise RuntimeError(
                f"Schema version {schema_version} not supported"
            )

        return (hash_val, int(generation), schema_version)

    def _get_hash_raw(self, hash_val: str, file_name: str) -> bytes:
        """Fetch raw bytes for a given hash.

        The API requires an ``rm-filename`` header on GETs; rmapi-js uses the
        logical file name (``"<id>.docSchema"`` for entry files, or the file's
        full id like ``"<docid>.metadata"`` for leaf files).
        """
        if not HASH_RE.match(hash_val):
            raise ValueError(f"Invalid hash: {hash_val}")
        resp = self._request(
            "GET",
            f"{self._raw_host}/sync/v3/files/{hash_val}",
            headers={"rm-filename": file_name},
        )
        return resp.content

    def get_hash(self, hash_val: str, file_name: str) -> bytes:
        """Get binary data for a hash, with caching."""
        with self._cache_lock:
            cached = self._cache.get(hash_val)
        if cached is not None:
            return cached.encode("utf-8")
        data = self._get_hash_raw(hash_val, file_name)
        with self._cache_lock:
            if hash_val not in self._cache:
                self._cache[hash_val] = None
        return data

    def get_buffer(self, hash_val: str, file_name: str) -> bytes:
        """Get binary data for a hash (alias for get_hash)."""
        return self.get_hash(hash_val, file_name)

    def get_text(self, hash_val: str, file_name: str) -> str:
        """Get text content for a hash, with full caching."""
        with self._cache_lock:
            cached = self._cache.get(hash_val)
        if cached is not None:
            return cached
        data = self._get_hash_raw(hash_val, file_name)
        text = data.decode("utf-8")
        with self._cache_lock:
            self._cache[hash_val] = text
        return text

    def get_entries(self, hash_val: str, file_name: str) -> Entries:
        """Parse and return entries for a given hash.

        Works with both schema version 3 and 4. ``file_name`` is the logical
        name of the entries file (``"root.docSchema"`` for root, otherwise
        ``"<entry_id>.docSchema"``).
        """
        raw_file = self.get_text(hash_val, file_name)
        lines = raw_file.rstrip("\n").split("\n")
        version = lines[0]
        rest = lines[1:]

        if version == "3":
            entries = [_parse_entry_line(line) for line in rest]
            return Entries(entries=entries)
        elif version == "4":
            if not rest:
                raise RuntimeError("Missing info line for schema version 4")
            info = rest[0]
            remaining = rest[1:]
            parts = info.split(":")
            if len(parts) != 4 or parts[0] != "0":
                raise RuntimeError(
                    f"Schema 4 info line '{info}' not formatted correctly"
                )
            _, entry_id, count_str, size_str = parts
            entries = [_parse_entry_line(line) for line in remaining]
            expected_count = int(count_str)
            if expected_count != len(entries):
                raise RuntimeError(
                    f"Schema 4 expected {expected_count} entries, "
                    f"found {len(entries)}"
                )
            return Entries(
                entries=entries, id=entry_id, size=int(size_str)
            )
        else:
            raise RuntimeError(f"Schema version {version} not supported")

    # --- Write operations ---

    def put_root_hash(
        self, hash_val: str, generation: int, broadcast: bool = True
    ) -> Tuple[str, int]:
        """Update the root hash.

        Args:
            hash_val: New root hash.
            generation: Current generation (for conflict detection).
            broadcast: Whether to broadcast the change.

        Returns:
            Tuple of (new_hash, new_generation).
        """
        if not HASH_RE.match(hash_val):
            raise ValueError(f"Invalid root hash: {hash_val}")

        body = json.dumps({
            "hash": hash_val,
            "generation": generation,
            "broadcast": broadcast,
        })

        resp = self._request(
            "PUT", f"{self._raw_host}/sync/v3/root", body=body
        )
        data = resp.json()
        return (data["hash"], int(data["generation"]))

    def _put_file_raw(
        self, hash_val: str, file_name: str, data: bytes
    ) -> None:
        """Upload a file by hash if not already cached."""
        if hash_val in self._cache:
            return

        crc_b64 = _crc32c_base64(data)
        self._request(
            "PUT",
            f"{self._raw_host}/sync/v3/files/{hash_val}",
            body=data,
            headers={
                "rm-filename": file_name,
                "x-goog-hash": f"crc32c={crc_b64}",
            },
        )
        if hash_val not in self._cache:
            self._cache[hash_val] = None

    def put_file(self, file_id: str, data: bytes) -> RawEntry:
        """Upload a file and return its entry.

        Args:
            file_id: The file identifier (e.g., "docid.pdf").
            data: Raw bytes to upload.

        Returns:
            RawEntry for the uploaded file.
        """
        hash_val = _sha256_hex(data)
        entry = RawEntry(
            hash=hash_val, type=0, id=file_id,
            subfiles=0, size=len(data),
        )
        self._put_file_raw(hash_val, file_id, data)
        return entry

    def put_text(self, file_id: str, text: str) -> RawEntry:
        """Upload text content and return its entry."""
        data = text.encode("utf-8")
        entry = self.put_file(file_id, data)
        self._cache[entry.hash] = text
        return entry

    def put_entries(
        self, entry_id: str, entries: List[RawEntry], schema_version: int
    ) -> RawEntry:
        """Create and upload an entries file.

        Args:
            entry_id: "root" for root entries, or document ID.
            entries: List of entries to include.
            schema_version: 3 or 4.

        Returns:
            RawEntry for the entries file.
        """
        sorted_entries = sorted(entries, key=lambda e: e.id)
        total_size = sum(e.size for e in sorted_entries)

        records = [f"{schema_version}\n"]
        if schema_version == 4:
            name = "." if entry_id == "root" else entry_id
            records.append(
                f"0:{name}:{len(sorted_entries)}:{total_size}\n"
            )

        for e in sorted_entries:
            records.append(
                f"{e.hash}:{e.type}:{e.id}:{e.subfiles}:{e.size}\n"
            )

        entry_text = "".join(records)
        entry_bytes = entry_text.encode("utf-8")

        if schema_version == 3:
            hash_bytes = b""
            for e in sorted_entries:
                hash_bytes += bytes.fromhex(e.hash)
            hash_val = _sha256_hex(hash_bytes)
        elif schema_version == 4:
            hash_val = _sha256_hex(entry_bytes)
        else:
            raise RuntimeError(
                f"Unsupported schema version {schema_version}"
            )

        result = RawEntry(
            id=entry_id, hash=hash_val,
            type=0 if schema_version > 3 else 80000000,
            subfiles=len(sorted_entries), size=total_size,
        )

        self._put_file_raw(
            hash_val, f"{entry_id}.docSchema", entry_bytes
        )
        return result

    def upload_file(
        self, visible_name: str, data: bytes, mime: str,
    ) -> Dict[str, str]:
        """Upload a file via the simple upload API (v2).

        Args:
            visible_name: Display name on the reMarkable.
            data: File bytes.
            mime: MIME type (application/pdf, application/epub+zip, folder).

        Returns:
            Dict with 'id' and 'hash' keys.
        """
        meta_json = json.dumps({"file_name": visible_name})
        meta_b64 = base64.b64encode(
            meta_json.encode("utf-8")
        ).decode("ascii")

        resp = self._request(
            "POST",
            f"{self._upload_host}/doc/v2/files",
            body=data,
            headers={
                "Content-Type": mime,
                "rm-meta": meta_b64,
                "rm-source": "RoR-Browser",
            },
        )
        result = resp.json()
        return {"id": result["docID"], "hash": result["hash"]}


# --- High-level API ---


# --- Listing cache ---

_CACHE_PATH = Path.home() / ".local" / "inkan-doc-rm-listing.json"
_CACHE_MAX_AGE = 300  # 5 minutes


def _load_listing_cache() -> Optional[List[Dict[str, Any]]]:
    """Load cached document listing if fresh enough."""
    if not _CACHE_PATH.exists():
        return None
    try:
        cache = json.loads(_CACHE_PATH.read_text())
        age = time.time() - cache.get("ts", 0)
        if age < _CACHE_MAX_AGE:
            return cache.get("docs", [])
    except Exception:
        pass
    return None


def _save_listing_cache(documents: List["DocumentInfo"]) -> None:
    """Save document listing to cache file."""
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        cache = {
            "ts": time.time(),
            "docs": [
                {
                    "id": d.id, "name": d.name, "type": d.type,
                    "parent": d.parent, "last_modified": d.last_modified,
                    "pinned": d.pinned,
                }
                for d in documents
            ],
        }
        _CACHE_PATH.write_text(json.dumps(cache))
    except Exception:
        pass


def invalidate_listing_cache() -> None:
    """Delete the listing cache file."""
    try:
        _CACHE_PATH.unlink(missing_ok=True)
    except Exception:
        pass


def _docs_from_cache(
    cached: List[Dict[str, Any]],
) -> List["DocumentInfo"]:
    """Convert cached dicts back to DocumentInfo objects."""
    return [
        DocumentInfo(
            id=d["id"], name=d["name"], type=d["type"],
            parent=d.get("parent", ""),
            last_modified=d.get("last_modified", ""),
            pinned=d.get("pinned", False),
        )
        for d in cached
    ]


# --- High-level API ---


def _connect(device_token: Optional[str] = None) -> RemarkableCloud:
    """Create an authenticated RemarkableCloud instance."""
    session_token = authenticate(device_token)
    return RemarkableCloud(session_token)


def check_connection(device_token: Optional[str] = None) -> Dict[str, str]:
    """Check connection to reMarkable cloud.

    Returns:
        Dict with 'status', 'rootHash', 'generation' keys.
    """
    with _connect(device_token) as api:
        root_hash, generation, _ = api.get_root_hash()
        return {
            "status": "ok",
            "rootHash": root_hash[:16],
            "generation": str(generation),
        }


_metadata_errors: List[str] = []


def _get_entry_metadata(
    api: RemarkableCloud, entry: RawEntry
) -> Optional[Dict[str, Any]]:
    """Fetch metadata for a single entry. Returns metadata dict or None."""
    try:
        item_entries = api.get_entries(entry.hash, f"{entry.id}.docSchema")
        meta_entry = next(
            (e for e in item_entries.entries
             if e.id.endswith(".metadata")),
            None,
        )
        if meta_entry:
            text = api.get_text(meta_entry.hash, meta_entry.id)
            return json.loads(text)
    except Exception as e:
        _metadata_errors.append(str(e))
    return None


def _list_documents_remote(
    api: RemarkableCloud,
    max_workers: int = 5,
) -> List[DocumentInfo]:
    """Fetch full document listing from cloud using parallel metadata fetch.

    Only fetches metadata (name, type, parent). No document content is
    downloaded. Results are cached to ~/.local/inkan-doc-rm-listing.json.
    Uses 5 workers to avoid 429 rate limiting.
    """
    root_hash, _, _ = api.get_root_hash()
    root_entries = api.get_entries(root_hash, "root.docSchema")

    documents: List[DocumentInfo] = []

    def _fetch_one(entry: RawEntry) -> Tuple[RawEntry, Optional[Dict[str, Any]]]:
        meta = _get_entry_metadata(api, entry)
        return (entry, meta)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_fetch_one, entry): entry
            for entry in root_entries.entries
        }
        for future in as_completed(futures):
            entry, meta = future.result()
            if meta:
                documents.append(DocumentInfo(
                    id=entry.id,
                    name=meta.get("visibleName", entry.id),
                    type=meta.get("type", "DocumentType"),
                    parent=meta.get("parent", ""),
                    last_modified=meta.get("lastModified", ""),
                    pinned=meta.get("pinned", False),
                ))
            else:
                documents.append(
                    DocumentInfo(id=entry.id, name=entry.id, type="unknown")
                )

    _save_listing_cache(documents)
    return documents


def list_documents(
    filter_path: Optional[str] = None,
    device_token: Optional[str] = None,
    refresh: bool = False,
) -> List[DocumentInfo]:
    """List documents on the reMarkable cloud.

    Uses a local cache (~/.local/inkan-doc-rm-listing.json) to avoid
    scanning all entries on every call. Cache expires after 5 minutes.

    Args:
        filter_path: Optional name filter (case-insensitive substring).
        device_token: Optional device token.
        refresh: Force refresh from cloud (ignore cache).

    Returns:
        List of DocumentInfo objects.
    """
    if not refresh:
        cached = _load_listing_cache()
        if cached is not None:
            documents = _docs_from_cache(cached)
            if filter_path:
                fl = filter_path.lower()
                documents = [d for d in documents if fl in d.name.lower()]
            return documents

    with _connect(device_token) as api:
        documents = _list_documents_remote(api)

    if filter_path:
        fl = filter_path.lower()
        documents = [d for d in documents if fl in d.name.lower()]
    return documents


def search_document(
    name: str,
    device_token: Optional[str] = None,
) -> Optional[DocumentInfo]:
    """Find a single document by exact name.

    Uses cache for instant lookup. Falls back to cloud if not cached.

    Args:
        name: Exact visible name of the document.
        device_token: Optional device token.

    Returns:
        DocumentInfo if found, None otherwise.
    """
    # Try cache first
    cached = _load_listing_cache()
    if cached is not None:
        docs = _docs_from_cache(cached)
        for doc in docs:
            if doc.name == name:
                return doc
        return None

    # No cache — do full listing (populates cache for next time)
    docs = list_documents(device_token=device_token, refresh=True)
    for doc in docs:
        if doc.name == name:
            return doc
    return None


def download_document(
    doc_name: str,
    output_path: str,
    device_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Download a document from reMarkable cloud as .rmdoc (zip).

    Uses cached listing to resolve name→ID instantly, then downloads
    only the target document's files.

    Args:
        doc_name: Visible name of the document.
        output_path: Path to save the .rmdoc file.

    Returns:
        Dict with download status and metadata.

    Raises:
        RuntimeError: If document not found.
    """
    # Resolve name to ID via cache or listing
    doc_info = search_document(doc_name, device_token=device_token)
    if doc_info is None:
        raise RuntimeError(f"Document not found: {doc_name}")

    with _connect(device_token) as api:
        # Find the entry by ID in root
        root_hash, _, _ = api.get_root_hash()
        root_entries = api.get_entries(root_hash, "root.docSchema")

        target_entry: Optional[RawEntry] = None
        for entry in root_entries.entries:
            if entry.id == doc_info.id:
                target_entry = entry
                break

        if target_entry is None:
            raise RuntimeError(f"Document entry not found: {doc_name}")

        item_entries = api.get_entries(
            target_entry.hash, f"{target_entry.id}.docSchema"
        )
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_entry in item_entries.entries:
                try:
                    data = api.get_buffer(file_entry.hash, file_entry.id)
                    zf.writestr(file_entry.id, data)
                except Exception:
                    try:
                        text = api.get_text(file_entry.hash, file_entry.id)
                        zf.writestr(file_entry.id, text)
                    except Exception:
                        pass

        zip_data = buf.getvalue()
        out_path.write_bytes(zip_data)

        return {
            "status": "ok",
            "path": str(out_path),
            "id": target_entry.id,
            "size": len(zip_data),
            "files": len(item_entries.entries),
        }


def upload_document(
    file_path: str,
    destination: Optional[str] = None,
    device_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Upload a document to reMarkable cloud.

    Supports PDF, EPUB, and .rmdoc/.zip files.

    Args:
        file_path: Path to the file to upload.
        destination: Optional destination folder (currently unused).
        device_token: Optional device token.

    Returns:
        Dict with upload status and metadata.

    Raises:
        FileNotFoundError: If file doesn't exist.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = path.suffix.lower()

    with _connect(device_token) as api:
        if ext in (".rmdoc", ".zip"):
            return _upload_rmdoc(api, path)
        else:
            return _upload_simple(api, path, ext)


def _upload_rmdoc(
    api: RemarkableCloud, path: Path
) -> Dict[str, Any]:
    """Upload .rmdoc/.zip by decomposing and uploading individual files."""
    zip_data = path.read_bytes()

    with zipfile.ZipFile(BytesIO(zip_data), "r") as zf:
        content_file = next(
            (name for name in zf.namelist()
             if name.endswith(".content") and "/" not in name),
            None,
        )
        if not content_file:
            raise RuntimeError("Invalid .rmdoc: no .content file found")

        doc_id = content_file.replace(".content", "")

        root_hash, generation, schema_version = api.get_root_hash()
        root_entries_obj = api.get_entries(root_hash, "root.docSchema")

        existing_idx = next(
            (i for i, e in enumerate(root_entries_obj.entries)
             if e.id == doc_id),
            -1,
        )

        new_file_entries: List[RawEntry] = []
        for name in zf.namelist():
            info = zf.getinfo(name)
            if info.is_dir():
                continue
            content = zf.read(name)
            entry = api.put_file(name, content)
            new_file_entries.append(entry)

        doc_entry = api.put_entries(
            doc_id, new_file_entries, schema_version
        )

        new_entries = list(root_entries_obj.entries)
        if existing_idx >= 0:
            new_entries[existing_idx] = doc_entry
        else:
            new_entries.append(doc_entry)

        new_root_entry = api.put_entries(
            "root", new_entries, schema_version
        )

        _new_hash, new_gen = api.put_root_hash(
            new_root_entry.hash, generation
        )

        return {
            "status": "ok",
            "id": doc_id,
            "name": path.stem,
            "type": "notebook",
            "generation": str(new_gen),
            "isNew": existing_idx < 0,
        }


def _upload_simple(
    api: RemarkableCloud, path: Path, ext: str
) -> Dict[str, Any]:
    """Upload a PDF or EPUB via the simple upload API."""
    file_data = path.read_bytes()
    name = path.stem

    mime_map = {
        ".pdf": "application/pdf",
        ".epub": "application/epub+zip",
    }
    mime = mime_map.get(ext)
    if not mime:
        raise RuntimeError(f"Unsupported file type: {ext}")

    result = api.upload_file(name, file_data, mime)

    return {
        "status": "ok",
        "name": name,
        "type": ext.lstrip("."),
        "id": result["id"],
        "isNew": True,
    }
