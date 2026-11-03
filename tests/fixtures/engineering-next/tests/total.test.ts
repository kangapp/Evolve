import assert from "node:assert/strict";
import test from "node:test";
import { total } from "../src/total.ts";
test("original independent totals", () => { assert.equal(total([2, 3]), 5); assert.equal(total([]), 0); assert.equal(total([-2, 3]), 1); });
