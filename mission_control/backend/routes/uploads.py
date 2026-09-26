"""Bounded, validated image uploads with unique filenames and failure cleanup."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import uuid
import warnings
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from .tasks import get_task

router = APIRouter(tags=['uploads'])
_UPLOAD_ROOT = Path(__file__).resolve().parent.parent / 'uploaded_images'
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_FILES = 20
MAX_PIXELS = 20_000_000


def validate_image(content):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.width * image.height > MAX_PIXELS:
                    raise ValueError('Image exceeds 20 megapixels')
                extensions = {'JPEG': '.jpg', 'PNG': '.png', 'BMP': '.bmp', 'GIF': '.gif'}
                suffix = extensions.get(image.format)
                if suffix is None:
                    raise ValueError('Supported formats: JPEG, PNG, BMP, GIF')
                image.verify()
            # verify() alone does not decode truncated JPEG pixel data.
            with Image.open(BytesIO(content)) as image:
                image.load()
            return suffix
    except (OSError, ValueError, UnidentifiedImageError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise HTTPException(status_code=400, detail=f'Invalid image: {exc}') from exc


@router.post('/upload-images/{task_id}')
async def upload_images(task_id: str, files: List[UploadFile] = File()) -> dict:
    saved = []
    try:
        get_task(task_id)
        if not 1 <= len(files) <= MAX_FILES:
            raise HTTPException(status_code=400, detail=f'Upload 1 to {MAX_FILES} images')
        total = 0
        dest_dir = _UPLOAD_ROOT / task_id
        for upload in files:
            content = await upload.read(MAX_FILE_BYTES + 1)
            total += len(content)
            if len(content) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
                raise HTTPException(status_code=413, detail='Image/upload size limit exceeded')
            suffix = await run_in_threadpool(validate_image, content)
            dest_dir.mkdir(parents=True, exist_ok=True)
            out_path = dest_dir / (uuid.uuid4().hex + suffix)
            saved.append(out_path)
            with out_path.open('xb') as stream:
                stream.write(content)
        return {'ok': True, 'task_id': task_id,
                'saved_files': [str(p.resolve()) for p in saved], 'count': len(saved)}
    except BaseException:
        for path in saved:
            path.unlink(missing_ok=True)
        raise
    finally:
        for upload in files:
            await upload.close()
