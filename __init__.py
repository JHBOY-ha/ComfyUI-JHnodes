from .jhnodes import server as _server  # noqa: F401
from .jhnodes.nodes import ClearMemoryCache, ClearMemoryCacheNow, FolderCount, LoadFolderItem

WEB_DIRECTORY = "./web"

NODE_CLASS_MAPPINGS = {
    "JHnodes_ClearMemoryCache": ClearMemoryCache,
    "JHnodes_ClearMemoryCacheNow": ClearMemoryCacheNow,
    "JHnodes_FolderCount": FolderCount,
    "JHnodes_LoadFolderItem": LoadFolderItem,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "JHnodes_ClearMemoryCache": "Clear Memory Cache",
    "JHnodes_ClearMemoryCacheNow": "Clear Memory Cache Now",
    "JHnodes_FolderCount": "Folder Count",
    "JHnodes_LoadFolderItem": "Load Folder Item",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
