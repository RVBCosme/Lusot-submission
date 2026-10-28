// The M8 page's script (spec §5.4, C208). On each Set A photo, Rene clicks every vehicle,
// wheel and person he can read and picks its values from Table 5's lists, then sets the
// photo's marks. The page keeps his work in the browser and exports m8_labels.csv (§5.9).
//
// A classic script, no modules. It defines one global, M8, and runs nothing as it loads:
// its tests run it in node, where there is no document. m8_sheet.py embeds its text
// verbatim in the page's one script element, so the text holds no closing-tag opener; the
// tests check that. After this text, at the end of the page's body, the page runs
//   M8.start(document, window, data)
// where data has exactly these keys:
//   photos            [{id, file}], each shown from raw/<file>, beside the page
//   vehicleTypes, bodyWaterlines, wheelWaterlines, personWaterlines: Table 5's lists
//   storageKey        the localStorage key that holds the autosaved CSV
// The M8 columns, the qualities and the subset tags live here, not in data.
//
// The state, which the pure functions read and change in place:
//   {photos: {<id>: {marks, refs, next}}}
// marks is null until set, then {quality, subsets}. Each ref is {id, kind, x, y} plus its
// kind's value columns, blank until picked. next is the photo's next R number, so a removed
// number is never handed out again. An import resumes after the file's highest number.
var M8 = (function () {
  "use strict";

  // eval/templates/m8_labels.csv's header, formats.M8_COLUMNS.
  const COLUMNS = Object.freeze([
    "photo_id",
    "ref_id",
    "kind",
    "x",
    "y",
    "vehicle_type",
    "body_waterline",
    "waterline",
    "quality",
    "subsets",
  ]);
  // Each kind of reference, with the columns of its values. A photo's own row, P1, holds
  // its marks instead.
  const VALUES = {
    vehicle: ["vehicle_type", "body_waterline"],
    wheel: ["waterline"],
    person: ["waterline"],
  };
  // formats.QUALITIES and formats.SUBSET_TAGS, in order; test_m8_script.py ties them.
  const QUALITIES = Object.freeze(["ok", "dark", "blurry"]);
  const SUBSETS = Object.freeze(["reflection", "splash", "moving"]);
  const REF_ID = /^R[1-9][0-9]*$/;
  const DECIMAL = /^[0-9]+(\.[0-9]+)?$/;

  // A click's position in the shown image, whose box is rect (its getBoundingClientRect()),
  // as fractions of its width and height from the top left, to 4 decimals; null outside.
  function fractionOf(clientX, clientY, rect) {
    const x = (clientX - rect.left) / rect.width;
    const y = (clientY - rect.top) / rect.height;
    if (!(x >= 0 && x <= 1 && y >= 0 && y <= 1)) return null; // a box with no size gives NaN
    return { x: Math.round(x * 10000) / 10000, y: Math.round(y * 10000) / 10000 };
  }

  function newState(photoIds) {
    const photos = {};
    for (const id of photoIds) photos[id] = { marks: null, refs: [], next: 1 };
    return { photos };
  }

  // Adds a reference with blank values, and returns its id.
  function addRef(state, photoId, kind, x, y) {
    const photo = photoOf(state, photoId);
    const ref = { id: "R" + photo.next, kind, x, y };
    for (const column of VALUES[kind]) ref[column] = "";
    photo.next += 1;
    photo.refs.push(ref);
    return ref.id;
  }

  function setValue(state, photoId, refId, column, value) {
    const ref = photoOf(state, photoId).refs.find((item) => item.id === refId);
    if (!ref || !VALUES[ref.kind].includes(column)) {
      throw new Error(photoId + " " + refId + "." + column + ": no such value");
    }
    ref[column] = value;
  }

  function removeRef(state, photoId, refId) {
    const photo = photoOf(state, photoId);
    photo.refs = photo.refs.filter((ref) => ref.id !== refId);
  }

  // The photo's own row, P1: its quality (blank until picked) and a list of subset tags.
  function setMarks(state, photoId, quality, subsets) {
    photoOf(state, photoId).marks = { quality, subsets: subsets.slice() };
  }

  // The CSV, as MS2's tools write one: no BOM, and \n after every line. Every cell is an
  // id, a number or a listed word, none with a comma, quote or line break, so none is
  // quoted.
  function toCsv(state) {
    const lines = [COLUMNS.join(",")];
    for (const photoId of Object.keys(state.photos).sort()) {
      const photo = state.photos[photoId];
      if (photo.marks) {
        const marks = { quality: photo.marks.quality, subsets: photo.marks.subsets.join(";") };
        lines.push(joined({ photo_id: photoId, ref_id: "P1", kind: "photo", ...marks }));
      }
      for (const ref of byNumber(photo.refs)) {
        const point = { x: String(ref.x), y: String(ref.y) };
        const cells = { photo_id: photoId, ref_id: ref.id, kind: ref.kind, ...point };
        for (const column of VALUES[ref.kind]) cells[column] = ref[column];
        lines.push(joined(cells));
      }
    }
    return lines.join("\n") + "\n";
  }

  // Reads a CSV that toCsv wrote, with or without a BOM, with \n or \r\n line endings, and
  // returns {state, kept, dropped}. Blank rows are skipped. kept counts the rows read for
  // photos in photoIds, and dropped the rows of other photos, which are left out. Any other
  // row that can't be read whole refuses the file: it throws an Error naming the row and
  // column, never a cell's text. Values aren't checked against their lists: the intake
  // does that.
  function fromCsv(text, photoIds) {
    const body = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text; // past a BOM
    const lines = body.split(/\r?\n/);
    if (cellsOf(lines[0]).join(",") !== COLUMNS.join(",")) {
      throw new Error("header: not the M8 columns");
    }
    const state = newState(photoIds);
    let kept = 0;
    let dropped = 0;
    lines.slice(1).forEach((line, index) => {
      const cells = cellsOf(line);
      if (cells.every((cell) => cell === "")) return;
      const where = "row " + (index + 1); // as the tools number a CSV's data rows
      if (cells.length !== COLUMNS.length) {
        fail(where, "cells", cells.length > COLUMNS.length ? "too_many" : "too_few");
      }
      const row = {};
      COLUMNS.forEach((column, i) => {
        row[column] = cells[i];
      });
      if (Object.hasOwn(state.photos, row.photo_id)) {
        readRow(state.photos[row.photo_id], row, where);
        kept += 1;
      } else {
        dropped += 1;
      }
    });
    return { state, kept, dropped };
  }

  // Reads a file to import, whose rows are to replace the page's labels and their autosave.
  // A file that keeps no row for the page's photos, such as another set's export or an
  // empty one, is refused, since importing it would empty the page.
  function readImport(text, photoIds) {
    const read = fromCsv(text, photoIds);
    if (read.kept === 0) throw new Error("it has no rows for this page's photos");
    return read;
  }

  // What is left to label, in the export's order: a photo whose quality isn't picked, and
  // each blank value of a reference, in the intake's form, <photo_id> <ref_id>.<column>:
  // missing. A photo with no marks at all reads P1.quality too, where the intake, finding
  // no P1 row, reports <photo_id> m8: no_photo_row.
  function problems(state) {
    const found = [];
    for (const photoId of Object.keys(state.photos).sort()) {
      const photo = state.photos[photoId];
      if (!photo.marks || photo.marks.quality === "") {
        found.push(photoId + " P1.quality: missing");
      }
      for (const ref of byNumber(photo.refs)) {
        for (const column of VALUES[ref.kind]) {
          if (ref[column] === "") found.push(photoId + " " + ref.id + "." + column + ": missing");
        }
      }
    }
    return found;
  }

  function photoOf(state, photoId) {
    if (!Object.hasOwn(state.photos, photoId)) throw new Error(photoId + ": not on this page");
    return state.photos[photoId];
  }

  function byNumber(refs) {
    return refs.slice().sort((a, b) => Number(a.id.slice(1)) - Number(b.id.slice(1)));
  }

  function joined(cells) {
    return COLUMNS.map((column) => cells[column] || "").join(",");
  }

  function cellsOf(line) {
    return line.split(",").map((cell) => cell.trim());
  }

  function fail(where, column, kind) {
    throw new Error(where + " " + column + ": " + kind);
  }

  // One row of a known photo: its photo row, or a reference with its point and values.
  function readRow(photo, row, where) {
    let filled; // the columns after photo_id, ref_id and kind that this row may fill
    if (row.kind === "photo") {
      if (row.ref_id !== "P1") fail(where, "ref_id", "bad_ref");
      if (photo.marks) fail(where, "ref_id", "duplicate_ref");
      filled = ["quality", "subsets"];
    } else if (Object.hasOwn(VALUES, row.kind)) {
      if (!REF_ID.test(row.ref_id)) fail(where, "ref_id", "bad_ref");
      if (photo.refs.some((ref) => ref.id === row.ref_id)) fail(where, "ref_id", "duplicate_ref");
      for (const column of ["x", "y"]) {
        if (!DECIMAL.test(row[column]) || Number(row[column]) > 1) {
          fail(where, column, "out_of_range");
        }
      }
      filled = ["x", "y", ...VALUES[row.kind]];
    } else {
      fail(where, "kind", "not_in_list");
    }
    for (const column of COLUMNS.slice(3)) {
      if (row[column] !== "" && !filled.includes(column)) fail(where, column, "not_blank");
    }
    if (row.kind === "photo") {
      const subsets = row.subsets.split(";").map((tag) => tag.trim());
      photo.marks = { quality: row.quality, subsets: subsets.filter((tag) => tag !== "") };
      return;
    }
    const ref = { id: row.ref_id, kind: row.kind, x: Number(row.x), y: Number(row.y) };
    for (const column of VALUES[row.kind]) ref[column] = row[column];
    photo.refs.push(ref);
    photo.next = Math.max(photo.next, Number(row.ref_id.slice(1)) + 1);
  }

  // Inline styles only where the page's geometry depends on them; the page's stylesheet
  // does the rest, and an inline style wins over it. The photo has no border or padding,
  // so its box, which fractionOf reads, is the photo itself. align-items keeps the frame as
  // tall as its photo, so the marker layer lies exactly over it. The list's small basis
  // keeps it beside the photo when there is room, so a click's values are picked without
  // scrolling. A marker is white on dark red (about 7:1), edged in white so it shows on
  // dark photos too.
  const ROW_STYLE = "display:flex;flex-wrap:wrap;gap:12px;align-items:flex-start";
  const LIST_STYLE = "flex:1 1 16em;margin:0";
  const FRAME_STYLE = "position:relative;max-width:100%";
  const IMAGE_STYLE =
    "display:block;border:0;padding:0;max-width:100%;max-height:70vh;cursor:crosshair";
  const LAYER_STYLE = "position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none";
  const MARKER_STYLE =
    "position:absolute;transform:translate(-50%,-50%);padding:0 4px;border:2px solid #fff;" +
    "border-radius:9px;background:#b00020;color:#fff;font:bold 13px/18px sans-serif;";
  // What the next click on a photo marks, and where Rene clicks for it.
  const AIMS = [
    ["vehicle", "a vehicle's body"],
    ["wheel", "a wheel's hub"],
    ["person", "a person's torso"],
  ];

  // Builds the page at the end of doc's body: the tools, the list of what is left to label,
  // then each photo with its marks and its references. Every change is saved at once.
  function start(doc, win, data) {
    const ids = data.photos.map((photo) => photo.id);
    const choices = {
      vehicle: { vehicle_type: data.vehicleTypes, body_waterline: data.bodyWaterlines },
      wheel: { waterline: data.wheelWaterlines },
      person: { waterline: data.personWaterlines },
    };
    const views = {};
    let state = newState(ids);

    const make = (tag, text) => {
      const node = doc.createElement(tag);
      if (text) node.textContent = text;
      return node;
    };
    const button = (text, act) => {
      const node = make("button", text);
      node.type = "button";
      node.addEventListener("click", act);
      return node;
    };
    // A control with its visible label: a box's after it, a select's before it.
    const labelled = (text, control) => {
      const label = make("label");
      if (control.type === "checkbox" || control.type === "radio") {
        label.append(control, " " + text);
      } else {
        label.append(text + " ", control);
      }
      return label;
    };
    // A select of the listed values after a blank one. A value from an imported file that
    // isn't listed is shown too, so the page never hides what it holds.
    const picker = (values, current, pick) => {
      const select = make("select");
      const shown = current === "" || values.includes(current) ? values : [...values, current];
      for (const value of ["", ...shown]) {
        const option = make("option", value || "pick one");
        option.value = value;
        select.append(option);
      }
      select.value = current;
      select.addEventListener("change", () => pick(select.value));
      return select;
    };

    const status = make("p");
    status.setAttribute("role", "status");
    status.setAttribute("aria-atomic", "true");
    const say = (text) => {
      status.textContent = text;
    };
    const rows = (count) => count + (count === 1 ? " row" : " rows");

    const todo = make("details");
    todo.className = "m8-todo";
    const todoTitle = make("summary");
    const todoList = make("ul");
    todo.append(todoTitle, todoList);
    const drawTodo = () => {
      const found = problems(state);
      todoTitle.textContent = found.length
        ? "Left to label: " + found.length
        : "Nothing left to label";
      todoList.textContent = "";
      for (const problem of found) {
        const link = make("a", problem);
        link.href = "#m8-" + problem.split(" ")[0];
        const item = make("li");
        item.append(link);
        todoList.append(item);
      }
    };

    const save = () => {
      try {
        win.localStorage.setItem(data.storageKey, toCsv(state));
      } catch (error) {
        say("Couldn't save in this browser (" + error.name + "). Export to keep your work.");
      }
      drawTodo();
    };

    const marksOf = (id) => state.photos[id].marks || { quality: "", subsets: [] };
    const drawPhoto = (id) => {
      const view = views[id];
      const marks = marksOf(id);
      view.marksBox.textContent = "";
      view.marksBox.append(make("legend", "Photo marks"));
      const quality = picker(QUALITIES, marks.quality, (value) => {
        setMarks(state, id, value, marksOf(id).subsets);
        save();
      });
      view.marksBox.append(labelled("quality", quality));
      const boxes = SUBSETS.map((tag) => {
        const box = make("input");
        box.type = "checkbox";
        box.value = tag;
        box.checked = marks.subsets.includes(tag);
        box.addEventListener("change", () => {
          const checked = boxes.filter((item) => item.checked).map((item) => item.value);
          setMarks(state, id, marksOf(id).quality, checked);
          save();
        });
        view.marksBox.append(" ", labelled(tag, box));
        return box;
      });

      view.layer.textContent = "";
      view.list.textContent = "";
      for (const ref of state.photos[id].refs) {
        const marker = make("span", ref.id);
        marker.style.cssText =
          MARKER_STYLE + "left:" + ref.x * 100 + "%;top:" + ref.y * 100 + "%";
        view.layer.append(marker);
        const item = make("li", ref.id + " " + ref.kind);
        for (const column of VALUES[ref.kind]) {
          const select = picker(choices[ref.kind][column], ref[column], (value) => {
            setValue(state, id, ref.id, column, value);
            save();
          });
          item.append(" ", labelled(column, select));
        }
        const remove = button("Remove " + ref.id, () => {
          removeRef(state, id, ref.id);
          save();
          drawPhoto(id);
        });
        item.append(" ", remove);
        view.list.append(item);
      }
    };
    const drawAll = () => {
      for (const id of ids) drawPhoto(id);
      drawTodo();
    };

    const exportCsv = () => {
      const url = win.URL.createObjectURL(new win.Blob([toCsv(state)], { type: "text/csv" }));
      const link = make("a");
      link.href = url;
      link.download = "m8_labels.csv";
      doc.body.append(link);
      link.click();
      link.remove();
      win.URL.revokeObjectURL(url);
      const left = problems(state).length;
      say(
        left
          ? "Exported m8_labels.csv, with " + left + " left to label."
          : "Exported m8_labels.csv, with nothing left to label. Move it into set_a\\.",
      );
    };

    const chooser = make("input");
    chooser.type = "file";
    chooser.accept = ".csv";
    chooser.addEventListener("change", () => {
      const file = chooser.files[0];
      chooser.value = ""; // so that choosing the same file again still counts
      if (!file) return;
      const unchanged = " The labels on this page are unchanged.";
      file.text().then(
        (text) => {
          let read;
          try {
            read = readImport(text, ids);
          } catch (error) {
            say("Couldn't import the file: " + error.message + "." + unchanged);
            return;
          }
          // Both counts go in the question, before anything is replaced.
          const kept = rows(read.kept) + " for this page's photos";
          const left = rows(read.dropped) + " for other photos";
          const question = "Replace the labels on this page with the file's?";
          if (!win.confirm(question + " It keeps " + kept + " and leaves out " + left + ".")) {
            return;
          }
          state = read.state;
          save();
          drawAll();
          say("Imported the file: it kept " + kept + " and left out " + left + ".");
        },
        () => say("Couldn't read the file." + unchanged),
      );
    });

    const clear = () => {
      const question =
        "Clear the labels from this browser and from this page? " +
        "Export them first if you still need them.";
      if (!win.confirm(question)) return;
      try {
        win.localStorage.removeItem(data.storageKey);
      } catch (error) {
        say("Couldn't clear this browser's saved work (" + error.name + ").");
        return;
      }
      state = newState(ids);
      drawAll();
      say("Cleared the saved work. This browser no longer holds the labels.");
    };

    const tools = make("div");
    tools.className = "m8-tools";
    tools.append(
      button("Export m8_labels.csv", exportCsv),
      " ",
      labelled("Import m8_labels.csv", chooser),
      " ",
      button("Clear saved work", clear),
      status,
    );
    doc.body.append(tools, todo);

    for (const photo of data.photos) {
      const marksBox = make("fieldset");
      const aim = make("fieldset");
      aim.append(make("legend", "Next click marks"));
      let kind = AIMS[0][0];
      for (const [name, where] of AIMS) {
        const radio = make("input");
        radio.type = "radio";
        radio.name = "m8-next-" + photo.id;
        radio.checked = name === kind;
        radio.addEventListener("change", () => {
          kind = name;
        });
        aim.append(" ", labelled(where, radio));
      }

      const image = make("img");
      image.src = "raw/" + encodeURIComponent(photo.file);
      image.alt = "Photo " + photo.id;
      image.style.cssText = IMAGE_STYLE;
      image.addEventListener("click", (event) => {
        if (!image.naturalWidth) return; // not loaded, so its box isn't the photo's
        const point = fractionOf(event.clientX, event.clientY, image.getBoundingClientRect());
        if (!point) return;
        addRef(state, photo.id, kind, point.x, point.y);
        save();
        drawPhoto(photo.id);
      });
      const layer = make("div");
      layer.style.cssText = LAYER_STYLE;
      layer.setAttribute("aria-hidden", "true"); // the list below says the same
      const frame = make("div");
      frame.style.cssText = FRAME_STYLE;
      frame.append(image, layer);
      const list = make("ul");
      list.style.cssText = LIST_STYLE;
      const row = make("div");
      row.style.cssText = ROW_STYLE;
      row.append(frame, list);

      const section = make("section");
      section.id = "m8-" + photo.id;
      section.className = "m8-photo";
      section.append(make("h2", photo.id), marksBox, aim, row);
      doc.body.append(section);
      views[photo.id] = { marksBox, layer, list };
    }

    let saved = null;
    try {
      saved = win.localStorage.getItem(data.storageKey);
    } catch (error) {
      say("This browser won't keep your work (" + error.name + "). Export it as you go.");
    }
    if (saved !== null) {
      try {
        const read = fromCsv(saved, ids);
        state = read.state;
        const left = read.dropped
          ? " Left out " + rows(read.dropped) + " saved for photos not on this page;" +
            " your next change drops them."
          : "";
        say("Restored the labels saved in this browser." + left);
      } catch (error) {
        say(
          "The labels saved in this browser couldn't be read (" + error.message + ")," +
            " so the page starts empty. Your next change replaces them.",
        );
      }
    }
    drawAll();
  }

  return {
    COLUMNS,
    QUALITIES,
    SUBSETS,
    fractionOf,
    newState,
    addRef,
    setValue,
    removeRef,
    setMarks,
    toCsv,
    fromCsv,
    readImport,
    problems,
    start,
  };
})();
