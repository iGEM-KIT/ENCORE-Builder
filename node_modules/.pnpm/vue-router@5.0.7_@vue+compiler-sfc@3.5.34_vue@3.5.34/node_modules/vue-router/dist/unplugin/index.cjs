/*!
 * vue-router v5.0.7
 * (c) 2026 Eduardo San Martin Morote
 * @license MIT
 */
Object.defineProperties(exports, { __esModule: { value: true }, [Symbol.toStringTag]: { value: 'Module' } });
const require_auto_exports = require('../auto-exports-BTSsMjsv.cjs');
const require_utils = require('../utils-4TZ4o1By.cjs');
const require_unplugin_options = require('./options.cjs');
let unplugin = require("unplugin");
let pathe = require("pathe");

//#region src/unplugin/index.ts
var unplugin_default = (0, unplugin.createUnplugin)((opt = {}, _meta) => {
	const options = require_unplugin_options.resolveOptions(opt);
	const ctx = require_auto_exports.createRoutesContext(options);
	function getVirtualId$1(id) {
		if (options._inspect) return id;
		return require_auto_exports.getVirtualId(id);
	}
	function asVirtualId$1(id) {
		if (options._inspect) return id;
		return require_auto_exports.asVirtualId(id);
	}
	const pageFilePattern = require_utils.appendExtensionListToPattern(options.filePatterns, require_unplugin_options.mergeAllExtensions(options));
	const IDS_TO_INCLUDE = options.routesFolder.flatMap((routeOption) => pageFilePattern.map((pattern) => (0, pathe.join)(routeOption.src, pattern)));
	const plugins = [{
		name: "vue-router",
		enforce: "pre",
		resolveId: {
			filter: { id: { include: [
				new RegExp(`^${require_auto_exports.MODULE_ROUTES_PATH}$`),
				new RegExp(`^${require_auto_exports.MODULE_RESOLVER_PATH}$`),
				require_auto_exports.routeBlockQueryRE
			] } },
			handler(id) {
				if (id === require_auto_exports.MODULE_ROUTES_PATH || id === require_auto_exports.MODULE_RESOLVER_PATH) return asVirtualId$1(id);
				return require_auto_exports.ROUTE_BLOCK_ID;
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
				include: [...IDS_TO_INCLUDE, require_auto_exports.DEFINE_PAGE_QUERY_RE],
				exclude: options.exclude
			} },
			handler(code, id) {
				return ctx.definePageTransform(code, id);
			}
		},
		load: {
			filter: { id: { include: [
				new RegExp(`^${require_auto_exports.ROUTE_BLOCK_ID}$`),
				new RegExp(`^${require_auto_exports.VIRTUAL_PREFIX}${require_auto_exports.MODULE_ROUTES_PATH}$`),
				new RegExp(`^${require_auto_exports.VIRTUAL_PREFIX}${require_auto_exports.MODULE_RESOLVER_PATH}$`)
			] } },
			handler(id) {
				if (id === require_auto_exports.ROUTE_BLOCK_ID) return {
					code: `export default {}`,
					map: null
				};
				const resolvedId = getVirtualId$1(id);
				if (resolvedId === require_auto_exports.MODULE_ROUTES_PATH) {
					require_auto_exports.ROUTES_LAST_LOAD_TIME.update();
					return ctx.generateRoutes();
				}
				if (resolvedId === require_auto_exports.MODULE_RESOLVER_PATH) {
					require_auto_exports.ROUTES_LAST_LOAD_TIME.update();
					return ctx.generateResolver();
				}
			}
		},
		vite: { configureServer(server) {
			ctx.setServerContext(require_auto_exports.createViteContext(server));
		} }
	}];
	if (options.experimental.autoExportsDataLoaders) plugins.push(require_auto_exports.createAutoExportPlugin({
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
exports.AutoExportLoaders = require_auto_exports.AutoExportLoaders;
exports.DEFAULT_OPTIONS = require_unplugin_options.DEFAULT_OPTIONS;
exports.EditableTreeNode = require_auto_exports.EditableTreeNode;
exports.VueRouterAutoImports = VueRouterAutoImports;
exports.createRoutesContext = require_auto_exports.createRoutesContext;
exports.createTreeNodeValue = require_auto_exports.createTreeNodeValue;
exports.default = unplugin_default;
exports.getFileBasedRouteName = require_utils.getFileBasedRouteName;
exports.getPascalCaseRouteName = require_utils.getPascalCaseRouteName;
exports.resolveOptions = require_unplugin_options.resolveOptions;