/*!
 * vue-router v5.0.7
 * (c) 2026 Eduardo San Martin Morote
 * @license MIT
 */
Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' });
const require_auto_exports = require('../auto-exports-BTSsMjsv.cjs');
const require_utils = require('../utils-4TZ4o1By.cjs');
let pathe = require("pathe");
let local_pkg = require("local-pkg");

//#region src/unplugin/options.ts
/**
* Resolves an overridable option by calling the function with the existing
* value if it's a function, otherwise returning the passed `value`. If `value`
* is undefined, it returns the `defaultValue` instead.
*
* @param defaultValue default value for the option
* @param value and overridable option
*
* @internal
*/
function resolveOverridableOption(defaultValue, value) {
	return typeof value === "function" ? value(defaultValue) : value ?? defaultValue;
}
/**
* Default options for experimental param parsers.
*/
const DEFAULT_PARAM_PARSERS_OPTIONS = {
	dir: ["src/params"],
	include: ["*.ts"],
	exclude: ["*.test.{ts,js}", "*.spec.{ts,js}"]
};
/**
* Default plugin options.
*/
const DEFAULT_OPTIONS = {
	extensions: [".vue"],
	exclude: [],
	routesFolder: "src/pages",
	filePatterns: ["**/*"],
	routeBlockLang: "json5",
	getRouteName: require_utils.getFileBasedRouteName,
	importMode: "async",
	root: process.cwd(),
	dts: (0, local_pkg.isPackageExists)("typescript"),
	logs: false,
	_inspect: false,
	pathParser: { dotNesting: true },
	watch: !process.env.CI,
	experimental: {}
};
function normalizeRoutesFolderOption(routesFolder) {
	return (require_utils.isArray(routesFolder) ? routesFolder : [routesFolder]).map((routeOption) => normalizeRouteOption(typeof routeOption === "string" ? { src: routeOption } : routeOption));
}
function normalizeRouteOption(routeOption) {
	return {
		...routeOption,
		filePatterns: routeOption.filePatterns ? typeof routeOption.filePatterns === "function" ? routeOption.filePatterns : require_utils.isArray(routeOption.filePatterns) ? routeOption.filePatterns : [routeOption.filePatterns] : void 0,
		exclude: routeOption.exclude ? typeof routeOption.exclude === "function" ? routeOption.exclude : require_utils.isArray(routeOption.exclude) ? routeOption.exclude : [routeOption.exclude] : void 0
	};
}
/**
* Normalize user options with defaults and resolved paths.
*
* @param options - user provided options
* @returns normalized options
*/
function resolveOptions(options) {
	const root = options.root || DEFAULT_OPTIONS.root;
	const routesFolder = normalizeRoutesFolderOption(options.routesFolder || DEFAULT_OPTIONS.routesFolder).map((routeOption) => ({
		...routeOption,
		src: (0, pathe.resolve)(root, routeOption.src)
	}));
	const paramParsers = options.experimental?.paramParsers ? options.experimental.paramParsers === true ? DEFAULT_PARAM_PARSERS_OPTIONS : {
		...DEFAULT_PARAM_PARSERS_OPTIONS,
		...options.experimental.paramParsers
	} : void 0;
	const paramParsersDir = (paramParsers?.dir ? require_utils.isArray(paramParsers.dir) ? paramParsers.dir : [paramParsers.dir] : []).map((dir) => (0, pathe.resolve)(root, dir));
	const paramParsersInclude = paramParsers?.include ? require_utils.isArray(paramParsers.include) ? paramParsers.include : [paramParsers.include] : DEFAULT_PARAM_PARSERS_OPTIONS.include;
	const paramParsersExclude = paramParsers?.exclude ? require_utils.isArray(paramParsers.exclude) ? paramParsers.exclude : [paramParsers.exclude] : DEFAULT_PARAM_PARSERS_OPTIONS.exclude;
	const autoExportsDataLoaders = options.experimental?.autoExportsDataLoaders ? (require_utils.isArray(options.experimental.autoExportsDataLoaders) ? options.experimental.autoExportsDataLoaders : [options.experimental.autoExportsDataLoaders]).map((path) => (0, pathe.resolve)(root, path)) : void 0;
	const experimental = {
		...options.experimental,
		autoExportsDataLoaders,
		paramParsers: paramParsers && {
			...paramParsers,
			dir: paramParsersDir,
			include: paramParsersInclude,
			exclude: paramParsersExclude
		}
	};
	if (options.extensions) options.extensions = options.extensions.map((ext) => {
		if (!ext.startsWith(".")) {
			require_utils.warn(`Invalid extension "${ext}". Extensions must start with a dot.`);
			return "." + ext;
		}
		return ext;
	}).sort((a, b) => b.length - a.length);
	const filePatterns = options.filePatterns ? require_utils.isArray(options.filePatterns) ? options.filePatterns : [options.filePatterns] : DEFAULT_OPTIONS.filePatterns;
	const exclude = options.exclude ? require_utils.isArray(options.exclude) ? options.exclude : [options.exclude] : DEFAULT_OPTIONS.exclude;
	return {
		...DEFAULT_OPTIONS,
		...options,
		experimental,
		routesFolder,
		filePatterns,
		exclude
	};
}
/**
* Merge all the possible extensions as an array of unique values
* @param options - user provided options
* @internal
*/
function mergeAllExtensions(options) {
	const allExtensions = new Set(options.extensions);
	for (const routeOption of options.routesFolder) if (routeOption.extensions) {
		const extensions = resolveOverridableOption(options.extensions, routeOption.extensions);
		for (const ext of extensions) allExtensions.add(ext);
	}
	return Array.from(allExtensions.values());
}

//#endregion
exports.DEFAULT_OPTIONS = DEFAULT_OPTIONS;
exports.DEFAULT_PARAM_PARSERS_OPTIONS = DEFAULT_PARAM_PARSERS_OPTIONS;
exports.mergeAllExtensions = mergeAllExtensions;
exports.resolveOptions = resolveOptions;
exports.resolveOverridableOption = resolveOverridableOption;