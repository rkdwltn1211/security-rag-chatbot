import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from langchain_core.embeddings import Embeddings
import ingest


class LocalEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[1.0, float(len(text)), 1.0] for text in texts]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


class ExtractionTests(unittest.TestCase):
    def test_normal_text_never_uses_ocr(self):
        page = Mock()
        text = 'Existing text must remain unchanged. ' * 10
        page.get_text.return_value = text
        self.assertEqual(ingest.extract_page_text(page), (text, False))
        page.get_textpage_ocr.assert_not_called()

    def test_short_text_only_page_never_uses_ocr(self):
        page = Mock()
        page.get_text.return_value = 'Title'
        page.get_images.return_value = []
        page.get_drawings.return_value = []
        self.assertEqual(ingest.extract_page_text(page), ('Title', False))
        page.get_textpage_ocr.assert_not_called()

    def test_scanned_page_uses_korean_and_english_ocr(self):
        page = Mock()
        page.get_text.side_effect = ['', '한국어 English OCR result']
        page.get_images.return_value = [object()]
        with tempfile.TemporaryDirectory() as directory:
            for language in ('kor', 'eng'):
                (Path(directory) / f'{language}.traineddata').touch()
            self.assertEqual(ingest.extract_page_text(page, tessdata=directory), ('한국어 English OCR result', True))
            page.get_textpage_ocr.assert_called_once_with(language='kor+eng', dpi=300, full=True, tessdata=directory)

    def test_missing_ocr_data_fails_explicitly(self):
        page = Mock()
        page.get_text.return_value = ''
        page.get_images.return_value = [object()]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, 'setup_ocr'):
                ingest.extract_page_text(page, tessdata=directory)

    def test_vector_outlined_page_also_uses_ocr(self):
        page = Mock()
        page.get_text.side_effect = ['', 'Outlined Korean text']
        page.get_images.return_value = []
        page.get_drawings.return_value = [object()]
        with tempfile.TemporaryDirectory() as directory:
            for language in ('kor', 'eng'):
                (Path(directory) / f'{language}.traineddata').touch()
            self.assertEqual(ingest.extract_page_text(page, tessdata=directory), ('Outlined Korean text', True))

    def test_failed_recognition_preserves_native_text(self):
        page = Mock()
        page.get_text.side_effect = ['Native heading', '']
        page.get_images.return_value = [object()]
        with tempfile.TemporaryDirectory() as directory:
            for language in ('kor', 'eng'):
                (Path(directory) / f'{language}.traineddata').touch()
            self.assertEqual(ingest.extract_page_text(page, tessdata=directory), ('Native heading', True))


class StorageTests(unittest.TestCase):
    @patch.object(ingest, 'OpenAIEmbeddings', return_value=LocalEmbeddings())
    def test_reingest_deduplicates_and_preserves_source_metadata(self, _):
        # Chroma itself is real; only embeddings are local to avoid external API calls.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            chunk = {'text': 'OCR 한국어 English', 'source': 'scan.pdf', 'page': 3, 'permission': 'EMPLOYEE'}
            store = ingest.save_to_vectorstore([chunk], directory)
            ingest.save_to_vectorstore([chunk], directory)
            self.assertEqual(len(store.get()['ids']), 1)
            newer = {**chunk, 'text': 'Updated OCR 한국어 English'}
            ingest.save_to_vectorstore([newer], directory)
            result = store.get()
            self.assertEqual(result['documents'], [newer['text']])
            self.assertEqual(result['metadatas'], [{'source': 'scan.pdf', 'page': 3, 'permission': 'EMPLOYEE'}])


if __name__ == '__main__':
    unittest.main()
