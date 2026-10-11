"""ZIP Compressor and ZIP Extractor services.

Security is the priority here because ZIP is the classic path-traversal vector
("zip-slip") and zip-bomb vector:

* every entry name is normalised and rejected if it escapes the target folder
  (absolute paths, ``..`` segments, drive letters);
* the *uncompressed* size declared in the archive is summed up front and capped,
  so a tiny file that inflates to gigabytes is refused before we write a byte;
* the number of entries is capped;
* the compression ratio per archive is capped as a second bomb guard;
* the expansion is bounded so we never unpack more than we budgeted even if the
  archive lies about its size.

Output filenames are sanitised because a user-supplied "zip name" is echoed back
into a Content-Disposition header.
"""
import os
import re
import shutil
import uuid
import zipfile

from django.conf import settings

# --- Hard limits (env-overridable) ----------------------------------------- #
ZIP_MAX_TOTAL_SIZE = int(os.getenv('ZIP_MAX_TOTAL_SIZE', 100 * 1024 * 1024))
ZIP_MAX_FILES = int(os.getenv('ZIP_MAX_FILES', '200'))
# Refuse an archive whose declared uncompressed size exceeds this (zip bomb).
ZIP_MAX_UNCOMPRESSED = int(os.getenv('ZIP_MAX_UNCOMPRESSED', 1024 * 1024 * 1024))
# Refuse an archive whose overall compression ratio exceeds this (classic bomb).
ZIP_MAX_RATIO = float(os.getenv('ZIP_MAX_RATIO', '200'))
# Absolute cap on bytes written per extraction (second bomb guard).
ZIP_MAX_WRITE_BYTES = ZIP_MAX_UNCOMPRESSED

# Compression level presets -> zlib level. None = stored (no compression);
# 1 = fastest real compression; 6 = balanced; 9 = maximum.
LEVELS = {
    'fast': (1, 'Fast - larger file, quickest'),
    'normal': (6, 'Normal - balanced size and speed'),
    'maximum': (9, 'Maximum - smallest file, slowest'),
}


class ZipSecurityError(Exception):
    """Raised for zip-slip, zip-bomb or oversized archives."""


def _temp_dir():
    d = os.path.join(settings.MEDIA_ROOT, 'temp', 'zip_' + uuid.uuid4().hex)
    os.makedirs(d, exist_ok=True)
    return d


def sanitize_filename(name):
    """Return a safe single-path filename for Content-Disposition.

    Strips directory components and anything that is not alphanumeric, dot,
    dash, underscore or space.
    """
    name = os.path.basename(name or '').strip()
    name = name.replace('\\', '/').split('/')[-1]
    name = re.sub(r'[^A-Za-z0-9._\- ]+', '_', name)
    name = name.strip(' .') or 'download'
    return name[:120]


def _safe_target(base_dir, entry_name):
    """Resolve ``entry_name`` inside ``base_dir`` and ensure it cannot escape.

    Returns the absolute destination path, or raises :class:`ZipSecurityError`.
    """
    # Normalise separators and drop any leading slash / drive letter so an
    # absolute path in the archive cannot write outside the folder.
    cleaned = entry_name.replace('\\', '/').lstrip('/')
    if re.match(r'^[A-Za-z]:', cleaned):
        cleaned = cleaned.split(':', 1)[1].lstrip('/')
    # Reject explicit parent traversal outright.
    if '..' in cleaned.split('/'):
        raise ZipSecurityError(
            "The entry '%s' tries to escape the archive folder and was blocked."
            % entry_name)
    parts = [p for p in cleaned.split('/') if p not in ('', '.')]
    safe_rel = os.path.join(*parts) if parts else os.path.basename(cleaned)
    dest = os.path.normpath(os.path.join(base_dir, safe_rel))
    base_norm = os.path.normpath(base_dir)
    if dest != base_norm and not dest.startswith(base_norm + os.sep):
        raise ZipSecurityError(
            "The entry '%s' points outside the archive folder and was blocked."
            % entry_name)
    return dest


