import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('check_docs', Path(__file__).resolve().parents[1] / 'scripts/check_docs.py')
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class DocumentationTests(unittest.TestCase):
    def test_local_navigation_and_configuration_examples(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'README.md').write_text('[指南](guide.md#安装)\n[重复](guide.md#安装-1)\n[显式](guide.md#custom)\n')
            (root / 'guide.md').write_text('# 安装\n# 安装\n<a id="custom"></a>\n```json\n{"ok":true}\n```\n```toml\nenabled = true\n```\n')
            self.assertEqual(CHECKER.check(root)['errors'], [])

    def test_broken_navigation_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'README.md').write_text('# Start\n[missing](absent.md)\n[anchor](#absent)\n[escape](../outside.md)\n')
            self.assertEqual(len(CHECKER.check(root)['errors']), 3)

    def test_invalid_examples_and_unclosed_blocks_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'README.md').write_text('<!-- source-only -->\n```json\n{broken}\n```\n```toml\na =\n```\n```text\nopen\n')
            self.assertEqual(len(CHECKER.check(root)['errors']), 4)
