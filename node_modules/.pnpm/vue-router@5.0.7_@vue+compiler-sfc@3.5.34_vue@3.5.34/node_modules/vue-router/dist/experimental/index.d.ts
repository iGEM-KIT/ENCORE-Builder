/*!
 * vue-router v5.0.7
 * (c) 2026 Eduardo San Martin Morote
 * @license MIT
 */
import { a as DefineLoaderFn, b as trackRoute, c as UseDataLoaderResult, d as DataLoaderPlugin, f as DataLoaderPluginOptions, g as useIsDataLoading, h as reroute, i as DefineDataLoaderOptionsBase_LaxData, l as toLazyValue, m as SetupLoaderGuardOptions, n as DataLoaderEntryBase, o as UseDataLoader, p as NavigationResult$1, r as DefineDataLoaderOptionsBase_DefinedData, s as UseDataLoaderInternals, t as DataLoaderContextBase, u as ErrorDefault, v as getCurrentContext, x as withLoaderContext, y as setCurrentContext } from "../index-CzEDAlw7.js";
import { A as EXPERIMENTAL_RouterOptions, B as MatcherParamsFormatted, C as EXPERIMENTAL_RouteRecordNormalized_Group, D as EXPERIMENTAL_RouteRecord_Group, Dt as RouteLocationNormalizedLoaded, E as EXPERIMENTAL_RouteRecord_Base, F as createFixedResolver, G as MatcherPatternPathDynamic_ParamOptions, H as MatcherPatternHash, I as MatcherPatternQuery, J as MatcherQueryParamsValue, K as MatcherPatternPathStatic, L as MatcherPatternQueryParam, Ln as TypesConfig, M as EXPERIMENTAL_Router_Base, N as experimental_createRouter, O as EXPERIMENTAL_RouteRecord_Matchable, P as normalizeRouteRecord, S as EXPERIMENTAL_RouteRecordNormalized, T as EXPERIMENTAL_RouteRecordRaw, U as MatcherPatternPath, V as MatcherPattern, W as MatcherPatternPathDynamic, Y as ParamParser, Zt as RouteMap, _n as RouteRecordRaw, j as EXPERIMENTAL_RouterOptions_Base, k as EXPERIMENTAL_Router, q as MatcherQueryParams, w as EXPERIMENTAL_RouteRecordNormalized_Matchable, z as EmptyParams } from "../useApi-D6ckOsFy.js";

//#region src/experimental/route-resolver/matchers/param-parsers/define-param-parser.d.ts
/**
 * Defines a path param parser.
 *
 * @param parser - the parser to define. Will be returned as is.
 *
 * @see {@link defineQueryParamParser}
 * @see {@link defineParamParser}
 */
/*! #__NO_SIDE_EFFECTS__ */
declare function definePathParamParser<TParam, TUrlParam extends string | string[] | null = string | string[] | null, TParamRaw = TParam>(parser: Required<ParamParser<TParam, TUrlParam, TParamRaw>>): Required<ParamParser<TParam, TUrlParam, TParamRaw>>;
/**
 * Defines a query param parser. Note that query params can also be used as
 * path param parsers.
 *
 * @param parser - the parser to define. Will be returned as is.
 *
 * @see {@link definePathParamParser}
 * @see {@link defineParamParser}
 */
