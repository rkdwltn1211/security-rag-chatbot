"""Install pinned official Tesseract Korean/English data for PyMuPDF's built-in OCR."""
import hashlib
from pathlib import Path
from urllib.request import urlopen

LANGUAGES = {
    'kor': '6b85e11d9bbf07863b97b3523b1b112844c43e713df8b66418a081fd1060b3b2',
    'eng': '7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2',
}


def install():
    directory = Path(__file__).resolve().parent / '.tessdata'
    directory.mkdir(exist_ok=True)
    for language, expected_hash in LANGUAGES.items():
        path = directory / f'{language}.traineddata'
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash:
            print(f'{language}: verified')
            continue
        url = f'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/{language}.traineddata'
        with urlopen(url, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != expected_hash:
            raise RuntimeError(f'{language}: OCR data checksum mismatch')
        temporary = path.with_suffix('.tmp')
        temporary.write_bytes(data)
        temporary.replace(path)
        print(f'{language}: installed and verified')


if __name__ == '__main__':
    install()
