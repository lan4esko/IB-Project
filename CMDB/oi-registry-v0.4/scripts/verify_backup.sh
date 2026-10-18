#!/usr/bin/env bash
# Validates outer archive and all internal file hashes without modifying a running service.
set -Eeuo pipefail
[[ $# -eq 1 ]] || { echo "Usage: $0 /full/path/oi-registry-YYYYMMDD-HHMMSS.tar.gz" >&2; exit 2; }
[[ -r "$1" ]] || { echo "Archive not readable: $1" >&2; exit 1; }
python3 - "$1" <<'PY'
import hashlib,json,pathlib,sys,tarfile
path=pathlib.Path(sys.argv[1]).resolve()
sidecar=pathlib.Path(str(path)+'.sha256')
if sidecar.exists():
    expected=sidecar.read_text().strip().split()[0]
    actual=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): actual.update(block)
    if expected!=actual.hexdigest(): raise SystemExit('ERROR: SHA256 of archive differs from sidecar')
    print('Outer archive checksum OK')
else:
    print('Warning: .sha256 file absent, internal checksums will still be verified')
with tarfile.open(path,'r:gz') as archive:
    names=[m.name for m in archive.getmembers()]
    required={'database.dump','documents.tar.gz','application.tar.gz','config.env','manifest.json'}
    if set(names)!=required or any(not m.isfile() for m in archive.getmembers()):
        raise SystemExit(f'ERROR: invalid archive contents: {names}')
    manifest=json.load(archive.extractfile('manifest.json'))
    if manifest.get('format')!='oi-registry-backup' or manifest.get('format_version')!=1:
        raise SystemExit('ERROR: unsupported backup format')
    manifest_names={e['file'] for e in manifest['files']}
    if manifest_names!=required-{'manifest.json'}: raise SystemExit('ERROR: incomplete manifest')
    for entry in manifest['files']:
        reader=archive.extractfile(entry['file']);digest=hashlib.sha256();length=0
        for block in iter(lambda:reader.read(1024*1024),b''):
            digest.update(block);length+=len(block)
        if digest.hexdigest()!=entry['sha256'] or length!=entry['size']:
            raise SystemExit('ERROR: damaged file '+entry['file'])
        print(f"Verified: {entry['file']} ({length} bytes)")
    # Check that nested document tar has a correctly formed archive header and that
    # its files are not absolute paths or traversal attempts.
    with tarfile.open(fileobj=archive.extractfile('documents.tar.gz'),mode='r|gz') as docs:
        for item in docs:
            parts=pathlib.PurePosixPath(item.name).parts
            if not parts or parts[0]!='documents' or '..' in parts or item.name.startswith('/'):
                raise SystemExit('ERROR: unsafe document path')
            if item.issym() or item.islnk():
                raise SystemExit('ERROR: unexpected symbolic link in documents')
print('BACKUP VERIFIED OK:',path)
PY