/*! #__NO_SIDE_EFFECTS__ */
declare function defineQueryParamParser<TParam, TParamRaw = TParam>(parser: Required<ParamParser<TParam, MatcherQueryParamsValue, TParamRaw>>): Required<ParamParser<TParam, MatcherQueryParamsValue, TParamRaw>>;
/**
 * Defines a param parser that works with any kind of param (path, repeatable,
 * optional, query, hash, ...) but requires the user to handle all cases in the
 * get and set functions (nullish, undefined, arrays, etc). This allows you to
 * have full control over the parsing logic, but it also means that you need to
 * handle all edge cases yourself. If possible, prefer using {@see defineParamParser}
 * which provides a more structured way to handle these
 * cases and automatically handles arrays and nullish values.
 *
 * @example
 *
 * Here is an example that allows arbitrary numbers (NaN values are filtered
 * out). It supports repeatable params, so it can be used both as a path param
 * parser and a query param parser.
 *
 * ```ts
 * export const parser = defineParamParserRaw<number>({
 *   get: value => {
 *     if (value == null) return null
 *     if (Array.isArray(value)) {
 *       return value
 *         .filter(v => v != null)
 *         .map(Number)
 *         .filter(v => !Number.isNaN(v))
 *     }
 *
 *     return Number.isNaN(Number(value))
 *       ? miss(`"${value}" is not a valid number`)
 *       : Number(value)
 *   },
 *
 *   set: value =>
 *     Array.isArray(value)
 *       ? value.map(String)
 *       : value == null
 *         ? null
 *         : String(value),
 * })
 * ```
 *
 * @see {@link defineParamParser}
 */
declare function defineParamParserRaw<TParam, TParamRaw = TParam>(parser: Required<ParamParser<TParam | TParam[] | null, MatcherQueryParamsValue, TParamRaw | TParamRaw[] | null>>): Required<ParamParser<TParam | TParam[] | null, MatcherQueryParamsValue, TParamRaw | TParamRaw[] | null>>;
/**
 * Defines a param parser that transforms strings to another type. Handles
 * optional and repeatable params, so it can be used for both path and query
 * params.
 *
 * @example
 *
 * Here is an example that allows arbitrary numbers (NaN values are filtered
 * out). It supports repeatable params, so it can be used both as a path param
 * parser and a query param parser.
 *
 * ```ts
 * import { miss } from 'vue-router/experimental'
 *
 * export const parser = defineParamParser<number>({
 *   get: value => {
 *     const num = Number(value)
 *     if (Number.isNaN(num)) {
 *       miss(`"${value}" is not a valid number`)
 *     }
 *     return num
 *   },
 *
 *   set: value => String(value),
 * })
 * ```
 *
 * @see {@link defineQueryParamParser}
 * @see {@link definePathParamParser}
 */
declare function defineParamParser<TParam, TParamRaw = TParam>(parser: Required<ParamParser<TParam, string, TParamRaw>>): Required<ParamParser<TParam | TParam[] | null, MatcherQueryParamsValue, TParamRaw | TParamRaw[] | null | undefined>>;
//#endregion
//#region src/experimental/route-resolver/matchers/param-parsers/booleans.d.ts
/**
 * Native Param parser for booleans.
 *
 * @internal
 */
declare const PARAM_PARSER_BOOL: {
  get: (value: NoInfer<MatcherQueryParamsValue>) => boolean | boolean[] | undefined;
  set: (value: boolean | boolean[] | null | undefined) => string | string[] | null | undefined;
};
//#endregion
//#region src/experimental/route-resolver/matchers/param-parsers/integers.d.ts
/**
 * Native Param parser for integers.
 *
 * @internal
 */
declare const PARAM_PARSER_INT: {
  get: (value: NoInfer<MatcherQueryParamsValue>) => number | number[] | null;
  set: (value: number | number[] | null) => string | string[] | null;
};
//#endregion
//#region src/experimental/route-resolver/matchers/param-parsers/standard-schema-types.d.ts
/**
 * Inlined subset of `@standard-schema/spec` v1.1.0 so the distributed code
 * has zero external type dependencies. Keep the package installed to track
 * upstream changes.
 *
 * @see https://github.com/standard-schema/standard-schema
 */
