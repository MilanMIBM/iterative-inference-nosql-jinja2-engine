from typing import Sequence
import marimo as mo
import anywidget
import traitlets


_ESM = """
function render({ model, el }) {
  el.classList.add("sortable-kv-widget");

  let draggedItem = null;
  let draggedIndex = null;
  let dropTarget = null;
  let dropPosition = null;

  function renderList() {
    el.replaceChildren();

    let label = model.get("label");
    if (label) {
      let heading = document.createElement("div");
      heading.className = "kv-label";
      heading.textContent = label;
      el.appendChild(heading);
    }

    let container = document.createElement("div");
    container.className = "kv-container";

    model.get("value").forEach((item, index) => {
      let row = document.createElement("div");
      row.className = "kv-row";
      row.draggable = true;
      row.dataset.index = index;

      let movable = model.get("movable");
      row.draggable = movable;

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
      dragHandle.setAttribute("aria-label", `Reorder row ${index + 1}`);

      let keyField = document.createElement("input");
      keyField.type = "text";
      keyField.className = "kv-key" + (model.get("editable") ? "" : " readonly");
      keyField.value = item.key ?? "";
      keyField.placeholder = model.get("key_placeholder");
      keyField.readOnly = !model.get("editable");
      keyField.addEventListener("mousedown", e => e.stopPropagation());
      keyField.addEventListener("change", () => {
        let items = model.get("value").map(o => ({ ...o }));
        items[index] = { ...items[index], key: keyField.value };
        model.set("value", items);
        model.save_changes();
      });
      keyField.addEventListener("keydown", e => e.stopPropagation());

      let separator = document.createElement("span");
      separator.className = "kv-separator";
      separator.textContent = ":";

      let valueField = document.createElement("input");
      valueField.type = "text";
      valueField.className = "kv-value" + (model.get("editable") ? "" : " readonly");
      valueField.value = item.value ?? "";
      valueField.placeholder = model.get("value_placeholder");
      valueField.readOnly = !model.get("editable");
      valueField.addEventListener("mousedown", e => e.stopPropagation());
      valueField.addEventListener("change", () => {
        let items = model.get("value").map(o => ({ ...o }));
        items[index] = { ...items[index], value: valueField.value };
        model.set("value", items);
        model.save_changes();
      });
      valueField.addEventListener("keydown", e => e.stopPropagation());

      row.appendChild(dragHandle);
      row.appendChild(keyField);
      row.appendChild(separator);
      row.appendChild(valueField);

      if (model.get("removable")) {
        let removeButton = document.createElement("button");
        removeButton.className = "remove-button";
        removeButton.innerHTML = `
          <svg width="10" height="10" viewBox="0 0 14 14" fill="none">
            <path d="M4 4l6 6m0-6l-6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        `;
        removeButton.setAttribute("aria-label", `Remove row ${index + 1}`);
        removeButton.addEventListener("click", e => {
          e.stopPropagation();
          removeItem(index);
        });
        row.appendChild(removeButton);
      }

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

      container.appendChild(row);
    });

    el.appendChild(container);

    if (model.get("addable")) {
      let addButton = document.createElement("button");
      addButton.className = "add-button";
      addButton.textContent = "+ Add row";
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
  model.on("change:value", renderList);
  model.on("change:label", renderList);
  model.on("change:addable", renderList);
  model.on("change:removable", renderList);
  model.on("change:editable", renderList);
  model.on("change:movable", renderList);
}

export default { render };
"""

