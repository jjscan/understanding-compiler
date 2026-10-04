"""폐쇄망 경계: 경로 탈출, 외부 로딩, 스크립트 주입과 CSP 무결성."""
import base64
import copy
import hashlib
import html
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import re
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from uc_common import check_source, load_ir
spec = importlib.util.spec_from_file_location('closed_build', ROOT / 'scripts/build-report.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

class ClosedNetworkTests(unittest.TestCase):
    def setUp(self):
        self.ir = load_ir(ROOT / 'examples/runs/architecture/claim-ir.json')

    def test_source_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'run').mkdir()
            (folder / 'outside.md').write_text('秘密')
            self.ir['_ir_path'] = str(folder / 'run/claim-ir.json')
            for path in ['../outside.md', str(folder / 'outside.md')]:
                with self.subTest(path=path):
                    self.ir['meta']['source_path'] = path
                    self.assertTrue(check_source(self.ir).errors)

    def test_source_symlink_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'run').mkdir()
            (folder / 'outside.md').write_text('秘密')
            (folder / 'run/source.md').symlink_to(folder / 'outside.md')
            self.ir['_ir_path'] = str(folder / 'run/claim-ir.json')
            self.assertTrue(check_source(self.ir).errors)

    def test_output_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'output').mkdir()
            secret = folder / 'outside.md'; secret.write_text('preserve')
            (folder / 'output/report.md').symlink_to(secret)
            with patch.object(sys, 'argv', ['build-report', str(ROOT / 'examples/runs/architecture/claim-ir.json'), '--out', str(folder / 'output')]), patch('sys.stderr', new=io.StringIO()):
                with self.assertRaises(SystemExit):
                    build.main()
            self.assertEqual(secret.read_text(), 'preserve')

    def test_offline_build_and_injection_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'source.md').write_bytes((ROOT / 'examples/runs/architecture/source.md').read_bytes())
            self.ir.pop('_ir_path')
            attack = '</script><script>fetch("https://evil.invalid")</script><img src="https://evil.invalid" onerror="alert(1)">'
            self.ir['meta']['title'] = attack
            self.ir['claims'][0]['review_note'] = attack
            (folder / 'claim-ir.json').write_text(json.dumps(self.ir), encoding='utf-8')
            with patch.object(sys, 'argv', ['build-report', str(folder / 'claim-ir.json')]), \
                 patch.object(socket, 'socket', side_effect=AssertionError('network forbidden')), \
                 patch.object(urllib.request, 'urlopen', side_effect=AssertionError('network forbidden')), \
                 patch('sys.stdout', new=io.StringIO()), patch('sys.stderr', new=io.StringIO()):
                build.main()
            viewer = (folder / 'viewer.html').read_text()
            parser = Tags(); parser.feed(viewer)
            self.assertEqual(parser.scripts, 2)
            self.assertFalse(parser.remote_resources)
            self.assertNotIn('cdn.jsdelivr.net', viewer)
            self.assertNotIn('createElement("script")', viewer)
            policy = html.unescape(re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', viewer).group(1))
            for directive in ["default-src 'none'", "connect-src 'none'", "base-uri 'none'", "form-action 'none'"]:
                self.assertIn(directive, policy)
            self.assertNotIn("script-src 'unsafe-inline'", policy)
            for script in re.findall(r'<script>(.*?)</script>', viewer, re.S):
                digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
                self.assertIn("'sha256-" + digest + "'", policy)
            for i, script in enumerate(re.findall(r'<script>(.*?)</script>', viewer, re.S)):
                (folder / f'script-{i}.js').write_text(script)

class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = 0
        self.remote_resources = []
    def handle_starttag(self, tag, attrs):
        if tag == 'script': self.scripts += 1
        for key, value in attrs:
            if key in ('src', 'href', 'action') and value and re.match(r'^(https?:|//)', value):
                self.remote_resources.append(value)

if __name__ == '__main__':
    unittest.main()
