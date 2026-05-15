/*!
 * vue-router v5.0.7
 * (c) 2026 Eduardo San Martin Morote
 * @license MIT
 */
import { Options } from "./options.cjs";
import * as rolldown from "rolldown";

//#region src/unplugin/rolldown.d.ts
declare const _default: (options?: Options | undefined) => rolldown.Plugin<any> | rolldown.Plugin<any>[];
export = _default;