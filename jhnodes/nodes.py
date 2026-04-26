import hashlib
import gc
import os

from .utils import VIDEO_EXTENSIONS, file_change_hash, list_folder_entries, normalize_folder
from .video_reader import load_single_image, read_video_as_image_batch

CATEGORY_NAME = "JHnodes"
BIGMAX = 0xFFFFFFFF
DIMMAX = 8192


class AnyType(str):
    def __ne__(self, other):
        return False


ANY_TYPE = AnyType("*")


def _import_optional(module_name):
    try:
        return __import__(module_name, fromlist=["*"]), None
    except Exception as exc:
        return None, exc


def _call_if_present(target, name, status, *args, **kwargs):
    func = getattr(target, name, None)
    if func is None:
        return False
    try:
        func(*args, **kwargs)
        return True
    except Exception as exc:
        status.append(f"{name} failed: {exc}")
        return False


def _clear_torch_cache(status):
    torch, exc = _import_optional("torch")
    if torch is None:
        status.append(f"torch unavailable: {exc}")
        return

    cuda = getattr(torch, "cuda", None)
    if cuda is not None:
        try:
            if cuda.is_available():
                _call_if_present(cuda, "synchronize", status)
                _call_if_present(cuda, "empty_cache", status)
                _call_if_present(cuda, "ipc_collect", status)
                status.append("cleared torch CUDA cache")
                return
        except Exception as exc:
            status.append(f"CUDA cache clear failed: {exc}")

    for backend_name in ("mps", "xpu", "npu", "mlu"):
        backend = getattr(torch, backend_name, None)
        if backend is None:
            continue
        try:
            is_available = getattr(backend, "is_available", lambda: True)
            if is_available():
                if _call_if_present(backend, "empty_cache", status):
                    status.append(f"cleared torch {backend_name} cache")
                return
        except Exception as exc:
            status.append(f"{backend_name} cache clear failed: {exc}")

    status.append("no active torch accelerator cache")


def clear_memory_cache(unload_models=False, clear_cuda=True, collect_python=True):
    status = []

    model_management, exc = _import_optional("comfy.model_management")
    if model_management is None:
        status.append(f"ComfyUI model_management unavailable: {exc}")
    else:
        if unload_models:
            if _call_if_present(model_management, "unload_all_models", status):
                status.append("unloaded ComfyUI models")
        if _call_if_present(model_management, "cleanup_models_gc", status):
            status.append("ran ComfyUI model GC")
        if _call_if_present(model_management, "cleanup_models", status):
            status.append("cleaned ComfyUI model registry")
        soft_empty_cache = getattr(model_management, "soft_empty_cache", None)
        if soft_empty_cache is not None:
            try:
                soft_empty_cache(force=True)
                status.append("ran ComfyUI soft_empty_cache")
            except TypeError:
                try:
                    soft_empty_cache()
                    status.append("ran ComfyUI soft_empty_cache")
                except Exception as cache_exc:
                    status.append(f"soft_empty_cache failed: {cache_exc}")
            except Exception as cache_exc:
                status.append(f"soft_empty_cache failed: {cache_exc}")

    if clear_cuda:
        _clear_torch_cache(status)

    if collect_python:
        collected = gc.collect()
        status.append(f"released {collected} Python objects")

    return "; ".join(status) if status else "nothing selected"


class ClearMemoryCache:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "anything": (ANY_TYPE, {"forceInput": True}),
                "unload_models": ("BOOLEAN", {"default": False}),
                "clear_cuda": ("BOOLEAN", {"default": True}),
                "collect_python": ("BOOLEAN", {"default": True}),
            }
        }

    CATEGORY = CATEGORY_NAME
    DESCRIPTION = "Clear ComfyUI/PyTorch/Python memory caches and pass input through."
    RETURN_TYPES = (ANY_TYPE, "STRING")
    RETURN_NAMES = ("output", "status")
    FUNCTION = "run"

    def run(self, anything, unload_models, clear_cuda, collect_python):
        status = clear_memory_cache(
            unload_models=unload_models,
            clear_cuda=clear_cuda,
            collect_python=collect_python,
        )
        return (anything, status)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")


