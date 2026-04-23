import os

import cv2
import numpy as np
import torch
from PIL import Image, ImageOps

from .ffmpeg import EMPTY_AUDIO


def _target_size(width, height, custom_width, custom_height, downscale_ratio=8):
    # Mirrors VHS target_size (load_video_nodes.py:56-75).
    if custom_width == 0 and custom_height == 0:
        pass
    elif custom_height == 0:
        height *= custom_width / width
        width = custom_width
    elif custom_width == 0:
        width *= custom_height / height
        height = custom_height
    else:
        width = custom_width
        height = custom_height
    width = int(width / downscale_ratio + 0.5) * downscale_ratio
    height = int(height / downscale_ratio + 0.5) * downscale_ratio
    return width, height


def _resize_batch(images: torch.Tensor, new_w: int, new_h: int) -> torch.Tensor:
    # images: [F, H, W, 3] float32 in [0,1]
    try:
        from comfy.utils import common_upscale
        x = images.movedim(-1, 1)  # [F, 3, H, W]
        x = common_upscale(x, new_w, new_h, "lanczos", "center")
        return x.movedim(1, -1)
    except ImportError:
        out = []
        for frame in images.numpy():
            resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
            out.append(resized)
        return torch.from_numpy(np.stack(out))


def _make_video_info(src_fps, src_frames, src_w, src_h,
                     loaded_fps, loaded_frames, loaded_w, loaded_h, filename):
    src_duration = src_frames / src_fps if src_fps > 0 else 0.0
    loaded_duration = loaded_frames / loaded_fps if loaded_fps > 0 else 0.0
    return {
        "source_fps": float(src_fps),
        "source_frame_count": int(src_frames),
        "source_duration": float(src_duration),
        "source_width": int(src_w),
        "source_height": int(src_h),
        "loaded_fps": float(loaded_fps),
        "loaded_frame_count": int(loaded_frames),
        "loaded_duration": float(loaded_duration),
        "loaded_width": int(loaded_w),
        "loaded_height": int(loaded_h),
        "filename": filename,
    }


def read_video_as_image_batch(
    path: str,
    force_rate: float = 0,
    custom_width: int = 0,
    custom_height: int = 0,
    frame_load_cap: int = 0,
    skip_first_frames: int = 0,
    select_every_nth: int = 1,
):
    """Decodes a video with cv2 following VHS cv_frame_generator's timing logic.

    Returns (images[F,H,W,3] float32 in [0,1], frame_count, lazy_audio, video_info).
    """
    cap = cv2.VideoCapture(path)
    if not cap.isOpened() or not cap.grab():
        raise ValueError(f"{path} could not be loaded with cv.")
    try:
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        src_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if src_w <= 0 or src_h <= 0:
            ok, frame = cap.retrieve()
            if ok and frame is not None:
                src_h, src_w = frame.shape[:2]
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            cap.grab()

        if src_fps <= 0:
            base_frame_time = 1.0
            target_frame_time = 1.0 / force_rate if force_rate > 0 else 1.0
        else:
            base_frame_time = 1.0 / src_fps
            target_frame_time = 1.0 / force_rate if force_rate > 0 else base_frame_time

        frames = []
        total_frame_count = 0
        total_frames_evaluated = -1
        time_offset = target_frame_time
        select_every_nth = max(1, int(select_every_nth))

        while True:
            if time_offset < target_frame_time:
                if not cap.grab():
                    break
                time_offset += base_frame_time
            if time_offset < target_frame_time:
                continue
            time_offset -= target_frame_time

            total_frame_count += 1
            if total_frame_count <= skip_first_frames:
                continue
            total_frames_evaluated += 1
            if total_frames_evaluated % select_every_nth != 0:
                continue

            ok, frame = cap.retrieve()
            if not ok or frame is None:
                break
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(frame.astype(np.float32) / 255.0)

            if frame_load_cap > 0 and len(frames) >= frame_load_cap:
                break
    finally:
        cap.release()

    if not frames:
        raise RuntimeError(f"No frames decoded from: {path}")

    images = torch.from_numpy(np.stack(frames))

    new_w, new_h = _target_size(src_w, src_h, custom_width, custom_height)
    if (new_w, new_h) != (images.shape[2], images.shape[1]):
        images = _resize_batch(images, new_w, new_h)

    loaded_fps = 1.0 / target_frame_time if target_frame_time > 0 else 0.0
    info = _make_video_info(
        src_fps, src_frames, src_w, src_h,
        loaded_fps, images.shape[0], images.shape[2], images.shape[1],
        os.path.basename(path),
    )

    from .ffmpeg import lazy_get_audio
    audio = lazy_get_audio(path)
    return images, images.shape[0], audio, info


def load_single_image(path: str, custom_width: int = 0, custom_height: int = 0):
    img = Image.open(path)
    img = ImageOps.exif_transpose(img).convert("RGB")
    src_w, src_h = img.size
    new_w, new_h = _target_size(src_w, src_h, custom_width, custom_height)
    if (new_w, new_h) != (src_w, src_h):
        img = img.resize((new_w, new_h), Image.LANCZOS)
    arr = np.array(img, dtype=np.float32) / 255.0
    images = torch.from_numpy(arr)[None, ...]
    info = _make_video_info(
        0.0, 1, src_w, src_h,
        0.0, 1, new_w, new_h,
        os.path.basename(path),
    )
    return images, 1, EMPTY_AUDIO, info
