/*!
 * vue-router v5.0.7
 * (c) 2026 Eduardo San Martin Morote
 * @license MIT
 */
import { a as getFileBasedRouteName, f as warn, s as isArray } from "../utils-xJAnIh6o.mjs";
import { resolve } from "pathe";
import { isPackageExists } from "local-pkg";

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
	getRouteName: getFileBasedRouteName,
	importMode: "async",
	root: process.cwd(),
	dts: isPackageExists("typescript"),
	logs: false,
	_inspect: false,
	pathParser: { dotNesting: true },
	watch: !process.env.CI,
	experimental: {}
};
function normalizeRoutesFolderOption(routesFolder) {
	return (isArray(routesFolder) ? routesFolder : [routesFolder]).map((routeOption) => normalizeRouteOption(typeof routeOption === "string" ? { src: routeOption } : routeOption));
}
function normalizeRouteOption(routeOption) {
	return {
		...routeOption,
		filePatterns: routeOption.filePatterns ? typeof routeOption.filePatterns === "function" ? routeOption.filePatterns : isArray(routeOption.filePatterns) ? routeOption.filePatterns : [routeOption.filePatterns] : void 0,
		exclude: routeOption.exclude ? typeof routeOption.exclude === "function" ? routeOption.exclude : isArray(routeOption.exclude) ? routeOption.exclude : [routeOption.exclude] : void 0
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
		src: resolve(root, routeOption.src)
	}));
	const paramParsers = options.experimental?.paramParsers ? options.experimental.paramParsers === true ? DEFAULT_PARAM_PARSERS_OPTIONS : {
		...DEFAULT_PARAM_PARSERS_OPTIONS,
		...options.experimental.paramParsers
	} : void 0;
	const paramParsersDir = (paramParsers?.dir ? isArray(paramParsers.dir) ? paramParsers.dir : [paramParsers.dir] : []).map((dir) => resolve(root, dir));
	const paramParsersInclude = paramParsers?.include ? isArray(paramParsers.include) ? paramParsers.include : [paramParsers.include] : DEFAULT_PARAM_PARSERS_OPTIONS.include;
	const paramParsersExclude = paramParsers?.exclude ? isArray(paramParsers.exclude) ? paramParsers.exclude : [paramParsers.exclude] : DEFAULT_PARAM_PARSERS_OPTIONS.exclude;
	const autoExportsDataLoaders = options.experimental?.autoExportsDataLoaders ? (isArray(options.experimental.autoExportsDataLoaders) ? options.experimental.autoExportsDataLoaders : [options.experimental.autoExportsDataLoaders]).map((path) => resolve(root, path)) : void 0;
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
			warn(`Invalid extension "${ext}". Extensions must start with a dot.`);
			return "." + ext;
		}
		return ext;
	}).sort((a, b) => b.length - a.length);
	const filePatterns = options.filePatterns ? isArray(options.filePatterns) ? options.filePatterns : [options.filePatterns] : DEFAULT_OPTIONS.filePatterns;
	const exclude = options.exclude ? isArray(options.exclude) ? options.exclude : [options.exclude] : DEFAULT_OPTIONS.exclude;
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
export { DEFAULT_OPTIONS, DEFAULT_PARAM_PARSERS_OPTIONS, mergeAllExtensions, resolveOptions, resolveOverridableOption };