def compress_files(file_paths, level='normal', zip_name=None):
    """Zip a list of saved file paths.

    ``file_paths`` is a list of ``(abs_path, display_name)`` tuples.
    Returns ``(zip_path, display_filename)``.
    """
    if level not in LEVELS:
        level = 'normal'
    zlevel, _ = LEVELS[level]

    zip_path = os.path.join(settings.MEDIA_ROOT, 'temp',
                            uuid.uuid4().hex + '.zip')
    used_names = set()
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=zlevel) as zf:
        for abs_path, display_name in file_paths:
            arcname = sanitize_filename(display_name)
            # De-duplicate names so two files called "a.pdf" don't collide.
            if arcname in used_names:
                stem, ext = os.path.splitext(arcname)
                n = 2
                while '%s_%d%s' % (stem, n, ext) in used_names:
                    n += 1
                arcname = '%s_%d%s' % (stem, n, ext)
            used_names.add(arcname)
            zf.write(abs_path, arcname)

    filename = sanitize_filename(zip_name or 'pdfmaster-files')
    if not filename.lower().endswith('.zip'):
        filename += '.zip'
    return zip_path, filename


def list_zip_contents(zip_path):
    """Return a safe preview of a zip's contents.

    Enforces the bomb / slip / count limits up front and returns a dict with
    ``entries`` (list of ``{'name', 'size'}``), ``count``, ``uncompressed`` and
    ``compressed``. Raises :class:`ZipSecurityError` on any violation.
    """
    with zipfile.ZipFile(zip_path, 'r') as zf:
        infos = zf.infolist()
        if len(infos) > ZIP_MAX_FILES:
            raise ZipSecurityError(
                'This archive has %d entries, over the %d-file limit.'
                % (len(infos), ZIP_MAX_FILES))
        total_uncompressed = 0
        total_compressed = 0
        entries = []
        for info in infos:
            is_dir = info.filename.endswith('/')
            # Validate every path (even directory entries) so a malicious
            # archive is rejected before we unpack anything.
            _safe_target(_temp_dir(), info.filename)
            total_compressed += max(info.compress_size, 1)
            if not is_dir:
                total_uncompressed += info.file_size
                entries.append({
                    'name': info.filename.replace('\\', '/'),
                    'size': info.file_size,
                })
        if total_uncompressed > ZIP_MAX_UNCOMPRESSED:
            raise ZipSecurityError(
                'This archive would expand to more than %d MB, which looks like '
                'a zip bomb. Extraction was blocked.'
                % (ZIP_MAX_UNCOMPRESSED // (1024 * 1024)))
        if total_uncompressed > ZIP_MAX_RATIO * total_compressed:
            raise ZipSecurityError(
                'This archive has an extreme compression ratio and was blocked '
                'as a possible zip bomb.')
        return {
            'entries': entries,
            'count': len(entries),
            'uncompressed': total_uncompressed,
            'compressed': os.path.getsize(zip_path),
        }


def extract_zip(zip_path, only_names=None):
    """Extract a zip into a fresh temp folder, guarding zip-slip and bombs.

    ``only_names`` optionally restricts extraction to a subset of entry names.
    Returns ``(extract_dir, [rel_paths], summary)``.
    """
    # Re-validate before writing anything to disk.
    summary = list_zip_contents(zip_path)
    extract_dir = _temp_dir()
    written = 0
    out_paths = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for info in zf.infolist():
            if info.filename.endswith('/'):
                continue  # directory entry; created implicitly
            if only_names and info.filename not in only_names:
                continue
            dest = _safe_target(extract_dir, info.filename)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            written += max(info.file_size, 0)
            if written > ZIP_MAX_WRITE_BYTES:
                shutil.rmtree(extract_dir, ignore_errors=True)
                raise ZipSecurityError(
                    'Extraction exceeded the %d MB safety limit and was stopped.'
                    % (ZIP_MAX_WRITE_BYTES // (1024 * 1024)))
            with zf.open(info) as src, open(dest, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            out_paths.append(os.path.relpath(dest, extract_dir))
    return extract_dir, out_paths, summary

