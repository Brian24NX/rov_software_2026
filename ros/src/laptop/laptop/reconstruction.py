"""CPU COLMAP sparse reconstruction with bounded jobs and real output checks."""
from pathlib import Path
import os
import shutil
import struct
import subprocess
import time


def run_colmap(image_dir, work_dir, timeout=600, executable='colmap'):
    binary = shutil.which(executable)
    if binary is None:
        raise RuntimeError('COLMAP is not installed on the laptop')
    image_dir, work_dir = Path(image_dir), Path(work_dir)
    if len(list(image_dir.glob('*.jpg'))) < 3:
        raise ValueError('At least three overlapping images are required')
    work_dir.mkdir(parents=True, exist_ok=True)
    sparse = work_dir / 'sparse'
    sparse.mkdir(exist_ok=True)
    database = work_dir / 'database.db'
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    deadline = time.monotonic() + timeout
    with (work_dir / 'colmap.log').open('w') as log:
        def run(arguments):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('COLMAP job exceeded its time limit')
            try:
                subprocess.run([binary, *arguments], check=True, timeout=remaining,
                               env=environment, stdout=log, stderr=subprocess.STDOUT)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError('Reconstruction exceeded its time limit') from exc
            except subprocess.CalledProcessError as exc:
                log.flush()
                detail = (work_dir / 'colmap.log').read_text(errors='replace')[-8192:]
                if 'No good initial image pair' in detail:
                    raise RuntimeError(
                        'No suitable image pair; capture overlapping views '
                        'from different positions'
                    ) from exc
                raise RuntimeError(
                    f'Reconstruction failed during {arguments[0]}; see {work_dir / "colmap.log"}'
                ) from exc

        # COLMAP 4 renamed the SIFT-only option namespace; support both CLIs.
        help_result = subprocess.run([binary, 'feature_extractor', '-h'],
                                     capture_output=True, text=True, timeout=min(timeout, 15),
                                     env=environment, check=True)
        modern = '--FeatureExtraction.use_gpu' in help_result.stdout + help_result.stderr
        extract = 'FeatureExtraction' if modern else 'SiftExtraction'
        match = 'FeatureMatching' if modern else 'SiftMatching'
        run(['feature_extractor', '--database_path', str(database),
             '--image_path', str(image_dir), '--ImageReader.single_camera', '1',
             f'--{extract}.use_gpu', '0', f'--{extract}.num_threads', '4'])
        run(['exhaustive_matcher', '--database_path', str(database),
             f'--{match}.use_gpu', '0', f'--{match}.num_threads', '4'])
        run(['mapper', '--database_path', str(database), '--image_path', str(image_dir),
             '--output_path', str(sparse), '--Mapper.num_threads', '4'])
        models = []
        for points in sparse.glob('*/points3D.bin'):
            with points.open('rb') as stream:
                header = stream.read(8)
            if len(header) == 8:
                count = struct.unpack('<Q', header)[0]
                if count:
                    models.append((count, points.parent))
        if not models:
            raise RuntimeError(
                'No 3D points reconstructed; capture overlapping views from different positions')
        model = max(models, key=lambda item: item[0])[1]
        output = work_dir / 'model.ply'
        run(['model_converter', '--input_path', str(model), '--output_path', str(output),
             '--output_type', 'PLY'])
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError('COLMAP did not produce a model')
        return output.resolve()
