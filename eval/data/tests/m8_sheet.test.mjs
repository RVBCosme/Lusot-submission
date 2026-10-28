// Tests for the M8 page's script, eval/data/m8_sheet.js (C208). The script runs here as a
// classic script, as it does in the page, but in a vm context without `document`.
// Run: node --test eval/data/tests/m8_sheet.test.mjs (test_m8_script.py runs it too).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../m8_sheet.js", import.meta.url), "utf8");
const template = readFileSync(new URL("../../templates/m8_labels.csv", import.meta.url), "utf8");
const context = vm.createContext({});
vm.runInContext(source, context, { filename: "m8_sheet.js" });
const { M8 } = context;
const HEADER = M8.COLUMNS.join(",");

// Objects made inside the vm context carry its prototypes, which deepEqual compares, so
// values from the script are compared as JSON.
const plain = (value) => JSON.parse(JSON.stringify(value));
// A CSV as the script writes it: \n after every line.
const csv = (...lines) => [...lines, ""].join("\n");

test("the script defines one global, M8", () => {
  assert.deepEqual(Object.keys(context), ["M8"]);
});

test("the script holds no </, so a page can embed it verbatim", () => {
  // Inside an HTML script element, a </ could end the element early. A <!-- could start
  // the parser's escaped states, in which the page's own end tag stops working.
  assert.equal(source.indexOf("</"), -1);
  assert.equal(source.indexOf("<!--"), -1);
});

test("fractionOf maps a click to fractions of the shown image", () => {
  const rect = { left: 10, top: 20, width: 200, height: 100 };
  assert.deepEqual(plain(M8.fractionOf(110, 70, rect)), { x: 0.5, y: 0.5 });
  assert.deepEqual(plain(M8.fractionOf(10 + 200 / 3, 20, rect)), { x: 0.3333, y: 0 });
  assert.deepEqual(plain(M8.fractionOf(210, 120, rect)), { x: 1, y: 1 });
  assert.equal(M8.fractionOf(5, 70, rect), null);
  assert.equal(M8.fractionOf(211, 70, rect), null);
  assert.equal(M8.fractionOf(110, 19, rect), null);
  assert.equal(M8.fractionOf(110, 121, rect), null);
});

test("references are numbered per photo and never reused", () => {
  const state = M8.newState(["A001", "A002"]);
  assert.equal(M8.addRef(state, "A001", "vehicle", 0.5, 0.4), "R1");
  assert.equal(M8.addRef(state, "A001", "wheel", 0.3, 0.7), "R2");
  assert.equal(M8.addRef(state, "A002", "person", 0.6, 0.5), "R1");
  M8.removeRef(state, "A001", "R2");
  assert.equal(M8.addRef(state, "A001", "wheel", 0.35, 0.7), "R3");
  M8.removeRef(state, "A001", "R3"); // the highest number goes too, and still isn't reused
  assert.equal(M8.addRef(state, "A001", "wheel", 0.4, 0.7), "R4");
  assert.equal(
    M8.toCsv(state),
    csv(
      HEADER,
      "A001,R1,vehicle,0.5,0.4,,,,,",
      "A001,R4,wheel,0.4,0.7,,,,,",
      "A002,R1,person,0.6,0.5,,,,,",
    ),
  );
});

test("export then import gives the same state", () => {
  const ids = ["A002", "A001", "A003"]; // not in id order, though the export's rows are
  const state = M8.newState(ids);
  M8.setMarks(state, "A002", "dark", ["reflection", "splash"]);
  const car = M8.addRef(state, "A002", "vehicle", 0.5, 0.4);
  M8.setValue(state, "A002", car, "vehicle_type", "suv_mpv");
  M8.setValue(state, "A002", car, "body_waterline", "door_sill");
  M8.removeRef(state, "A002", M8.addRef(state, "A002", "wheel", 0.1, 0.1));
  const wheel = M8.addRef(state, "A002", "wheel", 0.3333, 0.75);
  M8.setValue(state, "A002", wheel, "waterline", "hub");
  M8.setMarks(state, "A001", "ok", []);
  const person = M8.addRef(state, "A001", "person", 0.25, 1);
  M8.setValue(state, "A001", person, "waterline", "knee");
  M8.addRef(state, "A003", "wheel", 0.9, 0); // work in progress: no marks, no waterline
  const text = M8.toCsv(state);
  assert.equal(
    text,
    csv(
      HEADER,
      "A001,P1,photo,,,,,,ok,",
      "A001,R1,person,0.25,1,,,knee,,",
      "A002,P1,photo,,,,,,dark,reflection;splash",
      "A002,R1,vehicle,0.5,0.4,suv_mpv,door_sill,,,",
      "A002,R3,wheel,0.3333,0.75,,,hub,,",
      "A003,R1,wheel,0.9,0,,,,,",
    ),
  );
  const back = M8.fromCsv(text, ids);
  assert.equal(back.dropped, 0);
  assert.deepEqual(plain(back.state), plain(state));
  assert.equal(M8.toCsv(back.state), text);
});

test("the export header equals eval/templates/m8_labels.csv", () => {
  assert.equal(M8.toCsv(M8.newState(["A001"])), template);
});

