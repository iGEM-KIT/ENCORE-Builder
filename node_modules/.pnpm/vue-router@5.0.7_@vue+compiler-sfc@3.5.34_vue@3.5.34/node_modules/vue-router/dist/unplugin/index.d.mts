/*!
 * vue-router v5.0.7
 * (c) 2026 Eduardo San Martin Morote
 * @license MIT
 */
import { a as TreeNode, c as TreeNodeValueGroup, d as createTreeNodeValue, i as getPascalCaseRouteName, l as TreeNodeValueParam, n as EditableTreeNode, r as getFileBasedRouteName, s as TreeNodeValue, u as TreeNodeValueStatic } from "../index-BzSypdj8.mjs";
import { DEFAULT_OPTIONS, Options, ParamParsersOptions, ResolvedOptions, RoutesFolder, RoutesFolderOption, RoutesFolderOptionResolved, ServerContext, resolveOptions } from "./options.mjs";
import * as unplugin from "unplugin";
import { StringFilter } from "unplugin";
import { Plugin } from "vite";

//#region src/unplugin/core/context.d.ts
declare function createRoutesContext(options: ResolvedOptions): {
  scanPages: (startWatchers?: boolean) => Promise<void>;
  writeConfigFiles: () => void;
  setServerContext: (_server: ServerContext) => void;
  stopWatcher: () => void;
  generateRoutes: () => string;
  generateResolver: () => string;
  definePageTransform(code: string, id: string): unplugin.Thenable<unplugin.TransformResult>;
};
//#endregion
//#region src/experimental/data-loaders/auto-exports.d.ts
/**
 * {@link AutoExportLoaders} options.
 */
interface AutoExportLoadersOptions {
  /**
   * Filter page components to apply the auto-export. Passed to `transform.filter.id`.
   */
  transformFilter: StringFilter;
  /**
   * Globs to match the paths of the loaders.
   */
  loadersPathsGlobs: string | string[];
  /**
   * Root of the project. All paths are resolved relatively to this one.
   * @default `process.cwd()`
   */
  root?: string;
}
/**
 * Vite Plugin to automatically export loaders from page components.
 *
 * @param options Options
 * @experimental - This API is experimental and can be changed in the future. It's used internally by `experimental.autoExportsDataLoaders`

 */
declare function AutoExportLoaders({
  transformFilter,
  loadersPathsGlobs,
  root
}: AutoExportLoadersOptions): Plugin;
//#endregion
//#region src/unplugin/index.d.ts
declare const _default: unplugin.UnpluginInstance<Options | undefined, boolean>;
/**
 * Adds useful auto imports to the AutoImport config:
 * @example
 * ```js
 * import { VueRouterAutoImports } from 'vue-router/unplugin'
 *
 * AutoImport({
 *   imports: [VueRouterAutoImports],
 * }),
 * ```
 */
declare const VueRouterAutoImports: Record<string, Array<string | [importName: string, alias: string]>>;
//#endregion
export { AutoExportLoaders, type AutoExportLoadersOptions, DEFAULT_OPTIONS, EditableTreeNode, type Options, type ParamParsersOptions, type ResolvedOptions, type RoutesFolder, type RoutesFolderOption, type RoutesFolderOptionResolved, type TreeNode, type TreeNodeValue, type TreeNodeValueGroup, type TreeNodeValueParam, type TreeNodeValueStatic, VueRouterAutoImports, createRoutesContext, createTreeNodeValue, _default as default, getFileBasedRouteName, getPascalCaseRouteName, resolveOptions };