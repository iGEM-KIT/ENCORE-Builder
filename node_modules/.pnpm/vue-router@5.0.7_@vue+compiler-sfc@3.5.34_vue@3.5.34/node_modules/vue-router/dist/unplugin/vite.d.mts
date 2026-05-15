/*!
 * vue-router v5.0.7
 * (c) 2026 Eduardo San Martin Morote
 * @license MIT
 */
import { Options } from "./options.mjs";
import * as vite from "vite";

//#region src/unplugin/vite.d.ts
declare const _default: (options?: Options | undefined) => vite.Plugin<any> | vite.Plugin<any>[];
//#endregion
export { _default as default };