test("import tolerates a BOM and CRLF and drops unknown photos", () => {
  const lines = [
    HEADER,
    "A009,P1,photo,,,,,,ok,",
    "A001,R10,wheel,0.2,0.8,,,rim_top,,",
    ",,,,,,,,,", // a blank row, as a spreadsheet may save one
    "A001,R9,wheel,0.6,0.8,,,hub,,",
    "A001,P1,photo,,,,,,blurry,moving",
    "A009,R1,person,0.5,0.5,,,waist,,",
    "",
  ];
  const bom = String.fromCharCode(0xfeff);
  const { state, dropped } = M8.fromCsv(bom + lines.join("\r\n"), ["A001", "A002"]);
  assert.equal(dropped, 2);
  assert.equal(
    M8.toCsv(state),
    csv(
      HEADER,
      "A001,P1,photo,,,,,,blurry,moving",
      "A001,R9,wheel,0.6,0.8,,,hub,,",
      "A001,R10,wheel,0.2,0.8,,,rim_top,,",
    ),
  );
  // Numbering resumes after the file's highest number.
  assert.equal(M8.addRef(state, "A001", "person", 0.5, 0.5), "R11");
});

test("import refuses a file it can't read whole", () => {
  const refused = (row) => () => M8.fromCsv(csv(HEADER, row), ["A001"]);
  assert.throws(() => M8.fromCsv(csv("candidate_id,photo_file"), ["A001"]), /^Error: header/);
  assert.throws(refused("A001,R1,wheel,0.5,0.5,,,hub,"), /^Error: row 1 cells: too_few$/);
  assert.throws(refused("A001,R1,boat,0.5,0.5,,,,,"), /^Error: row 1 kind: not_in_list$/);
  assert.throws(refused("A001,P1,wheel,0.5,0.5,,,hub,,"), /^Error: row 1 ref_id: bad_ref$/);
  assert.throws(refused("A001,R1,wheel,1.5,0.5,,,hub,,"), /^Error: row 1 x: out_of_range$/);
  assert.throws(refused("A001,R1,wheel,0.5,,,,hub,,"), /^Error: row 1 y: out_of_range$/);
  assert.throws(
    refused("A001,R1,wheel,0.5,0.5,van,,hub,,"),
    /^Error: row 1 vehicle_type: not_blank$/,
  );
  const twice = csv(HEADER, "A001,R1,wheel,0.5,0.5,,,hub,,", "A001,R1,person,0.2,0.5,,,knee,,");
  assert.throws(() => M8.fromCsv(twice, ["A001"]), /^Error: row 2 ref_id: duplicate_ref$/);
});

test("an import counts the rows it keeps and the rows it leaves out", () => {
  const text = csv(
    HEADER,
    "A001,P1,photo,,,,,,ok,",
    ",,,,,,,,,", // a blank row counts as neither
    "A001,R1,wheel,0.5,0.5,,,hub,,",
    "A009,P1,photo,,,,,,dark,",
  );
  const read = M8.readImport(text, ["A001", "A002"]);
  assert.deepEqual([read.kept, read.dropped], [2, 1]);
  assert.equal(
    M8.toCsv(read.state),
    csv(HEADER, "A001,P1,photo,,,,,,ok,", "A001,R1,wheel,0.5,0.5,,,hub,,"),
  );
});

test("an import that keeps no row for this page's photos is refused", () => {
  const foreign = csv(HEADER, "A009,P1,photo,,,,,,ok,", "A009,R1,wheel,0.5,0.5,,,hub,,");
  for (const text of [foreign, csv(HEADER)]) {
    assert.throws(
      () => M8.readImport(text, ["A001", "A002"]),
      /^Error: it has no rows for this page's photos$/,
    );
  }
  // Restoring the autosave still reads such a file, and reports what it leaves out.
  const { state, kept, dropped } = M8.fromCsv(foreign, ["A001", "A002"]);
  assert.deepEqual([kept, dropped], [0, 2]);
  assert.equal(M8.toCsv(state), csv(HEADER));
});

test("the photo's inline style pins the border and padding its click geometry assumes", () => {
  // fractionOf reads the photo's getBoundingClientRect(), which includes any border and
  // padding, and an inline style wins over the page's stylesheet.
  const style = /const IMAGE_STYLE =\s*"([^"]*)"/.exec(source)[1].split(";");
  assert.ok(style.includes("border:0"), style.join(";"));
  assert.ok(style.includes("padding:0"), style.join(";"));
});

test("problems name a photo without marks and a wheel without its waterline", () => {
  const state = M8.newState(["A001", "A002"]);
  M8.setMarks(state, "A001", "ok", []);
  M8.addRef(state, "A001", "wheel", 0.5, 0.5);
  const car = M8.addRef(state, "A001", "vehicle", 0.4, 0.4);
  M8.setValue(state, "A001", car, "vehicle_type", "van");
  assert.deepEqual(plain(M8.problems(state)), [
    "A001 R1.waterline: missing",
    "A001 R2.body_waterline: missing",
    "A002 P1.quality: missing",
  ]);
  M8.setValue(state, "A001", "R1", "waterline", "tire_only");
  M8.setValue(state, "A001", car, "body_waterline", "bumper");
  M8.setMarks(state, "A002", "blurry", []);
  assert.deepEqual(plain(M8.problems(state)), []);
});