class ClearMemoryCacheNow:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "unload_models": ("BOOLEAN", {"default": False}),
                "clear_cuda": ("BOOLEAN", {"default": True}),
                "collect_python": ("BOOLEAN", {"default": True}),
            }
        }

    CATEGORY = CATEGORY_NAME
    DESCRIPTION = "Clear ComfyUI/PyTorch/Python memory caches when this output node runs."
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("status",)
    FUNCTION = "run"
    OUTPUT_NODE = True

    def run(self, unload_models, clear_cuda, collect_python):
        status = clear_memory_cache(
            unload_models=unload_models,
            clear_cuda=clear_cuda,
            collect_python=collect_python,
        )
        return (status,)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")


class FolderCount:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder": (
                    "STRING",
                    {
                        "default": "",
                        "placeholder": "X://path/to/folder",
                        "vhs_path_extensions": [],
                    },
                ),
                "start_index": ("INT", {"default": 0, "min": 0, "max": BIGMAX, "step": 1}),
                "limit": ("INT", {"default": 0, "min": 0, "max": BIGMAX, "step": 1}),
            }
        }

    CATEGORY = CATEGORY_NAME
    RETURN_TYPES = ("INT", "STRING", "INT", "INT")
    RETURN_NAMES = ("count", "folder", "start_index", "limit")
    FUNCTION = "run"

    def run(self, folder, start_index, limit):
        folder_clean = normalize_folder(folder)
        if not os.path.isdir(folder_clean):
            raise FileNotFoundError(f"Folder not found: {folder}")
        entries = list_folder_entries(folder_clean)
        if start_index > 0:
            entries = entries[start_index:]
        if limit > 0:
            entries = entries[:limit]
        return (len(entries), folder_clean, start_index, limit)

    @classmethod
    def IS_CHANGED(cls, folder, start_index=0, limit=0):
        h = hashlib.sha256()
        entries = list_folder_entries(folder)
        if start_index > 0:
            entries = entries[start_index:]
        if limit > 0:
            entries = entries[:limit]
        for p in entries:
            h.update(file_change_hash(p).encode())
        return h.hexdigest() or "empty"


class LoadFolderItem:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder": (
                    "STRING",
                    {
                        "default": "",
                        "placeholder": "X://path/to/folder",
                        "vhs_path_extensions": [],
                    },
                ),
                "index": ("INT", {"default": 0, "min": 0, "max": BIGMAX, "step": 1}),
                "force_rate": ("FLOAT", {"default": 0, "min": 0, "max": 60, "step": 1}),
                "custom_width": ("INT", {"default": 0, "min": 0, "max": DIMMAX, "step": 8}),
                "custom_height": ("INT", {"default": 0, "min": 0, "max": DIMMAX, "step": 8}),
                "frame_load_cap": ("INT", {"default": 0, "min": 0, "max": BIGMAX, "step": 1}),
                "skip_first_frames": ("INT", {"default": 0, "min": 0, "max": BIGMAX, "step": 1}),
                "select_every_nth": ("INT", {"default": 1, "min": 1, "max": BIGMAX, "step": 1}),
            },
            "optional": {
                "start_index": (
                    "INT",
                    {"default": 0, "min": 0, "max": BIGMAX, "step": 1, "forceInput": True},
                ),
                "limit": (
                    "INT",
                    {"default": 0, "min": 0, "max": BIGMAX, "step": 1, "forceInput": True},
                ),
            }
        }

    CATEGORY = CATEGORY_NAME
    RETURN_TYPES = ("IMAGE", "INT", "AUDIO", "VHS_VIDEOINFO", "STRING")
    RETURN_NAMES = ("IMAGE", "frame_count", "audio", "video_info", "filename")
    FUNCTION = "run"

    def run(self, folder, index, force_rate, custom_width, custom_height,
            frame_load_cap, skip_first_frames, select_every_nth, start_index=0, limit=0):
        entries = list_folder_entries(folder)
        if not entries:
            raise FileNotFoundError(f"No video/image files in: {folder}")
        if limit > 0 and index >= limit:
            raise IndexError(f"index {index} outside limited range [0, {limit})")

        entry_index = start_index + index
        if not 0 <= entry_index < len(entries):
            raise IndexError(f"index {entry_index} out of range [0, {len(entries)})")

        path = entries[entry_index]
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
    def IS_CHANGED(cls, folder, index, start_index=0, limit=0, **kwargs):
        entries = list_folder_entries(folder)
        if limit > 0 and index >= limit:
            return f"OOL:{index}/{limit}"
        entry_index = start_index + index
        if 0 <= entry_index < len(entries):
            return file_change_hash(entries[entry_index])
        return f"OOR:{entry_index}/{len(entries)}"
