/*!
 * vue-router v5.0.7
 * (c) 2026 Eduardo San Martin Morote
 * @license MIT
 */
import { Options } from "./options.mjs";
import * as rollup from "rollup";

//#region src/unplugin/rollup.d.ts
declare const _default: (options?: Options | undefined) => rollup.Plugin<any> | rollup.Plugin<any>[];
//#endregion
export { _default as default };