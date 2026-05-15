/*!
 * vue-router v5.0.7
 * (c) 2026 Eduardo San Martin Morote
 * @license MIT
 */
import { Options } from "./options.mjs";
import * as esbuild from "esbuild";

//#region src/unplugin/esbuild.d.ts
declare const _default: (options?: Options | undefined) => esbuild.Plugin;
//#endregion
export { _default as default };