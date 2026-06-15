from typing import Sequence
import marimo as mo
import anywidget
import traitlets


_ESM = """
function render({ model, el }) {
  el.classList.add("sortable-textarea-widget");

  let draggedItem = null;
  let draggedIndex = null;
  let dropTarget = null;
  let dropPosition = null;

  // Prevents change:value from triggering a full re-render while the user
  // is actively typing - we update the model but own the DOM ourselves.
  let suppressValueRerender = false;

  function setModelValue(items) {
    suppressValueRerender = true;
    model.set("value", items);
    model.save_changes();
    suppressValueRerender = false;
  }

  function autoResize(textarea) {
    if (!model.get("autosize")) return;
    textarea.style.height = "auto";
    textarea.style.height = textarea.scrollHeight + "px";
  }

  function buildRow(item, index) {
    let movable = model.get("movable");
    let editable = model.get("editable");

    let row = document.createElement("div");
    row.className = "st-row";
    row.draggable = movable;
    row.dataset.index = index;

    let header = document.createElement("div");
    header.className = "st-header";

    let dragHandle = document.createElement("button");
    dragHandle.className = "drag-handle" + (movable ? "" : " hidden");
    dragHandle.innerHTML = `
      <svg width="10" height="10" viewBox="0 0 16 16">
        <circle cx="4" cy="4" r="1"/>
        <circle cx="12" cy="4" r="1"/>
        <circle cx="4" cy="8" r="1"/>
        <circle cx="12" cy="8" r="1"/>
        <circle cx="4" cy="12" r="1"/>
        <circle cx="12" cy="12" r="1"/>
      </svg>
    `;
    dragHandle.setAttribute("aria-label", `Reorder item ${index + 1}`);

    let keyField = document.createElement("input");
    keyField.type = "text";
    keyField.className = "st-key" + (editable ? "" : " readonly");
    keyField.value = item.key ?? "";
    keyField.placeholder = model.get("key_placeholder");
    keyField.readOnly = !editable;
    keyField.draggable = false;
    keyField.addEventListener("mousedown", e => e.stopPropagation());
    keyField.addEventListener("dragstart", e => e.preventDefault());
    keyField.addEventListener("keydown", e => e.stopPropagation());
    keyField.addEventListener("input", () => {
      let items = model.get("value").map(o => ({ ...o }));
      items[index] = { ...items[index], key: keyField.value };
      setModelValue(items);
    });

    header.appendChild(dragHandle);
    header.appendChild(keyField);

    if (model.get("removable")) {
      let removeButton = document.createElement("button");
      removeButton.className = "remove-button";
      removeButton.innerHTML = `
        <svg width="10" height="10" viewBox="0 0 14 14" fill="none">
          <path d="M4 4l6 6m0-6l-6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      `;
      removeButton.setAttribute("aria-label", `Remove item ${index + 1}`);
      removeButton.addEventListener("click", e => {
        e.stopPropagation();
        removeItem(index);
      });
      header.appendChild(removeButton);
    }

    let valueField = document.createElement("textarea");
    valueField.className = "st-value" + (editable ? "" : " readonly");
    valueField.value = item.value ?? "";
    valueField.placeholder = model.get("value_placeholder");
    valueField.readOnly = !editable;
    valueField.rows = model.get("rows");
    valueField.draggable = false;
    valueField.addEventListener("mousedown", e => e.stopPropagation());
    valueField.addEventListener("dragstart", e => e.preventDefault());
    valueField.addEventListener("keydown", e => e.stopPropagation());
    valueField.addEventListener("input", () => {
      let items = model.get("value").map(o => ({ ...o }));
      items[index] = { ...items[index], value: valueField.value };
      setModelValue(items);
      autoResize(valueField);
    });

    row.appendChild(header);
    row.appendChild(valueField);

    if (movable) {
      row.addEventListener("dragstart", e => {
        draggedItem = row;
        draggedIndex = index;
        row.classList.add("dragging");
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/html", row.outerHTML);
      });

      row.addEventListener("dragend", () => {
        row.classList.remove("dragging");
        draggedItem = null;
        draggedIndex = null;
        clearDropIndicators();
      });

      row.addEventListener("dragover", e => {
        if (draggedItem && draggedItem !== row) {
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
          let rect = row.getBoundingClientRect();
          let newDropPosition = e.clientY < rect.top + rect.height / 2 ? "top" : "bottom";
          if (dropTarget !== row || dropPosition !== newDropPosition) {
            clearDropIndicators();
            dropTarget = row;
            dropPosition = newDropPosition;
            showDropIndicator(row, newDropPosition);
          }
        }
      });

      row.addEventListener("dragleave", e => {
        if (!row.contains(e.relatedTarget)) {
          clearDropIndicators();
        }
      });

      row.addEventListener("drop", e => {
        e.preventDefault();
        if (draggedItem && draggedItem !== row) {
          let targetIndex = parseInt(row.dataset.index);
          let newIndex = dropPosition === "bottom" ? targetIndex + 1 : targetIndex;
          if (draggedIndex < newIndex) newIndex--;
          reorderItems(draggedIndex, newIndex);
        }
        clearDropIndicators();
      });
    }

    return row;
  }

  function renderList() {
    el.replaceChildren();

    let label = model.get("label");
    if (label) {
      let heading = document.createElement("div");
      heading.className = "st-label";
      heading.textContent = label;
      el.appendChild(heading);
    }

    let container = document.createElement("div");
    container.className = "st-container";
    model.get("value").forEach((item, index) => {
      container.appendChild(buildRow(item, index));
    });
    el.appendChild(container);

    if (model.get("autosize")) {
      el.querySelectorAll(".st-value").forEach(t => autoResize(t));
    }

    if (model.get("addable")) {
      let addButton = document.createElement("button");
      addButton.className = "add-button";
      addButton.textContent = "+ Add item";
      addButton.addEventListener("click", () => addItem());
      el.appendChild(addButton);
    }
  }

  function addItem() {
    model.set("value", [...model.get("value"), { key: "", value: "" }]);
    model.save_changes();
  }

  function removeItem(index) {
    model.set("value", model.get("value").toSpliced(index, 1));
    model.save_changes();
  }

  function showDropIndicator(element, position) {
    let indicator = document.createElement("div");
    indicator.className = "drop-indicator";
    indicator.style.cssText = "position:absolute;left:0;right:0;height:2px;background:#0066cc;z-index:1000;" +
      (position === "top" ? "top:-1px" : "bottom:-1px");
    element.style.position = "relative";
    element.appendChild(indicator);
  }

  function clearDropIndicators() {
    el.querySelectorAll(".drop-indicator").forEach(i => i.remove());
    dropTarget = null;
    dropPosition = null;
  }

  function reorderItems(fromIndex, toIndex) {
    let items = [...model.get("value")];
    let [moved] = items.splice(fromIndex, 1);
    items.splice(toIndex, 0, moved);
    model.set("value", items);
    model.save_changes();
  }

  renderList();
  model.on("change:value", () => { if (!suppressValueRerender) renderList(); });
  model.on("change:label", renderList);
  model.on("change:addable", renderList);
  model.on("change:removable", renderList);
  model.on("change:editable", renderList);
  model.on("change:movable", renderList);
  model.on("change:rows", renderList);
  model.on("change:autosize", renderList);
}

export default { render };
"""

