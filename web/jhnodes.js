import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const FOLDER_NODES = new Set(["JHnodes_FolderCount", "JHnodes_LoadFolderItem"]);

function pathStem(value) {
    const unixIndex = value.lastIndexOf("/");
    const windowsIndex = value.lastIndexOf("\\");
    const index = Math.max(unixIndex, windowsIndex);
    if (index < 0) return ["", value];
    return [value.slice(0, index + 1), value.slice(index + 1)];
}

function fitPath(ctx, text, width) {
    if (ctx.measureText(text).width <= width) return text;
    let shown = text;
    while (shown.length > 1 && ctx.measureText("…" + shown).width > width) {
        shown = shown.slice(1);
    }
    return "…" + shown;
}

function openFolderPicker(widget, node, event) {
    if (widget._pickerOpen) return;
    widget._pickerOpen = true;

    const dialog = document.createElement("div");
    dialog.className = "litegraph litesearchbox graphdialog rounded";
    dialog.innerHTML =
        '<span class="name">Folder</span>' +
        '<input autofocus="" type="text" class="value" spellcheck="false">' +
        '<button class="rounded">OK</button>' +
        '<div class="helper"></div>';
    dialog.close = () => {
        dialog.remove();
        widget._pickerOpen = false;
    };
    document.body.append(dialog);

    const scale = app.canvas?.ds?.scale ?? 1;
    if (scale > 1) {
        dialog.style.transform = "scale(" + scale + ")";
    }

    const input = dialog.querySelector(".value");
    const optionsElement = dialog.querySelector(".helper");
    input.value = widget.value || "";

    let entries = [];
    let lastPath = null;
    let timeout = null;

    const commit = (value) => {
        widget.value = value.replace(/[\\/]+$/, "");
        widget.callback?.(widget.value);
        node.graph?.setDirtyCanvas(true, true);
    };

    async function fetchOptions(path) {
        try {
            const url = api.apiURL("/jhnodes/listdir?" + new URLSearchParams({ path }));
            const response = await fetch(url);
            return await response.json();
        } catch {
            return [];
        }
    }

    async function updateOptions() {
        timeout = null;
        const [path, remainder] = pathStem(input.value);
        if (lastPath !== path) {
            entries = await fetchOptions(path);
            lastPath = path;
        }

        optionsElement.innerHTML = "";
        for (const name of entries) {
            if (!name.startsWith(remainder)) continue;
            const option = document.createElement("div");
            option.innerText = name;
            option.className = "litegraph lite-search-item is-dir";
            option.addEventListener("click", () => {
                input.value = lastPath + name;
                if (timeout) clearTimeout(timeout);
                timeout = setTimeout(updateOptions, 10);
            });
            optionsElement.appendChild(option);
        }
    }

    input.addEventListener("keydown", (e) => {
        if (e.keyCode === 27) {
            dialog.close();
        } else if (e.keyCode === 13) {
            commit(input.value);
            dialog.close();
        } else {
            if (timeout) clearTimeout(timeout);
            timeout = setTimeout(updateOptions, 10);
            return;
        }
        e.preventDefault();
        e.stopPropagation();
    });

    dialog.querySelector("button").addEventListener("click", () => {
        commit(input.value);
        dialog.close();
    });

    const rect = app.canvas.canvas.getBoundingClientRect();
    let offsetX = -20;
    let offsetY = -20;
    if (rect) {
        offsetX -= rect.left;
        offsetY -= rect.top;
    }

    if (event?.clientX != null) {
        dialog.style.left = event.clientX + offsetX + "px";
        dialog.style.top = event.clientY + offsetY + "px";
    } else {
        dialog.style.left = app.canvas.canvas.width * 0.5 + offsetX + "px";
        dialog.style.top = app.canvas.canvas.height * 0.5 + offsetY + "px";
    }

    setTimeout(async () => {
        input.focus();
        input.select();
        await updateOptions();
    }, 10);

    return dialog;
}

function drawFolderWidget(ctx, node, widgetWidth, y, height) {
    const showText =
        app.canvas.ds.scale >= (app.canvas.low_quality_zoom_threshold ?? 0.5);
    const margin = 15;
    ctx.textAlign = "left";
    ctx.strokeStyle = LiteGraph.WIDGET_OUTLINE_COLOR;
    ctx.fillStyle = LiteGraph.WIDGET_BGCOLOR;
    ctx.beginPath();
    if (showText) {
        ctx.roundRect(margin, y, widgetWidth - margin * 2, height, [height * 0.5]);
    } else {
        ctx.rect(margin, y, widgetWidth - margin * 2, height);
    }
    ctx.fill();
    if (!showText) return;
    if (!this.disabled) ctx.stroke();

    ctx.save();
    ctx.beginPath();
    ctx.rect(margin, y, widgetWidth - margin * 2, height);
    ctx.clip();

    let freeWidth = widgetWidth - margin * 2 - 40;
    const label = this.label || this.name;
    ctx.fillStyle = LiteGraph.WIDGET_SECONDARY_TEXT_COLOR;
    if (label) {
        const labelWidth = ctx.measureText(label).width;
        freeWidth -= labelWidth;
        ctx.fillText(label, margin * 2, y + height * 0.7);
    }

    ctx.fillStyle = this.value ? LiteGraph.WIDGET_TEXT_COLOR : "#777";
    ctx.textAlign = "right";
    const display = String(this.value || this.options.placeholder || "");
    ctx.fillText(
        fitPath(ctx, display, freeWidth),
        widgetWidth - margin * 2,
        y + height * 0.7
    );
    ctx.restore();
}

function replaceFolderWidget(node) {
    if (!node.widgets) return;
    const index = node.widgets.findIndex((widget) => widget.name === "folder");
    if (index < 0) return;

    const old = node.widgets[index];
    if (old.type !== "text") return;

    node.widgets[index] = {
        name: old.name,
        type: "JHNODES.FOLDER",
        value: old.value || "",
        callback: old.callback,
        options: {
            ...old.options,
            placeholder: old.options?.placeholder || "X://path/to/folder",
        },
        draw: drawFolderWidget,
        mouse(event, pos, nodeRef) {
            if (event.type === "pointerdown") {
                openFolderPicker(this, nodeRef, event);
                return true;
            }
            return false;
        },
        computeSize() {
            return [0, LiteGraph.NODE_WIDGET_HEIGHT];
        },
        serializeValue() {
            return this.value;
        },
    };
}

app.registerExtension({
    name: "JHnodes.FolderPicker",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!FOLDER_NODES.has(nodeData?.name)) return;
        const original = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = original ? original.apply(this, arguments) : undefined;
            replaceFolderWidget(this);
            return result;
        };
    },
});
