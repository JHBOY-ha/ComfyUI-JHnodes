# ComfyUI-JHnodes

个人 ComfyUI custom nodes 集合，会持续追加节点。首批包含一个 **Folder Batch Loader**（两个节点），用来以 for-loop / 迭代器方式批处理一个文件夹下的视频/图片。

## 安装

把本仓库放到 `ComfyUI/custom_nodes/ComfyUI-JHnodes`（软链或 clone 均可），然后：

```bash
pip install -r requirements.txt
```

## 节点

### Clear Memory Cache — `JHnodes_ClearMemoryCache`

用于放在 EasyUse loop 或其他长流程中间，执行到该节点时清理 Python / PyTorch / ComfyUI 缓存，并把输入原样透传到输出。

| 输入              | 类型    | 说明                                                                 |
| ----------------- | ------- | -------------------------------------------------------------------- |
| `anything`        | `*`     | 任意类型连接输入；节点会原样输出，用来控制清理发生在这条执行链上     |
| `unload_models`   | BOOLEAN | 是否调用 ComfyUI `unload_all_models`；更彻底，但下一轮可能需要重载模型 |
| `clear_cuda`      | BOOLEAN | 清理 torch CUDA/MPS/XPU 等加速器缓存；默认开启                       |
| `collect_python`  | BOOLEAN | 执行 `gc.collect()`；默认开启                                         |

| 输出     | 类型   | 说明                         |
| -------- | ------ | ---------------------------- |
| `output` | `*`    | 原样透传的输入               |
| `status` | STRING | 本次尝试执行过的清理动作摘要 |

建议接法：

```text
上游必须执行的输出 -> Clear Memory Cache.anything
Clear Memory Cache.output -> For Loop End.flow 或 For Loop End.valueX
```

如果要清理每一次循环产生的视频/图片张量，节点必须放在该轮重负载节点之后、`For Loop End` 之前，并且 `output` 要继续接到会被执行的下游。只把节点孤立放在画布上不会触发执行。

注意：这个节点可以释放 PyTorch/ComfyUI 已经不再引用的缓存，但不能释放仍被 loop 的 `valueX`、预览节点、保存节点、视频合成节点或其他下游对象持有的张量。如果某个下游节点把所有循环结果累积起来，显存仍可能增长。

### Clear Memory Cache Now — `JHnodes_ClearMemoryCacheNow`

无透传输入版，作为输出节点运行。用于确认节点是否能在菜单中出现，或手动插一个“只清理不透传”的终点。

| 输入             | 类型    | 说明                                                                  |
| ---------------- | ------- | --------------------------------------------------------------------- |
| `unload_models`  | BOOLEAN | 是否调用 ComfyUI `unload_all_models`；更彻底，但下一轮可能需要重载模型 |
| `clear_cuda`     | BOOLEAN | 清理 torch CUDA/MPS/XPU 等加速器缓存；默认开启                        |
| `collect_python` | BOOLEAN | 执行 `gc.collect()`；默认开启                                          |

| 输出     | 类型   | 说明                         |
| -------- | ------ | ---------------------------- |
| `status` | STRING | 本次尝试执行过的清理动作摘要 |

### Folder Count — `JHnodes_FolderCount`

| 输入            | 类型   | 说明                                                 |
| --------------- | ------ | ---------------------------------------------------- |
| `folder`      | STRING | 本地文件夹绝对路径                                   |
| `start_index` | INT    | 从排序后的第几个匹配文件开始统计；`0` 表示从头开始 |
| `limit`       | INT    | 最多统计多少个匹配文件；`0` 表示不限制             |

| 输出            | 类型   | 说明                                                  |
| --------------- | ------ | ----------------------------------------------------- |
| `count`       | INT    | 文件夹下视频+图片文件数                               |
| `folder`      | STRING | 规范化后的文件夹路径，可直接连到 `Load Folder Item` |
| `start_index` | INT    | 原样输出，可直接连到 `Load Folder Item.start_index` |
| `limit`       | INT    | 原样输出，可直接连到 `Load Folder Item.limit`       |

识别扩展名：

- 视频：`.mp4 .mkv .mov .webm .avi .gif .m4v`
- 图片：`.png .jpg .jpeg .bmp .webp .tif .tiff`

排序：文件名字母序。

### Load Folder Item — `JHnodes_LoadFolderItem`

按 **0-based** 索引读取文件夹下排序后的第 `start_index + index` 个文件。视频走 cv2 解码，图片走 PIL。

| 输入                                | 说明                                                                      |
| ----------------------------------- | ------------------------------------------------------------------------- |
| `folder`, `index`               | 文件夹 + 索引                                                             |
| `force_rate`                      | 目标 fps；0 保留源 fps                                                    |
| `custom_width`, `custom_height` | 目标尺寸（0 保持原尺寸，自动对齐 8）                                      |
| `frame_load_cap`                  | 最多读多少帧（0 全部）                                                    |
| `skip_first_frames`               | 跳过前 N 帧                                                               |
| `select_every_nth`                | 每 N 帧取 1 帧                                                            |
| `start_index`（连接输入）         | 从排序后的第几个匹配文件开始读取；用于连接 `Folder Count.start_index`   |
| `limit`（连接输入）               | 允许读取多少个匹配文件；用于连接 `Folder Count.limit`，`0` 表示不限制 |

| 输出            | 类型                                        |
| --------------- | ------------------------------------------- |
| `IMAGE`       | `[F, H, W, 3]` float32 0..1（单图时 F=1） |
| `frame_count` | INT                                         |
| `audio`       | AUDIO                                       |
| `video_info`  | VHS_VIDEOINFO dict（与 VHS 字段一致）       |
| `filename`    | STRING                                      |

由于输出类型名对齐 VHS，装了 VHS 时可直接接 `VHS_VideoCombine`、`VHS_BatchManager` 等下游；未装 VHS 也不会报错。

## 典型用法

与 EasyUse `For Loop` 一起使用

如果你用的是 `ComfyUI-Easy-Use` 的 `For Loop Start / End` 来遍历文件夹，推荐接法是：

```text
FolderCount.count  -> For Loop Start.total
FolderCount.folder -> Load Folder Item.folder
FolderCount.start_index -> Load Folder Item.start_index
FolderCount.limit -> Load Folder Item.limit
For Loop Start.index -> Load Folder Item.index
For Loop Start.flow -> For Loop End.flow

Load Folder Item.filename -> For Loop End.initial_value1
For Loop End.value1 -> Preview Any / Preview as Text / 其他会真正执行的下游节点
```

注意：

- `For Loop End` 的至少一个 `valueX` 输出必须被下游节点实际消费，否则 `EasyUse` 的循环递归不会真正触发，看起来就像只执行了一次。
- 只连接 `flow` 不够；`flow` 只是控制信号，不会单独强制 `For Loop End` 执行。

## 布局

```
ComfyUI-JHnodes/
├── __init__.py                 # NODE_CLASS_MAPPINGS
├── pyproject.toml
├── requirements.txt
├── README.md
└── jhnodes/
    ├── nodes.py                # FolderCount + LoadFolderItem
    ├── video_reader.py         # cv2 解码 + 单图加载
    ├── ffmpeg.py               # ffmpeg_path + get_audio + LazyAudioMap
    └── utils.py                # 扩展名常量 + 目录枚举
```

## License

This project is licensed under the GNU General Public License v3.0 only.