_CSS = """
.sortable-textarea-widget {
  font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  max-width: 100%;
  color-scheme: light dark;

  /* CSS variables for theming (overridden in dark mode below) */
  --stw-bg-container: #ffffff;
  --stw-bg-item: #ffffff;
  --stw-bg-hover: #f8f9fa;
  --stw-bg-focus: #ffffff;
  --stw-bg-button-hover: #e4e6ea;
  --stw-bg-add-hover: #f4f5f7;
  --stw-border-color: #e1e5e9;
  --stw-border-dashed: #c1c7d0;
  --stw-text-primary: #172b4d;
  --stw-text-secondary: #6b778c;
  --stw-text-button-hover: #42526e;
  --stw-accent: #0052cc;
  --stw-shadow: rgba(0, 0, 0, 0.1);
}
.sortable-textarea-widget .st-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--stw-text-primary);
  margin-bottom: 6px;
}
.sortable-textarea-widget .st-container {
  background: var(--stw-bg-container);
  border: 1px solid var(--stw-border-color);
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 1px 3px var(--stw-shadow);
}
.sortable-textarea-widget .st-row {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 10px;
  background: var(--stw-bg-item);
  border-bottom: 1px solid var(--stw-border-color);
  transition: background-color 0.15s ease, opacity 0.15s ease;
  cursor: default;
}
.sortable-textarea-widget .st-row[draggable="true"] {
  cursor: grab;
}
.sortable-textarea-widget .st-row:last-child {
  border-bottom: none;
}
.sortable-textarea-widget .st-row:hover {
  background-color: var(--stw-bg-hover);
}
.sortable-textarea-widget .st-row:hover .remove-button {
  opacity: 1;
}
.sortable-textarea-widget .st-row.dragging {
  opacity: 0.5;
  cursor: grabbing;
}
.sortable-textarea-widget .st-header {
  display: flex;
  align-items: center;
  gap: 6px;
}
.sortable-textarea-widget .drag-handle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: none;
  background: transparent;
  cursor: grab;
  color: var(--stw-text-secondary);
  flex-shrink: 0;
}
.sortable-textarea-widget .drag-handle.hidden {
  visibility: hidden;
  pointer-events: none;
}
.sortable-textarea-widget .drag-handle:active {
  cursor: grabbing;
}
.sortable-textarea-widget .drag-handle svg {
  fill: currentColor;
}
.sortable-textarea-widget .st-key {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  font-family: inherit;
  color: var(--stw-text-primary);
  border: 1px solid transparent;
  border-radius: 3px;
  padding: 2px 6px;
  background: transparent;
  outline: none;
  min-width: 0;
  cursor: text;
}
.sortable-textarea-widget .st-key:focus {
  border-color: var(--stw-accent);
  background: var(--stw-bg-focus);
}
.sortable-textarea-widget .st-key::placeholder {
  color: var(--stw-text-secondary);
  font-weight: 400;
}
.sortable-textarea-widget .st-key.readonly {
  cursor: default;
  color: var(--stw-text-primary);
}
.sortable-textarea-widget .st-value {
  width: 100%;
  box-sizing: border-box;
  font-size: 14px;
  line-height: 1.5;
  font-family: inherit;
  color: var(--stw-text-primary);
  border: 1px solid var(--stw-border-color);
  border-radius: 4px;
  padding: 6px 8px;
  background: var(--stw-bg-focus);
  outline: none;
  resize: vertical;
  cursor: text;
}
.sortable-textarea-widget .st-value:focus {
  border-color: var(--stw-accent);
}
.sortable-textarea-widget .st-value::placeholder {
  color: var(--stw-text-secondary);
}
.sortable-textarea-widget .st-value.readonly {
  cursor: default;
  background: transparent;
  resize: none;
}
.sortable-textarea-widget .remove-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 3px;
  color: var(--stw-text-secondary);
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s ease, background-color 0.15s ease;
}
.sortable-textarea-widget .remove-button:hover {
  background-color: var(--stw-bg-button-hover);
  color: var(--stw-text-button-hover);
}
.sortable-textarea-widget .add-button {
  margin-top: 8px;
  padding: 5px 10px;
  font-size: 13px;
  font-family: inherit;
  color: var(--stw-accent);
  background: transparent;
  border: 1px dashed var(--stw-border-dashed);
  border-radius: 4px;
  cursor: pointer;
  width: 100%;
  text-align: left;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}
.sortable-textarea-widget .add-button:hover {
  background-color: var(--stw-bg-add-hover);
  border-color: var(--stw-accent);
}
.sortable-textarea-widget .drop-indicator {
  background-color: var(--stw-accent) !important;
  border-radius: 1px;
}

/* Dark mode: marimo toggles `.dark` (and some hosts `.dark-theme`) on an ancestor */
.dark .sortable-textarea-widget,
.dark-theme .sortable-textarea-widget {
  --stw-bg-container: #1e1e1e;
  --stw-bg-item: #2a2a2a;
  --stw-bg-hover: #333333;
  --stw-bg-focus: #333333;
  --stw-bg-button-hover: #3a3a3a;
  --stw-bg-add-hover: #333333;
  --stw-border-color: #3a3a3a;
  --stw-border-dashed: #4a4a4a;
  --stw-text-primary: #e0e0e0;
  --stw-text-secondary: #a0a0a0;
  --stw-text-button-hover: #f0f0f0;
  --stw-accent: #4d9fff;
  --stw-shadow: rgba(0, 0, 0, 0.3);
}
"""