/** The Standard Schema interface. */
interface StandardSchemaV1<Input = unknown, Output = Input> {
  /** The Standard Schema properties. */
  readonly '~standard': StandardSchemaV1.Props<Input, Output>;
}
declare namespace StandardSchemaV1 {
  /** The Standard Schema properties interface. */
  interface Props<Input = unknown, Output = Input> {
    /** The version number of the standard. */
    readonly version: 1;
    /** The vendor name of the schema library. */
    readonly vendor: string;
    /** Inferred types associated with the schema. */
    readonly types?: Types<Input, Output> | undefined;
    /** Validates unknown input values. */
    readonly validate: (value: unknown) => Result<Output> | Promise<Result<Output>>;
  }
  /** The Standard Schema types interface. */
  interface Types<Input = unknown, Output = Input> {
    /** The input type of the schema. */
    readonly input: Input;
    /** The output type of the schema. */
    readonly output: Output;
  }
  /** The result interface of the validate function. */
  type Result<Output> = SuccessResult<Output> | FailureResult;
  /** The result interface if validation succeeds. */
  interface SuccessResult<Output> {
    /** The typed output value. */
    readonly value: Output;
    /** A falsy value for `issues` indicates success. */
    readonly issues?: undefined;
  }
  /** The result interface if validation fails. */
  interface FailureResult {
    /** The issues of failed validation. */
    readonly issues: ReadonlyArray<Issue>;
  }
  /** The issue interface of the failure output. */
  interface Issue {
    /** The error message of the issue. */
    readonly message: string;
    /** The path of the issue, if any. */
    readonly path?: ReadonlyArray<PropertyKey | PathSegment> | undefined;
  }
  /** The path segment interface of the issue. */
  interface PathSegment {
    /** The key representing a path segment. */
    readonly key: PropertyKey;
  }
  /** Infers the input type of a Standard Schema. */
  type InferInput<Schema extends StandardSchemaV1> = NonNullable<Schema['~standard']['types']>['input'];
  /** Infers the output type of a Standard Schema. */
  type InferOutput<Schema extends StandardSchemaV1> = NonNullable<Schema['~standard']['types']>['output'];
}
//#endregion
//#region src/experimental/route-resolver/matchers/param-parsers/standard-schema.d.ts
/**
 * Normalizes a param parser input, converting a StandardSchema-compliant object
 * into a {@link ParamParser} if needed.
 *
 * @param parser - a param parser or a StandardSchema-compliant validator
 *
 * @internal
 */
declare function normalizeParamParser<TParam = MatcherQueryParamsValue, TUrlParam = MatcherQueryParamsValue, TParamRaw = TParam>(parser: ParamParser<TParam, TUrlParam, TParamRaw> | StandardSchemaV1<unknown, TParam>): ParamParser<TParam, TUrlParam, TParamRaw>;
/**
 * Extracts the param type from Param Parsers or StandardSchema validators.
 *
 * @internal
 */
type ExtractParamParserType<PP> = PP extends ParamParser<infer T, any, any> ? T : PP extends StandardSchemaV1<unknown, infer T> ? T : unknown;
//#endregion
//#region src/experimental/route-resolver/matchers/errors.d.ts
/**
 * Error throw when a matcher matches by regex but validation fails.
 *
 * @internal
 */
declare class MatchMiss extends Error {
  name: string;
}
/**
 * Helper to throw a {@link MatchMiss} error.
 * @param args - Arguments to pass to the `MatchMiss` constructor.
 *
 * @example
 * ```ts
 * miss()
 * // in a number param matcher
 * miss('Number must be finite')
 * ```
 */
declare const miss: (...args: ConstructorParameters<typeof MatchMiss>) => never;
//#endregion
//#region src/experimental/runtime.d.ts
/**
 * Helper to define page properties with file-based routing.
 * **Doesn't do anything**, used for types only.
 *
 * @param route - route information to be added to this page
 *
 * @internal
 */
declare const definePage: (route: DefinePage) => DefinePage;
/**
 * Merges route records.
 *
 * @internal
 *
 * @param main - main route record
 * @param routeRecords - route records to merge
 * @returns merged route record
 */
declare function _mergeRouteRecord(main: RouteRecordRaw, ...routeRecords: Partial<RouteRecordRaw>[]): RouteRecordRaw;
/**
 * Type to define a page. Can be augmented to add custom properties.
 */
