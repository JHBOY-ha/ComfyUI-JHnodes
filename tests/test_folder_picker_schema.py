from pathlib import Path
import importlib.util
import sys
import types
import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_nodes_module():
    stub = types.ModuleType("jhnodes.video_reader")
    stub.load_single_image = lambda *args, **kwargs: None
    stub.read_video_as_image_batch = lambda *args, **kwargs: None
    sys.modules.setdefault("jhnodes.video_reader", stub)

    spec = importlib.util.spec_from_file_location("jhnodes.nodes", ROOT / "jhnodes" / "nodes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_root_module():
    spec = importlib.util.spec_from_file_location(
        "jhnodes_root",
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    stub = types.ModuleType("jhnodes_root.jhnodes.video_reader")
    stub.load_single_image = lambda *args, **kwargs: None
    stub.read_video_as_image_batch = lambda *args, **kwargs: None
    sys.modules["jhnodes_root.jhnodes.video_reader"] = stub
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_folder_inputs_expose_vhs_path_picker_metadata():
    nodes_module = load_nodes_module()
    folder_count_inputs = nodes_module.FolderCount.INPUT_TYPES()["required"]
    load_folder_item_types = nodes_module.LoadFolderItem.INPUT_TYPES()
    load_folder_item_inputs = load_folder_item_types["required"]
    load_folder_item_optional = load_folder_item_types["optional"]
    folder_count = folder_count_inputs["folder"]
    load_folder_item = load_folder_item_inputs["folder"]

    assert folder_count[0] == "STRING"
    assert load_folder_item[0] == "STRING"
    assert folder_count[1]["vhs_path_extensions"] == []
    assert load_folder_item[1]["vhs_path_extensions"] == []
    assert folder_count_inputs["start_index"][0] == "INT"
    assert folder_count_inputs["start_index"][1]["default"] == 0
    assert folder_count_inputs["limit"][0] == "INT"
    assert folder_count_inputs["limit"][1]["default"] == 0
    assert nodes_module.FolderCount.RETURN_TYPES == ("INT", "STRING", "INT", "INT")
    assert nodes_module.FolderCount.RETURN_NAMES == ("count", "folder", "start_index", "limit")
    assert "start_index" not in load_folder_item_inputs
    assert "limit" not in load_folder_item_inputs
    assert load_folder_item_optional["start_index"][0] == "INT"
    assert load_folder_item_optional["start_index"][1]["default"] == 0
    assert load_folder_item_optional["start_index"][1]["forceInput"] is True
    assert load_folder_item_optional["limit"][0] == "INT"
    assert load_folder_item_optional["limit"][1]["default"] == 0
    assert load_folder_item_optional["limit"][1]["forceInput"] is True


def test_folder_count_limit_and_start_index_slice_after_filtering(tmp_path):
    nodes_module = load_nodes_module()
    folder = tmp_path / "clips"
    folder.mkdir()

    for name in ["b.mp4", "a.mov", "c.png", "ignore.txt"]:
        (folder / name).write_text("x")

    node = nodes_module.FolderCount()

    assert node.run(str(folder), 0, 0) == (3, str(folder), 0, 0)
    assert node.run(str(folder), 0, 2) == (2, str(folder), 0, 2)
    assert node.run(str(folder), 0, 10) == (3, str(folder), 0, 10)
    assert node.run(str(folder), 1, 0) == (2, str(folder), 1, 0)
    assert node.run(str(folder), 1, 1) == (1, str(folder), 1, 1)
    assert node.run(str(folder), 5, 0) == (0, str(folder), 5, 0)


def test_load_folder_item_offsets_index_by_start_index(tmp_path):
    nodes_module = load_nodes_module()
    folder = tmp_path / "clips"
    folder.mkdir()

    for name in ["b.png", "a.png", "c.png"]:
        (folder / name).write_text("x")

    nodes_module.load_single_image = lambda *args, **kwargs: ("image", 1, "audio", "info")

    node = nodes_module.LoadFolderItem()

    assert node.run(str(folder), 0, 0, 0, 0, 0, 0, 1, start_index=1)[4] == "b.png"
    assert node.run(str(folder), 1, 0, 0, 0, 0, 0, 1, start_index=1)[4] == "c.png"

    with pytest.raises(IndexError, match="outside limited range"):
        node.run(str(folder), 1, 0, 0, 0, 0, 0, 1, start_index=1, limit=1)


def test_normalize_folder_handles_none_as_empty_string():
    from jhnodes.utils import normalize_folder

    assert normalize_folder(None) == ""


def test_package_exports_web_directory_for_frontend_extension():
    module = load_root_module()
    assert module.WEB_DIRECTORY == "./web"
    assert "JHnodes_ClearMemoryCache" in module.NODE_CLASS_MAPPINGS
    assert module.NODE_DISPLAY_NAME_MAPPINGS["JHnodes_ClearMemoryCache"] == "Clear Memory Cache"


def test_clear_memory_cache_node_is_passthrough_and_exposes_controls():
    nodes_module = load_nodes_module()
    node_inputs = nodes_module.ClearMemoryCache.INPUT_TYPES()

    assert node_inputs["required"]["anything"][0] == "*"
    assert node_inputs["required"]["anything"][1]["forceInput"] is True
    assert node_inputs["required"]["unload_models"][0] == "BOOLEAN"
    assert node_inputs["required"]["clear_cuda"][0] == "BOOLEAN"
    assert node_inputs["required"]["collect_python"][0] == "BOOLEAN"
    assert nodes_module.ClearMemoryCache.RETURN_TYPES == ("*", "STRING")
    assert nodes_module.ClearMemoryCache.RETURN_NAMES == ("output", "status")

    sentinel = object()
    calls = []
    original_clear = nodes_module.clear_memory_cache
    nodes_module.clear_memory_cache = lambda **kwargs: calls.append(kwargs) or "ok"
    try:
        assert nodes_module.ClearMemoryCache().run(sentinel, False, True, True) == (sentinel, "ok")
    finally:
        nodes_module.clear_memory_cache = original_clear

    assert calls == [
        {
            "unload_models": False,
            "clear_cuda": True,
            "collect_python": True,
        }
    ]


def test_clear_memory_cache_calls_comfy_torch_and_gc(monkeypatch):
    nodes_module = load_nodes_module()
    calls = []

    comfy = types.ModuleType("comfy")
    model_management = types.ModuleType("comfy.model_management")
    model_management.cleanup_models_gc = lambda: calls.append("cleanup_models_gc")
    model_management.cleanup_models = lambda: calls.append("cleanup_models")
    model_management.soft_empty_cache = lambda force=False: calls.append(("soft_empty_cache", force))
    model_management.unload_all_models = lambda: calls.append("unload_all_models")
    comfy.model_management = model_management

    torch = types.ModuleType("torch")

    class Cuda:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def synchronize():
            calls.append("cuda_synchronize")

        @staticmethod
        def empty_cache():
            calls.append("cuda_empty_cache")

        @staticmethod
        def ipc_collect():
            calls.append("cuda_ipc_collect")

    torch.cuda = Cuda

    monkeypatch.setitem(sys.modules, "comfy", comfy)
    monkeypatch.setitem(sys.modules, "comfy.model_management", model_management)
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setattr(nodes_module.gc, "collect", lambda: calls.append("gc_collect") or 7)

    status = nodes_module.clear_memory_cache(
        unload_models=True,
        clear_cuda=True,
        collect_python=True,
    )

    assert calls == [
        "unload_all_models",
        "cleanup_models_gc",
        "cleanup_models",
        ("soft_empty_cache", True),
        "cuda_synchronize",
        "cuda_empty_cache",
        "cuda_ipc_collect",
        "gc_collect",
    ]
    assert "unloaded ComfyUI models" in status
    assert "released 7 Python objects" in status


def test_server_resolves_empty_and_relative_paths_from_comfy_root():
    import jhnodes.server as server

    comfy_root = "/tmp/ComfyUI"
    original = server._comfy_root
    server._comfy_root = lambda: comfy_root
    try:
        assert server._resolve_path("") == comfy_root
        assert server._resolve_path("input/videos") == str(Path(comfy_root) / "input" / "videos")
        assert server._resolve_path("/var/tmp") == "/var/tmp"
    finally:
        server._comfy_root = original
