import importlib.util
import json
import pathlib
import tempfile
import types
import unittest

FILE = pathlib.Path(__file__).resolve().parents[1] / 'govsec.py'
spec = importlib.util.spec_from_file_location('govsec', FILE)
govsec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(govsec)

class Checks(unittest.TestCase):
    def test_manifest_19_https_pdf(self):
        docs=govsec.CATALOG['documents']
        self.assertEqual(len(docs),19)
        self.assertEqual(len({x['id'] for x in docs}),19)
        self.assertTrue(all(x['url'].lower().endswith('.pdf') for x in docs))
        self.assertTrue(all(x['url'].startswith('https://') for x in docs))
    def test_partition_long_page_below_rag_limit(self):
        govsec.ARGS=types.SimpleNamespace(ocr=False)
        items=govsec.CATALOG['documents'][0]
        with tempfile.TemporaryDirectory() as d:
            old=govsec.FILES
            govsec.FILES=pathlib.Path(d)
            try:
                parts,missing=govsec.pack_parts(items,['А'*9000,'Б'*9000,'В'*9000])
            finally:
                govsec.FILES=old
        self.assertFalse(missing)
        self.assertGreater(len(parts),1)
        self.assertTrue(all(len(x)<=govsec.MAX_PART_CHARS for x in parts))
        self.assertIn('[Страница PDF: 1]',parts[0])
    def test_empty_scanned_page_marked(self):
        govsec.ARGS=types.SimpleNamespace(ocr=False)
        parts,missing=govsec.pack_parts(govsec.CATALOG['documents'][0],['','Текст с содержанием'*10])
        self.assertEqual(missing,[1])
        self.assertEqual(len(parts),1)
    def test_save_json(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'a.json'
            govsec.save_json(p,{'ключ':'значение'})
            self.assertEqual(json.loads(p.read_text())['ключ'],'значение')
            self.assertFalse(p.with_name('a.json.new').exists())
if __name__=='__main__': unittest.main()
