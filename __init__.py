from .jhnodes.nodes import FolderCount, LoadFolderItem

NODE_CLASS_MAPPINGS = {
    "JHnodes_FolderCount": FolderCount,
    "JHnodes_LoadFolderItem": LoadFolderItem,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "JHnodes_FolderCount": "Folder Count",
    "JHnodes_LoadFolderItem": "Load Folder Item",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