class SortableTextarea(anywidget.AnyWidget):
    """Interactive sortable list of labelled text areas.

    Each item is a dict with ``key`` and ``value`` string fields. The key is
    shown as a header input and the value is edited in a multi-line textarea
    below it. Items drag as a single unit via the grip handle on the left.

    The value model is identical to ``SortableKV`` - a list of
    ``{"key": str, "value": str}`` dicts - so the two widgets are
    interchangeable from the consumer's point of view; only the UI differs.

    Args:
        value: Initial list of ``{"key": str, "value": str}`` dicts.
        addable: Allow inserting new items (default: False).
        removable: Allow deleting items (default: False).
        editable: Allow inline editing of key/value fields (default: True).
        movable: Allow reordering items by drag-and-drop (default: True).
        label: Optional heading shown above the list.
        key_placeholder: Placeholder text for the key field.
        value_placeholder: Placeholder text for the textarea.
        rows: Initial visible row count of each textarea (default: 3).
        autosize: Grow each textarea to fit its content (default: True).
        **kwargs: Forwarded to ``anywidget.AnyWidget``.
    """

    _esm = traitlets.Unicode(_ESM).tag(sync=True)
    _css = traitlets.Unicode(_CSS).tag(sync=True)

    value = traitlets.List(traitlets.Dict()).tag(sync=True)
    addable = traitlets.Bool(default_value=False).tag(sync=True)
    removable = traitlets.Bool(default_value=False).tag(sync=True)
    editable = traitlets.Bool(default_value=True).tag(sync=True)
    movable = traitlets.Bool(default_value=True).tag(sync=True)
    label = traitlets.Unicode("").tag(sync=True)
    key_placeholder = traitlets.Unicode("key").tag(sync=True)
    value_placeholder = traitlets.Unicode("value").tag(sync=True)
    rows = traitlets.Int(default_value=3).tag(sync=True)
    autosize = traitlets.Bool(default_value=True).tag(sync=True)

    def __init__(
        self,
        value: Sequence[dict],
        *,
        addable: bool = False,
        removable: bool = False,
        editable: bool = True,
        movable: bool = True,
        label: str = "",
        key_placeholder: str = "key",
        value_placeholder: str = "value",
        rows: int = 5,
        autosize: bool = True,
        **kwargs,
    ) -> None:
        items = [
            {"key": str(r), "value": ""}
            if isinstance(r, str)
            else {"key": str(r.get("key", "")), "value": str(r.get("value", ""))}
            for r in value
        ]
        super().__init__(
            value=items,
            addable=addable,
            removable=removable,
            editable=editable,
            movable=movable,
            label=label,
            key_placeholder=key_placeholder,
            value_placeholder=value_placeholder,
            rows=rows,
            autosize=autosize,
            **kwargs,
        )