_CSS = """
.sortable-kv-widget {
  font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  max-width: 100%;
  color-scheme: light dark;

  /* CSS variables for theming (overridden in dark mode below) */
  --skv-bg-container: #ffffff;
  --skv-bg-item: #ffffff;
  --skv-bg-hover: #f8f9fa;
  --skv-bg-focus: #ffffff;
  --skv-bg-button-hover: #e4e6ea;
  --skv-bg-add-hover: #f4f5f7;
  --skv-border-color: #e1e5e9;
  --skv-border-dashed: #c1c7d0;
  --skv-text-primary: #172b4d;
  --skv-text-secondary: #6b778c;
  --skv-text-button-hover: #42526e;
  --skv-accent: #0052cc;
  --skv-shadow: rgba(0, 0, 0, 0.1);
}
.sortable-kv-widget .kv-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--skv-text-primary);
  margin-bottom: 6px;
}
.sortable-kv-widget .kv-container {
  background: var(--skv-bg-container);
  border: 1px solid var(--skv-border-color);
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 1px 3px var(--skv-shadow);
}
.sortable-kv-widget .kv-row {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: var(--skv-bg-item);
  border-bottom: 1px solid var(--skv-border-color);
  transition: background-color 0.15s ease, opacity 0.15s ease;
  cursor: grab;
}
.sortable-kv-widget .kv-row:last-child {
  border-bottom: none;
}
.sortable-kv-widget .kv-row:hover {
  background-color: var(--skv-bg-hover);
}
.sortable-kv-widget .kv-row:hover .remove-button {
  opacity: 1;
}
.sortable-kv-widget .kv-row.dragging {
  opacity: 0.5;
  cursor: grabbing;
}
.sortable-kv-widget .drag-handle.hidden {
  visibility: hidden;
  pointer-events: none;
}
.sortable-kv-widget .drag-handle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: none;
  background: transparent;
  cursor: grab;
  color: var(--skv-text-secondary);
  flex-shrink: 0;
}
.sortable-kv-widget .drag-handle:active {
  cursor: grabbing;
}
.sortable-kv-widget .drag-handle svg {
  fill: currentColor;
}
.sortable-kv-widget .kv-key,
.sortable-kv-widget .kv-value {
  flex: 1;
  font-size: 14px;
  font-family: inherit;
  color: var(--skv-text-primary);
  border: 1px solid transparent;
  border-radius: 3px;
  padding: 2px 6px;
  background: transparent;
  outline: none;
  min-width: 0;
  cursor: text;
}
.sortable-kv-widget .kv-key:focus,
.sortable-kv-widget .kv-value:focus {
  border-color: var(--skv-accent);
  background: var(--skv-bg-focus);
}
.sortable-kv-widget .kv-key::placeholder,
.sortable-kv-widget .kv-value::placeholder {
  color: var(--skv-text-secondary);
}
.sortable-kv-widget .kv-key.readonly,
.sortable-kv-widget .kv-value.readonly {
  cursor: default;
  color: var(--skv-text-primary);
}
.sortable-kv-widget .kv-separator {
  color: var(--skv-text-secondary);
  font-size: 14px;
  flex-shrink: 0;
  user-select: none;
}
.sortable-kv-widget .remove-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 3px;
  color: var(--skv-text-secondary);
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s ease, background-color 0.15s ease;
}
.sortable-kv-widget .remove-button:hover {
  background-color: var(--skv-bg-button-hover);
  color: var(--skv-text-button-hover);
}
.sortable-kv-widget .add-button {
  margin-top: 8px;
  padding: 5px 10px;
  font-size: 13px;
  font-family: inherit;
  color: var(--skv-accent);
  background: transparent;
  border: 1px dashed var(--skv-border-dashed);
  border-radius: 4px;
  cursor: pointer;
  width: 100%;
  text-align: left;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}
.sortable-kv-widget .add-button:hover {
  background-color: var(--skv-bg-add-hover);
  border-color: var(--skv-accent);
}
.sortable-kv-widget .drop-indicator {
  background-color: var(--skv-accent) !important;
  border-radius: 1px;
}

/* Dark mode: marimo toggles `.dark` (and some hosts `.dark-theme`) on an ancestor */
.dark .sortable-kv-widget,
.dark-theme .sortable-kv-widget {
  --skv-bg-container: #1e1e1e;
  --skv-bg-item: #2a2a2a;
  --skv-bg-hover: #333333;
  --skv-bg-focus: #333333;
  --skv-bg-button-hover: #3a3a3a;
  --skv-bg-add-hover: #333333;
  --skv-border-color: #3a3a3a;
  --skv-border-dashed: #4a4a4a;
  --skv-text-primary: #e0e0e0;
  --skv-text-secondary: #a0a0a0;
  --skv-text-button-hover: #f0f0f0;
  --skv-accent: #4d9fff;
  --skv-shadow: rgba(0, 0, 0, 0.3);
}
"""


class SortableKV(anywidget.AnyWidget):
    """Interactive sortable key/value list widget.

    Each row is a dict with ``key`` and ``value`` string fields. Rows drag
    as a single unit via the grip handle on the left.

    Args:
        value: Initial list of ``{"key": str, "value": str}`` dicts.
        addable: Allow inserting new rows (default: False).
        removable: Allow deleting rows (default: False).
        editable: Allow inline editing of key/value fields (default: True).
        movable: Allow reordering rows by drag-and-drop (default: True).
        label: Optional heading shown above the list.
        key_placeholder: Placeholder text for the key field.
        value_placeholder: Placeholder text for the value field.
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
        **kwargs,
    ) -> None:
        rows = [
            {"key": str(r), "value": ""}
            if isinstance(r, str)
            else {"key": str(r.get("key", "")), "value": str(r.get("value", ""))}
            for r in value
        ]
        super().__init__(
            value=rows,
            addable=addable,
            removable=removable,
            editable=editable,
            movable=movable,
            label=label,
            key_placeholder=key_placeholder,
            value_placeholder=value_placeholder,
            **kwargs,
        )


def records_to_dict(records: Sequence[dict]) -> dict:
    """Collapse a list of ``{"key", "value"}`` records into a ``{key: value}`` dict.

    Later records win if two share the same key.
    """
    return {r.get("key", ""): r.get("value", "") for r in records}


class _SortableKVElement(mo.ui.anywidget):
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


def sortable_kv(
    value: Sequence[dict],
    *,
    addable: bool = False,
    removable: bool = False,
    editable: bool = True,
    movable: bool = True,
    label: str = "",
    key_placeholder: str = "key",
    value_placeholder: str = "value",
    as_dict: bool = True,
    **kwargs,
) -> mo.ui.anywidget:
    """Build a sortable key/value list as a marimo UI element.

    Args:
        as_dict: When False ``.value`` returns the records list,
            ``[{"key": str, "value": str}, ...]``. When True ``.value``
            returns a ``{key: value}`` dict, so ``.value.values()`` gives
            only the value strings.

    See :class:`SortableKV` for the remaining arguments.
    """
    return _SortableKVElement(
        SortableKV(
            value,
            addable=addable,
            removable=removable,
            editable=editable,
            movable=movable,
            label=label,
            key_placeholder=key_placeholder,
            value_placeholder=value_placeholder,
            **kwargs,
        ),
        as_dict=as_dict,
    )