interface DefinePage extends Partial<Omit<RouteRecordRaw, 'children' | 'components' | 'component' | 'name'>> {
  /**
   * A route name. If not provided, the name will be generated based on the file path.
   * Can be set to `false` to remove the name from types.
   */
  name?: string | false;
  /**
   * Custom parameters for the route. Requires `experimental.paramParsers` enabled.
   *
   * @experimental
   */
  params?: {
    path?: Record<string, ParamParserType>;
    /**
     * Parameters extracted from the query.
     */
    query?: Record<string, DefinePageQueryParamOptions | ParamParserType>;
  };
}
type ParamParserType_Native = 'int' | 'bool';
type ParamParserType = (TypesConfig extends Record<'ParamParsers', infer ParamParsers> ? ParamParsers : never) | ParamParserType_Native;
/**
 * Configures how to extract a route param from a specific query parameter.
 */
interface DefinePageQueryParamOptions<T = unknown> {
  /**
   * The type of the query parameter. Allowed values are native param parsers
   * and any parser in the {@link https://uvr.esm.is/TODO | params folder }. If
   * not provided, the value will kept as is.
   */
  parser?: ParamParserType;
  /**
   * Default value if the query parameter is missing or if the match fails
   * (e.g. a invalid number is passed to the int param parser). If not provided
   * and the param is not required, the route will match with undefined.
   */
  default?: (() => T) | T;
  /**
   * How to format the query parameter value.
   *
   * - 'value' - keep the first value only and pass that to parser
   * - 'array' - keep all values (even one or none) as an array and pass that to parser
   *
   * @default 'value'
   */
  format?: 'value' | 'array';
  /**
   * Whether this query parameter is required. If true and the parameter is
   * missing (and no default is provided), the route will not match.
   *
   * @default false
   */
  required?: boolean;
}
//#endregion
//#region src/experimental/data-loaders/defineLoader.d.ts
/**
 * Creates a data loader composable that can be exported by pages to attach the data loading to a route. In this version `data` is always defined.
 *
 * @param name - name of the route
 * @param loader - function that returns a promise with the data
 * @param options - options to configure the data loader
 */
declare function defineBasicLoader<Name extends keyof RouteMap, Data>(name: Name, loader: DefineLoaderFn<Data, DataLoaderContext, RouteLocationNormalizedLoaded<Name>>, options?: DefineDataLoaderOptions_DefinedData): UseDataLoaderBasic_DefinedData<Data>;
/**
 * Creates a data loader composable that can be exported by pages to attach the data loading to a route. In this version, `data` can be `undefined`.
 *
 * @param name - name of the route
 * @param loader - function that returns a promise with the data
 * @param options - options to configure the data loader
 */
declare function defineBasicLoader<Name extends keyof RouteMap, Data>(name: Name, loader: DefineLoaderFn<Data, DataLoaderContext, RouteLocationNormalizedLoaded<Name>>, options: DefineDataLoaderOptions_LaxData): UseDataLoaderBasic_LaxData<Data>;
/**
 * Creates a data loader composable that can be exported by pages to attach the data loading to a route. In this version `data` is always defined.
 *
 * @param loader - function that returns a promise with the data
 * @param options - options to configure the data loader
 */
declare function defineBasicLoader<Data>(loader: DefineLoaderFn<Data, DataLoaderContext, RouteLocationNormalizedLoaded>, options?: DefineDataLoaderOptions_DefinedData): UseDataLoaderBasic_DefinedData<Data>;
/**
 * Creates a data loader composable that can be exported by pages to attach the data loading to a route. In this version, `data` can be `undefined`.
 *
 * @param loader - function that returns a promise with the data
 * @param options - options to configure the data loader
 */
declare function defineBasicLoader<Data>(loader: DefineLoaderFn<Data, DataLoaderContext, RouteLocationNormalizedLoaded>, options: DefineDataLoaderOptions_LaxData): UseDataLoaderBasic_LaxData<Data>;
interface DefineDataLoaderOptions_LaxData extends DefineDataLoaderOptionsBase_LaxData {
  /**
   * Key to use for SSR state. This will be used to read the initial data from `initialData`'s object.
   */
  key?: string;
}
interface DefineDataLoaderOptions_DefinedData extends DefineDataLoaderOptionsBase_DefinedData {
  key?: string;
}
/**
 * @deprecated use {@link DefineDataLoaderOptions_LaxData} instead
 */
