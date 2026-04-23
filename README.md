# ComfyUI-JHnodes

个人 ComfyUI custom nodes 集合，会持续追加节点。首批包含一个 **Folder Batch Loader**（两个节点），用来以 for-loop / 迭代器方式批处理一个文件夹下的视频/图片。

## 安装

把本仓库放到 `ComfyUI/custom_nodes/ComfyUI-JHnodes`（软链或 clone 均可），然后：

```bash
pip install -r requirements.txt
```

> `imageio-ffmpeg` 用来在有需要时抽取视频音轨；没装也能跑，但连到 `audio` 输出的下游节点会报错。

## 节点

### Folder Count — `JHnodes_FolderCount`

| 输入 | 类型 | 说明 |
| --- | --- | --- |
| `folder` | STRING | 本地文件夹绝对路径 |

| 输出 | 类型 | 说明 |
| --- | --- | --- |
| `count` | INT | 文件夹下视频+图片文件数 |
| `folder` | STRING | 规范化后的文件夹路径，可直接连到 `Load Folder Item` |

识别扩展名：

- 视频：`.mp4 .mkv .mov .webm .avi .gif .m4v`
- 图片：`.png .jpg .jpeg .bmp .webp .tif .tiff`

排序：文件名字母序（与 VHS 的 `get_sorted_dir_files_from_directory` 对齐）。

### Load Folder Item — `JHnodes_LoadFolderItem`

按 **0-based** 索引读取文件夹下排序后的第 `index` 个文件。视频走 cv2 解码（移植自 VHS `cv_frame_generator`），图片走 PIL。

| 输入 | 说明 |
| --- | --- |
| `folder`, `index` | 文件夹 + 索引 |
| `force_rate` | 目标 fps；0 保留源 fps |
| `custom_width`, `custom_height` | 目标尺寸（0 保持原尺寸，自动对齐 8） |
| `frame_load_cap` | 最多读多少帧（0 全部） |
| `skip_first_frames` | 跳过前 N 帧 |
| `select_every_nth` | 每 N 帧取 1 帧 |

| 输出 | 类型 |
| --- | --- |
| `IMAGE` | `[F, H, W, 3]` float32 0..1（单图时 F=1） |
| `frame_count` | INT |
| `audio` | AUDIO（VHS 同款 LazyAudioMap，懒加载 ffmpeg；单图返回静音占位） |
| `video_info` | VHS_VIDEOINFO dict（与 VHS 字段一致） |
| `filename` | STRING |

由于输出类型名对齐 VHS，装了 VHS 时可直接接 `VHS_VideoCombine`、`VHS_BatchManager` 等下游；未装 VHS 也不会报错。

## 典型用法

```
[FolderCount] ── folder ──┐
                          ├─→ [LoadFolderItem] ─→ [VHS VideoCombine / KSampler / ...]
            index (0..N-1)─┘
```

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
