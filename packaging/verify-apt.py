#!/usr/bin/env python3
"""Verify a Pages deployment through HTTPS, allowing certificate/cache propagation."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

spec = importlib.util.spec_from_file_location('publisher', Path(__file__).with_name('publish-apt.py'))
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


def manifest(root):
    return {p.relative_to(root).as_posix(): publisher.digest(p)
            for p in sorted(root.rglob('*')) if p.is_file() and p.name not in ('.nojekyll', 'CNAME')}


def verify(expected, url, timeout=1800):
    deadline = time.monotonic() + timeout
    with tempfile.TemporaryDirectory(prefix='ptos-https-') as temporary:
        root = Path(temporary)
        for relative, sha256 in expected.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            while True:
                try:
                    # Validate the ordinary APT URL, including its normal caches.
                    request = urllib.request.Request(url + '/' + relative, method='HEAD')
                    with urllib.request.urlopen(request, timeout=30):
                        pass
                    publisher.fetch(url + '/' + relative, path)
                    if publisher.digest(path) != sha256:
                        raise ValueError('Old deployment or incorrect bytes')
                    break
                except (urllib.error.URLError, TimeoutError, ValueError) as error:
                    if time.monotonic() >= deadline:
                        raise ValueError(f'Public deployment did not converge for {relative}: {error}') from error
                    print(f'Waiting for HTTPS/Pages propagation: {relative}', flush=True)
                    time.sleep(15)
        for args in [('dists/stable/InRelease',),
                     ('dists/stable/Release.gpg', 'dists/stable/Release'),
                     ('apt-state.json.gpg', 'apt-state.json')]:
            subprocess.run(['gpgv', '--keyring', str(root / 'ptos-archive-keyring.gpg'),
                            *(str(root / p) for p in args)], check=True)
        publisher.validate_index_references(root)
    print('Public HTTPS bytes, package references, by-hash and signatures verified')


if __name__ == '__main__':
    if sys.argv[1] == '--manifest':
        print(json.dumps(manifest(Path(sys.argv[2])), sort_keys=True))
    else:
        verify(json.loads(Path(sys.argv[1]).read_text()), 'https://apt.ptos.dev')
