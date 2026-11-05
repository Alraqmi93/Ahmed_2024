"""Validate admin-uploaded raster photos and store them on the persistent disk."""
from email.parser import BytesParser
from email import policy
from hashlib import sha256
from io import BytesIO
import re
from PIL import Image, UnidentifiedImageError

UPLOAD_PATTERN = r'/uploads/[a-f0-9]{64}\.(jpg|png|webp)'
MAX_BODY = 20 * 1024 * 1024


def save_uploads(content_type, body, data_dir):
    if not content_type.startswith('multipart/form-data') or '\r' in content_type or '\n' in content_type:
        raise ValueError('Select photo files / اختر ملفات الصور')
    message=BytesParser(policy=policy.default).parsebytes(('Content-Type: '+content_type+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+body)
    if not message.is_multipart(): raise ValueError('Invalid photo upload')
    parts=[part for part in message.iter_parts() if part.get_filename() is not None]
    if not 1<=len(parts)<=10: raise ValueError('Choose 1–10 photos / اختر من صورة إلى ١٠ صور')
    prepared=[]
    for part in parts:
        raw=part.get_payload(decode=True)
        if not raw or len(raw)>8*1024*1024:
            raise ValueError('Each photo must be at most 8 MB / الحد الأقصى للصورة ٨ ميغابايت')
        try:
            with Image.open(BytesIO(raw)) as image:
                extension={'JPEG':'jpg','PNG':'png','WEBP':'webp'}.get(image.format)
                if not extension or image.width*image.height>20_000_000:
                    raise ValueError('Use JPG, PNG or WebP photos up to 20 megapixels')
                image.verify()
        except (UnidentifiedImageError,OSError,SyntaxError,Image.DecompressionBombError) as error:
            raise ValueError('Invalid or unsupported image / الصورة غير صالحة أو غير مدعومة') from error
        filename=sha256(raw).hexdigest()+'.'+extension
        prepared.append((filename,raw))
    directory=data_dir/'uploads';directory.mkdir(parents=True,exist_ok=True)
    for name,raw in prepared:
        path=directory/name
        if not path.exists():path.write_bytes(raw)
    return list(dict.fromkeys('/uploads/'+name for name,_ in prepared))


def valid_image_url(url):
    return isinstance(url,str) and len(url)<=2000 and (url.startswith('https://') or bool(re.fullmatch(r'/catalog-images/[a-f0-9]{24}\.webp',url)) or bool(re.fullmatch(UPLOAD_PATTERN,url)))
