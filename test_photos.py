import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from PIL import Image
from product_photos import save_uploads


def photo(color):
    output=BytesIO()
    Image.new('RGB',(10,10),color).save(output,'PNG')
    return output.getvalue()


def multipart(files):
    body=b''
    for name,raw in files:
        body+=b'--test-boundary\r\nContent-Disposition: form-data; name="photos"; filename="'+name.encode()+b'"\r\nContent-Type: image/png\r\n\r\n'+raw+b'\r\n'
    return 'multipart/form-data; boundary=test-boundary',body+b'--test-boundary--\r\n'


class PhotoTest(unittest.TestCase):
    def test_multiple_photos_deduplication_and_safe_names(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path)
            content,body=multipart([('../../outside.png',photo('red')),('two.png',photo('blue'))])
            urls=save_uploads(content,body,root)
            self.assertEqual(len(urls),2)
            for url in urls:
                self.assertTrue((root/'uploads'/url.rsplit('/',1)[-1]).is_file())
                self.assertNotIn('outside',url)
            self.assertEqual(save_uploads(content,body,root),urls)
            self.assertEqual(len(list((root/'uploads').iterdir())),2)

    def test_invalid_batch_does_not_save_partial_photos(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path)
            content,body=multipart([('one.png',photo('red')),('bad.png',b'<svg onload="alert(1)"></svg>')])
            with self.assertRaises(ValueError):save_uploads(content,body,root)
            self.assertFalse((root/'uploads').exists())
            content,body=multipart([])
            with self.assertRaises(ValueError):save_uploads(content,body,root)


if __name__=='__main__':unittest.main()
