/*!
 * vue-router v5.0.7
 * (c) 2026 Eduardo San Martin Morote
 * @license MIT
 */
import { a as getFileBasedRouteName, o as getPascalCaseRouteName, r as appendExtensionListToPattern } from "../utils-xJAnIh6o.mjs";
import { a as EditableTreeNode, c as MODULE_ROUTES_PATH, d as VIRTUAL_PREFIX, f as asVirtualId, h as createTreeNodeValue, i as createRoutesContext, l as ROUTES_LAST_LOAD_TIME, m as routeBlockQueryRE, n as createAutoExportPlugin, o as DEFINE_PAGE_QUERY_RE, p as getVirtualId, r as createViteContext, s as MODULE_RESOLVER_PATH, t as AutoExportLoaders, u as ROUTE_BLOCK_ID } from "../auto-exports-DQ4y7XZB.mjs";
import { DEFAULT_OPTIONS, mergeAllExtensions, resolveOptions } from "./options.mjs";
import { createUnplugin } from "unplugin";
import { join } from "pathe";

//#region src/unplugin/index.ts
var unplugin_default = createUnplugin((opt = {}, _meta) => {
	const options = resolveOptions(opt);
	const ctx = createRoutesContext(options);
	function getVirtualId$1(id) {
		if (options._inspect) return id;
		return getVirtualId(id);
	}
	function asVirtualId$1(id) {
		if (options._inspect) return id;
		return asVirtualId(id);
	}
	const pageFilePattern = appendExtensionListToPattern(options.filePatterns, mergeAllExtensions(options));
	const IDS_TO_INCLUDE = options.routesFolder.flatMap((routeOption) => pageFilePattern.map((pattern) => join(routeOption.src, pattern)));
	const plugins = [{
		name: "vue-router",
		enforce: "pre",
		resolveId: {
			filter: { id: { include: [
				new RegExp(`^${MODULE_ROUTES_PATH}$`),
				new RegExp(`^${MODULE_RESOLVER_PATH}$`),
				routeBlockQueryRE
			] } },
			handler(id) {
				if (id === MODULE_ROUTES_PATH || id === MODULE_RESOLVER_PATH) return asVirtualId$1(id);
				return ROUTE_BLOCK_ID;
			}
		},
		async buildStart() {
			await ctx.scanPages(options.watch);
		},
		buildEnd() {
			ctx.stopWatcher();
		},
		transform: {
			filter: { id: {
				include: [...IDS_TO_INCLUDE, DEFINE_PAGE_QUERY_RE],
				exclude: options.exclude
			} },
			handler(code, id) {
				return ctx.definePageTransform(code, id);
			}
		},
		load: {
			filter: { id: { include: [
				new RegExp(`^${ROUTE_BLOCK_ID}$`),
				new RegExp(`^${VIRTUAL_PREFIX}${MODULE_ROUTES_PATH}$`),
				new RegExp(`^${VIRTUAL_PREFIX}${MODULE_RESOLVER_PATH}$`)
			] } },
			handler(id) {
				if (id === ROUTE_BLOCK_ID) return {
					code: `export default {}`,
					map: null
				};
				const resolvedId = getVirtualId$1(id);
				if (resolvedId === MODULE_ROUTES_PATH) {
					ROUTES_LAST_LOAD_TIME.update();
					return ctx.generateRoutes();
				}
				if (resolvedId === MODULE_RESOLVER_PATH) {
					ROUTES_LAST_LOAD_TIME.update();
					return ctx.generateResolver();
				}
			}
		},
		vite: { configureServer(server) {
			ctx.setServerContext(createViteContext(server));
		} }
	}];
	if (options.experimental.autoExportsDataLoaders) plugins.push(createAutoExportPlugin({
		transformFilter: {
			include: IDS_TO_INCLUDE,
			exclude: options.exclude
		},
		loadersPathsGlobs: options.experimental.autoExportsDataLoaders,
		root: options.root
	}));
	return plugins;
});
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
const VueRouterAutoImports = {
	"vue-router": [
		"useRoute",
		"useRouter",
		"onBeforeRouteUpdate",
		"onBeforeRouteLeave"
	],
	"vue-router/experimental": ["definePage"]
};

//#endregion
export { AutoExportLoaders, DEFAULT_OPTIONS, EditableTreeNode, VueRouterAutoImports, createRoutesContext, createTreeNodeValue, unplugin_default as default, getFileBasedRouteName, getPascalCaseRouteName, resolveOptions };