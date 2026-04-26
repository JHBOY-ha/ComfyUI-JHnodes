import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_aiohttp_stub():
    if "aiohttp" in sys.modules:
        return

    aiohttp = types.ModuleType("aiohttp")
    web = types.SimpleNamespace(json_response=lambda data: data)
    aiohttp.web = web
    sys.modules["aiohttp"] = aiohttp
    sys.modules["aiohttp.web"] = web


def _install_torch_stub():
    if "torch" in sys.modules:
        return

    torch = types.ModuleType("torch")
    torch.Tensor = object
    torch.float32 = "float32"
    torch.equal = lambda left, right: left == right
    torch.from_numpy = lambda arr: arr
    torch.zeros = lambda *args, **kwargs: None
    sys.modules["torch"] = torch


_install_aiohttp_stub()
_install_torch_stub()
