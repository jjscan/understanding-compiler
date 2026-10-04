import sys
import importlib.util
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from uc_common import Issues, check_ste_style, review_status

class STEStyleTests(unittest.TestCase):
    def test_summary_and_narrative_are_checked(self):
        root=Path(__file__).resolve().parents[1]
        from uc_common import load_ir
        spec=importlib.util.spec_from_file_location('ste_trace',root/'scripts/validate-traceability.py')
        trace=importlib.util.module_from_spec(spec);spec.loader.exec_module(trace)
        ir=load_ir(root/'examples/runs/architecture/claim-ir.json')
        ir['summary'][0]['text']=' '.join(['word']*26)
        ir['narrative']['headline']['text']=' '.join(['word']*26)
        warnings=trace.check(ir).warnings
        self.assertTrue(any(i['where']==ir['summary'][0]['id'] and 'STE 참고' in i['msg'] for i in warnings))
        self.assertTrue(any(i['where']=='narrative.headline' and 'STE 참고' in i['msg'] for i in warnings))

    def test_procedure_limit_differs_from_description(self):
        text=' '.join(['word']*21)
        procedure=Issues(); description=Issues()
        check_ste_style(procedure,'procedure',text,True)
        check_ste_style(description,'description',text)
        self.assertTrue(procedure.warnings); self.assertFalse(description.warnings)
    def test_short_sentences_not_total_length(self):
        issues=Issues()
        check_ste_style(issues,'text',' '.join(['word']*15)+'. '+' '.join(['word']*15)+'.')
        self.assertFalse(issues.warnings)
    def test_advice_does_not_rewrite_or_remove_hedge(self):
        text='The operator may utilize the controller prior to starting the pump.'
        issues=Issues(); check_ste_style(issues,'text',text)
        self.assertEqual(len(issues.warnings),2)
        self.assertIn('may',text)
        self.assertFalse(issues.errors)
    def test_korean_not_claimed_as_formal_ste(self):
        issues=Issues(); check_ste_style(issues,'text',' '.join(['설명']*26))
        self.assertIn('한국어 적용 지침',issues.warnings[0]['msg'])
        self.assertEqual(review_status({})['writing']['formal_compliance'],'not-assessed')
    def test_alias_in_reading_text(self):
        issues=Issues();check_ste_style(issues,'narrative','The executor runs.',entities=[{'name':'Worker','aliases':['executor']}])
        self.assertTrue(any(i['gate']=='G3' for i in issues.warnings))
    def test_passive_procedure_is_advisory(self):
        issues=Issues();check_ste_style(issues,'procedure','The valve is closed.',True)
        self.assertTrue(issues.warnings);self.assertFalse(issues.errors)

if __name__=='__main__': unittest.main()
