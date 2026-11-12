// The chart the reader confirms: one region per unit. A turn end changes no unit, so the chart draws no arrow for it;
// the states where a turn end breaks a notice rule carry the mark.
import { NAME, step as words, unit } from "./words.mjs";

export const title = `a coordinator with two units and two workers (${process.env.MULTITASK_DESIGN ?? "today"})`;

export const state = (v) => ({ [NAME.a]: unit(v, "a"), [NAME.b]: unit(v, "b") });

export const step = words;
