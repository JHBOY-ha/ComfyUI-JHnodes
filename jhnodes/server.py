import os
import platform

from aiohttp import web

try:
    import server as _comfy_server
except ImportError:
    _comfy_server = None


def _list_directory(path: str) -> list[str]:
    try:
        names = sorted(os.listdir(path))
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return []

    entries = []
    for name in names:
        full = os.path.join(path, name)
        try:
            if os.path.isdir(full):
                entries.append(name + "/")
        except OSError:
            continue
    return entries


def _roots() -> list[str]:
    roots = []
    home = os.path.expanduser("~")
    if os.path.isdir(home):
        roots.append(home.rstrip(os.sep) + os.sep)

    if platform.system() == "Windows":
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = f"{letter}:{os.sep}"
            if os.path.isdir(drive):
                roots.append(drive)
    else:
        roots.append("/")
    return roots


def _comfy_root() -> str:
    if _comfy_server is not None and getattr(_comfy_server, "__file__", None):
        return os.path.dirname(os.path.abspath(_comfy_server.__file__))
    return os.getcwd()


def _resolve_path(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return _comfy_root()

    expanded = os.path.expanduser(raw)
    if os.path.isabs(expanded):
        return os.path.abspath(expanded)
    return os.path.abspath(os.path.join(_comfy_root(), expanded))


def register_routes():
    if _comfy_server is None or not hasattr(_comfy_server, "PromptServer"):
        return

    routes = _comfy_server.PromptServer.instance.routes

    @routes.get("/jhnodes/listdir")
    async def jhnodes_listdir(request):
        raw = request.rel_url.query.get("path", "")
        path = _resolve_path(raw)

        if not os.path.isdir(path):
            parent = os.path.dirname(path)
            if parent and os.path.isdir(parent):
                path = parent
            else:
                return web.json_response([])

        return web.json_response(_list_directory(path))


register_routes()
