"""원문 변조 회귀와 자동 검증의 한계를 확인한다. 표준 라이브러리만 사용."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import subprocess
import xml.etree.ElementTree as ET
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from uc_common import load_ir, review_status
spec = importlib.util.spec_from_file_location('claims', ROOT / 'scripts/validate-claims.py')
claims = importlib.util.module_from_spec(spec)
spec.loader.exec_module(claims)

class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.ir = load_ir(ROOT / 'examples/runs/architecture/claim-ir.json')

    def test_examples(self):
        for path in sorted(ROOT.rglob('claim-ir.json')):
            with self.subTest(path=path):
                self.assertFalse(claims.check(load_ir(path)).errors)

    def test_forged_line(self):
        self.ir['source']['units'][0]['line_start'] = 99999
        self.assertTrue(any(i['gate'] == 'G6' for i in claims.check(self.ir).errors))

    def test_forged_source(self):
        self.ir['source']['units'][0]['text'] = '가짜 원문'
        self.assertTrue(any(i['gate'] == 'G6' for i in claims.check(self.ir).errors))

    def test_missing_source(self):
        self.ir['meta']['source_path'] = 'missing-source.md'
        self.assertTrue(any(i['gate'] == 'G6' for i in claims.check(self.ir).errors))

    def test_relative_path_independent_of_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = ROOT / 'examples/runs/architecture/source.md'
            (folder / 'source.md').write_bytes(source.read_bytes())
            ir = copy.deepcopy(self.ir)
            ir.pop('_ir_path')
            (folder / 'claim-ir.json').write_text(json.dumps(ir), encoding='utf-8')
            self.assertFalse(claims.check(load_ir(folder / 'claim-ir.json')).errors)

    def test_semantic_distortion_is_not_semantic_pass(self):
        self.ir['claims'][0]['text'] = '이 시스템은 생산 서버의 모든 데이터를 외부로 전송한다'
        status = review_status(self.ir)
        self.assertEqual(status['semantic']['source_to_claim'], 'not-reviewed')
        self.assertIn('보장하지', status['scope'])

    def test_omitted_claim_is_not_coverage_review(self):
        units = [c['source_location'] for c in self.ir['claims']]
        victim = next(c for c in self.ir['claims'] if units.count(c['source_location']) > 1)
        self.ir['claims'].remove(victim)
        self.assertEqual(review_status(self.ir)['semantic']['coverage'], 'not-reviewed')

    def test_forged_verification_is_unverified_record(self):
        c = self.ir['claims'][0]
        c['verification'] = {'method': 'fake', 'reference': 'https://invalid.example', 'result': 'confirmed', 'checked_at': '2026-10-04'}
        status = review_status(self.ir)
        self.assertEqual(status['external']['status'], 'recorded-unverified')
        self.assertTrue(any('진위' in i['msg'] for i in claims.check(self.ir).warnings))

    def test_review_requires_audit_fields(self):
        self.ir['reviews'] = {'coverage': {'status': 'reviewed'}}
        self.assertTrue(any(i['where'] == 'reviews.coverage' for i in claims.check(self.ir).errors))

    def test_build_reports_scope_and_offline_svg(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/build-report.py'),
                str(ROOT / 'examples/runs/architecture/claim-ir.json'), '--out', directory], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = Path(directory)
            report = json.loads((output / 'gate-report.json').read_text())
            self.assertEqual(report['validation']['semantic']['coverage'], 'not-reviewed')
            viewer = (output / 'viewer.html').read_text()
            self.assertIn('의미 정확성', viewer)
            svgs = list((output / 'diagrams').glob('*.svg'))
            self.assertTrue(svgs)
            for svg in svgs:
                ET.fromstring(svg.read_text())
            self.assertIn('_svg', viewer)

    def test_plan_references(self):
        self.ir['explanation_plan'] = {'audience':'담당자','goal':'검토','opening_question':'왜?','depth':'quick','questions':[{'question':'왜?','claims':['C99999']}]}
        self.assertTrue(any(i['gate']=='G2' for i in claims.check(self.ir).errors))

if __name__ == '__main__':
    unittest.main()