type DefineDataLoaderOptions = DefineDataLoaderOptions_LaxData;
interface DataLoaderContext extends DataLoaderContextBase {}
/**
 * Symbol used to store the data in the router so it can be retrieved after the initial navigation.
 * @internal
 */
declare const SERVER_INITIAL_DATA_KEY: unique symbol;
/**
 * Initial data generated on server and consumed on client.
 * @internal
 */
declare const INITIAL_DATA_KEY: unique symbol;
declare module '../../router' {
  interface Router {
    /**
     * Gives access to the initial state during rendering. Should be set to `false` once it's consumed.
     * @internal
     */
    [SERVER_INITIAL_DATA_KEY]?: Record<string, unknown> | false;
    [INITIAL_DATA_KEY]?: Record<string, unknown> | false;
  }
}
interface UseDataLoaderBasic_LaxData<Data> extends UseDataLoader<Data | undefined, ErrorDefault> {}
/**
 * @deprecated use {@link UseDataLoaderBasic_LaxData} instead
 */
type UseDataLoaderBasic<Data> = UseDataLoaderBasic_LaxData<Data>;
interface UseDataLoaderBasic_DefinedData<Data> extends UseDataLoader<Data, ErrorDefault> {}
interface DataLoaderBasicEntry<TData, TError = unknown, TDataInitial extends TData | undefined = TData | undefined> extends DataLoaderEntryBase<TData, TError, TDataInitial> {}
//#endregion
//#region src/experimental/index.d.ts
/**
 * @deprecated Use {@link reroute} instead.
 */
declare class NavigationResult extends NavigationResult$1 {
  constructor(...args: ConstructorParameters<typeof NavigationResult$1>);
}
//#endregion
export { type DataLoaderBasicEntry, type DataLoaderContext, type DataLoaderContextBase, type DataLoaderEntryBase, DataLoaderPlugin, type DataLoaderPluginOptions, type DefineDataLoaderOptions, type DefineDataLoaderOptionsBase_DefinedData, type DefineDataLoaderOptionsBase_LaxData, type DefineDataLoaderOptions_DefinedData, type DefineDataLoaderOptions_LaxData, type DefineLoaderFn, type DefinePage, type DefinePageQueryParamOptions, type EXPERIMENTAL_RouteRecordNormalized, type EXPERIMENTAL_RouteRecordNormalized_Group, type EXPERIMENTAL_RouteRecordNormalized_Matchable, type EXPERIMENTAL_RouteRecordRaw, type EXPERIMENTAL_RouteRecord_Base, type EXPERIMENTAL_RouteRecord_Group, type EXPERIMENTAL_RouteRecord_Matchable, type EXPERIMENTAL_Router, type EXPERIMENTAL_RouterOptions, type EXPERIMENTAL_RouterOptions_Base, type EXPERIMENTAL_Router_Base, type EmptyParams, type ErrorDefault, type MatcherParamsFormatted, type MatcherPattern, type MatcherPatternHash, type MatcherPatternPath, MatcherPatternPathDynamic, type MatcherPatternPathDynamic_ParamOptions, MatcherPatternPathStatic, type MatcherPatternQuery, MatcherPatternQueryParam, type MatcherQueryParams, type MatcherQueryParamsValue, NavigationResult, PARAM_PARSER_BOOL, PARAM_PARSER_INT, type ParamParser, type ParamParserType, type ParamParserType_Native, type SetupLoaderGuardOptions, type UseDataLoader, type UseDataLoaderBasic, type UseDataLoaderBasic_DefinedData, type UseDataLoaderBasic_LaxData, type UseDataLoaderInternals, type UseDataLoaderResult, type ExtractParamParserType as _ExtractParamParserType, MatchMiss as _MatchMiss, NavigationResult$1 as _NavigationResult, _mergeRouteRecord, normalizeParamParser as _normalizeParamParser, createFixedResolver, defineBasicLoader, definePage, defineParamParser, defineParamParserRaw, definePathParamParser, defineQueryParamParser, experimental_createRouter, getCurrentContext, miss, normalizeRouteRecord, reroute, setCurrentContext, toLazyValue, trackRoute, useIsDataLoading, withLoaderContext };