# SPDX-License-Identifier: MIT
"""The generated work-item report stays in sync with the symbolic change surface."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '00_Tools'))
import change_surface


class WorkItemReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rgbds = change_surface.find_rgbds()
        if cls.rgbds is None:
            raise unittest.SkipTest('RGBDS not available; build it with 00_Tools/build_rgbds.py')
        cls.spec = change_surface.load_spec()

    def test_report_is_current(self):
        expected = change_surface.report(self.spec, None, self.rgbds)
        path = ROOT / 'docs' / 'WORK_ITEMS.md'
        self.assertTrue(path.is_file(), 'docs/WORK_ITEMS.md is missing')
        self.assertEqual(path.read_text(encoding='utf-8'), expected)

    def test_report_covers_every_stage_and_patch(self):
        text = change_surface.report(self.spec, None, self.rgbds)
        self.assertIn('## 00 操作工序', text)
        for number in ('01', '02', '03', '04', '05', '06', '07', '08', '09'):
            self.assertIn('## %s ' % number, text)
        self.assertIn('## 附录 A：全部 116 处补丁', text)
        self.assertIn('## 附录 B：文本条目（121 条）', text)
        self.assertIn('## 附录 C：页面层（48 页）', text)
        self.assertIn('全部 116 处补丁', text)
        self.assertIn('0x00148', text)
        self.assertIn('two_row_vblank_queue_writer', text)
        self.assertIn('stage_1_bundle_pointer', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