def records_to_dict(records: Sequence[dict]) -> dict:
    """Collapse a list of ``{"key", "value"}`` records into a ``{key: value}`` dict.

    Later records win if two share the same key.
    """
    return {r.get("key", ""): r.get("value", "") for r in records}


class _SortableTextareaElement(mo.ui.anywidget):
    """``mo.ui.anywidget`` wrapper whose ``.value`` exposes only the records.

    Plain ``mo.ui.anywidget`` returns the widget's *entire* trait state from
    ``.value`` (``value``, ``addable``, ``removable``, ...). This subclass
    narrows ``.value`` to just the ``value`` section - the list of
    ``{"key", "value"}`` records - so ``.value`` reflects the data only.

    When ``as_dict`` is True, ``.value`` is collapsed to a ``{key: value}``
    dict via :func:`records_to_dict`, so ``.value.values()`` yields only the
    value strings and ``.value.keys()`` only the keys.
    """

    def __init__(self, widget, *, as_dict: bool = False):
        # Set before super().__init__ flips _initialized to True so the
        # forwarding __setattr__ keeps it on the element, not the widget.
        self._as_dict = as_dict
        super().__init__(widget)

    @property
    def value(self):
        records = super().value.get("value", [])
        return records_to_dict(records) if self._as_dict else records

    @value.setter
    def value(self, value):
        del value
        raise RuntimeError("Setting the value of a UIElement is not allowed.")


def sortable_textarea(
    value: Sequence[dict],
    *,
    addable: bool = False,
    removable: bool = False,
    editable: bool = True,
    movable: bool = True,
    label: str = "",
    key_placeholder: str = "key",
    value_placeholder: str = "value",
    rows: int = 5,
    autosize: bool = True,
    as_dict: bool = True,
    **kwargs,
) -> mo.ui.anywidget:
    """Build a sortable list of labelled text areas as a marimo UI element.

    Args:
        as_dict: When False``.value`` returns the records list,
            ``[{"key": str, "value": str}, ...]`` (i.e. "as they are now").
            When True ``.value`` returns a ``{key: value}`` dict, so
            ``.value.values()`` gives only the value strings.

    See :class:`SortableTextarea` for the remaining arguments.
    """
    return _SortableTextareaElement(
        SortableTextarea(
            value,
            addable=addable,
            removable=removable,
            editable=editable,
            movable=movable,
            label=label,
            key_placeholder=key_placeholder,
            value_placeholder=value_placeholder,
            rows=rows,
            autosize=autosize,
            **kwargs,
        ),
        as_dict=as_dict,
    )
