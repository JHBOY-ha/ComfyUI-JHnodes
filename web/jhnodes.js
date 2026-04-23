import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const FOLDER_NODES = new Set(["JHnodes_FolderCount", "JHnodes_LoadFolderItem"]);

function pathStem(value) {
    const i = value.lastIndexOf("/");
    if (i < 0) return ["", value];
    return [value.slice(0, i + 1), value.slice(i + 1)];
}

function openFolderPicker(widget, node, event) {
    if (widget._picker_open) return;
    widget._picker_open = true;

    const dialog = document.createElement("div");
    dialog.className = "litegraph litesearchbox graphdialog rounded";
    dialog.innerHTML =
        '<span class="name">Folder</span>' +
        '<input autofocus="" type="text" class="value" spellcheck="false">' +
        '<button class="rounded">OK</button>' +
        '<div class="helper"></div>';
    document.body.append(dialog);

    const scale = app.canvas?.ds?.scale ?? 1;
    if (scale > 1) dialog.style.transform = "scale(" + scale + ")";

    const input = dialog.querySelector(".value");
    const options_element = dialog.querySelector(".helper");
    input.value = widget.value || "";

    let entries = [];
    let last_path = null;
    let timeout = null;

    const close = () => {
        dialog.remove();
        widget._picker_open = false;
    };

    const commit = (value) => {
        widget.value = value;
        if (widget.callback) widget.callback(widget.value);
        node.graph?.setDirtyCanvas(true, true);
    };

    async function fetchOptions(path) {
        try {
            const url = api.apiURL("/jhnodes/listdir?" + new URLSearchParams({ path }));
            const res = await fetch(url);
            return await res.json();
        } catch (e) {
            return [];
        }
    }

    async function updateOptions() {
        timeout = null;
        const [path, remainder] = pathStem(input.value);
        if (last_path !== path) {
            entries = await fetchOptions(path);
            last_path = path;
        }
        options_element.innerHTML = "";
        for (const name of entries) {
            if (!name.startsWith(remainder)) continue;
            const el = document.createElement("div");
            el.innerText = name;
            el.className = "litegraph lite-search-item is-dir";
            el.addEventListener("click", () => {
                input.value = last_path + name;
                if (timeout) clearTimeout(timeout);
                timeout = setTimeout(updateOptions, 10);
            });
            options_element.appendChild(el);
        }
    }

    input.addEventListener("keydown", (e) => {
        if (e.keyCode === 27) {
            close();
            e.preventDefault();
            e.stopPropagation();
        } else if (e.keyCode === 13) {
            commit(input.value.replace(/\/+$/, ""));
            close();
            e.preventDefault();
            e.stopPropagation();
        } else {
            if (timeout) clearTimeout(timeout);
            timeout = setTimeout(updateOptions, 10);
        }
    });

    dialog.querySelector("button").addEventListener("click", () => {
        commit(input.value.replace(/\/+$/, ""));
        close();
    });

    const rect = app.canvas.canvas.getBoundingClientRect();
    let x, y;
    if (event && event.clientX != null) {
        x = event.clientX - 20 - rect.left;
        y = event.clientY - 20 - rect.top;
    } else {
        x = rect.width * 0.5 - 150;
        y = rect.height * 0.5 - 50;
    }
    dialog.style.left = x + "px";
    dialog.style.top = y + "px";

    setTimeout(async () => {
        input.focus();
        input.select();
        await updateOptions();
    }, 10);
}

function drawPathWidget(ctx, node, widget_width, y, H) {
    const show_text = app.canvas.ds.scale >= (app.canvas.low_quality_zoom_threshold ?? 0.5);
    const margin = 15;
    ctx.textAlign = "left";
    ctx.strokeStyle = LiteGraph.WIDGET_OUTLINE_COLOR;
    ctx.fillStyle = LiteGraph.WIDGET_BGCOLOR;
    ctx.beginPath();
    if (show_text) ctx.roundRect(margin, y, widget_width - margin * 2, H, [H * 0.5]);
    else ctx.rect(margin, y, widget_width - margin * 2, H);
    ctx.fill();
    if (!show_text) return;
    if (!this.disabled) ctx.stroke();
    ctx.save();
    ctx.beginPath();
    ctx.rect(margin, y, widget_width - margin * 2, H);
    ctx.clip();

    ctx.fillStyle = LiteGraph.WIDGET_SECONDARY_TEXT_COLOR;
    const label = this.label || this.name;
    const labelWidth = ctx.measureText(label).width;
    ctx.fillText(label, margin * 2, y + H * 0.7);

    ctx.fillStyle = this.value ? LiteGraph.WIDGET_TEXT_COLOR : "#777";
    ctx.textAlign = "right";
    const placeholder = this.options?.placeholder || "click to pick folder";
    const display = String(this.value || placeholder);
    const maxWidth = widget_width - margin * 3 - labelWidth - 10;
    let shown = display;
    if (ctx.measureText(shown).width > maxWidth) {
        // truncate from the left so the tail (most specific dir) stays visible
        while (shown.length > 1 && ctx.measureText("…" + shown).width > maxWidth) {
            shown = shown.slice(1);
        }
        shown = "…" + shown;
    }
    ctx.fillText(shown, widget_width - margin * 2, y + H * 0.7);
    ctx.restore();
}

function replaceFolderWidget(node) {
    if (!node.widgets) return;
    const idx = node.widgets.findIndex((w) => w.name === "folder");
    if (idx < 0) return;
    const old = node.widgets[idx];
    const picker = {
        name: "folder",
        type: "JHNODES.FOLDER",
        value: old.value || "",
        options: { placeholder: old.options?.placeholder || "click to pick folder" },
        draw: drawPathWidget,
        mouse(event, pos, node) {
            if (event.type === "pointerdown") {
                openFolderPicker(this, node, event);
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
    node.widgets[idx] = picker;
}

app.registerExtension({
    name: "JHnodes.FolderPicker",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!FOLDER_NODES.has(nodeData?.name)) return;
        const orig = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = orig ? orig.apply(this, arguments) : undefined;
            replaceFolderWidget(this);
            return r;
        };
    },
});
