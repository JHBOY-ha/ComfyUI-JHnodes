import hashlib
import os

from .utils import VIDEO_EXTENSIONS, file_change_hash, list_folder_entries, normalize_folder
from .video_reader import load_single_image, read_video_as_image_batch

CATEGORY_NAME = "JHnodes"
BIGMAX = 0xFFFFFFFF
DIMMAX = 8192


class FolderCount:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder": ("STRING", {"default": "", "placeholder": "X://path/to/folder"}),
            }
        }

    CATEGORY = CATEGORY_NAME
    RETURN_TYPES = ("INT", "STRING")
    RETURN_NAMES = ("count", "folder")
    FUNCTION = "run"

    def run(self, folder):
        folder_clean = normalize_folder(folder)
        if not os.path.isdir(folder_clean):
            raise FileNotFoundError(f"Folder not found: {folder}")
        return (len(list_folder_entries(folder_clean)), folder_clean)

    @classmethod
    def IS_CHANGED(cls, folder):
        h = hashlib.sha256()
        for p in list_folder_entries(folder):
            h.update(file_change_hash(p).encode())
        return h.hexdigest() or "empty"


class LoadFolderItem:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder": ("STRING", {"default": "", "placeholder": "X://path/to/folder"}),
                "index": ("INT", {"default": 0, "min": 0, "max": BIGMAX, "step": 1}),
                "force_rate": ("FLOAT", {"default": 0, "min": 0, "max": 60, "step": 1}),
                "custom_width": ("INT", {"default": 0, "min": 0, "max": DIMMAX, "step": 8}),
                "custom_height": ("INT", {"default": 0, "min": 0, "max": DIMMAX, "step": 8}),
                "frame_load_cap": ("INT", {"default": 0, "min": 0, "max": BIGMAX, "step": 1}),
                "skip_first_frames": ("INT", {"default": 0, "min": 0, "max": BIGMAX, "step": 1}),
                "select_every_nth": ("INT", {"default": 1, "min": 1, "max": BIGMAX, "step": 1}),
            }
        }

    CATEGORY = CATEGORY_NAME
    RETURN_TYPES = ("IMAGE", "INT", "AUDIO", "VHS_VIDEOINFO", "STRING")
    RETURN_NAMES = ("IMAGE", "frame_count", "audio", "video_info", "filename")
    FUNCTION = "run"

    def run(self, folder, index, force_rate, custom_width, custom_height,
            frame_load_cap, skip_first_frames, select_every_nth):
        entries = list_folder_entries(folder)
        if not entries:
            raise FileNotFoundError(f"No video/image files in: {folder}")
        if not 0 <= index < len(entries):
            raise IndexError(f"index {index} out of range [0, {len(entries)})")

        path = entries[index]
        ext = os.path.splitext(path)[1].lower()
        if ext in VIDEO_EXTENSIONS:
            images, frame_count, audio, info = read_video_as_image_batch(
                path,
                force_rate=force_rate,
                custom_width=custom_width,
                custom_height=custom_height,
                frame_load_cap=frame_load_cap,
                skip_first_frames=skip_first_frames,
                select_every_nth=select_every_nth,
            )
        else:
            images, frame_count, audio, info = load_single_image(
                path, custom_width=custom_width, custom_height=custom_height
            )
        return (images, frame_count, audio, info, os.path.basename(path))

    @classmethod
    def IS_CHANGED(cls, folder, index, **kwargs):
        entries = list_folder_entries(folder)
        if 0 <= index < len(entries):
            return file_change_hash(entries[index])
        return f"OOR:{index}/{len(entries)}"
