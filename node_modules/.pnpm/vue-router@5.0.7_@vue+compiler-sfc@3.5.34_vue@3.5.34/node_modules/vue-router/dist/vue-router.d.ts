/*!
 * vue-router v5.0.7
 * (c) 2026 Eduardo San Martin Morote
 * @license MIT
 */
import { $ as createMemoryHistory, $t as RouteRecordInfo, An as RouteRecordNormalized, At as RouteLocationNormalizedLoadedTypedList, Bt as RouteRecordName, Cn as HistoryState, Ct as RouteLocationAsStringTypedList, Dn as PathParserOptions, Dt as RouteLocationNormalizedLoaded, En as createRouterMatcher, Et as RouteLocationNormalizedGeneric, Fn as parseQuery, Ft as RouteLocationResolvedGeneric, Gt as ParamValue, Ht as RouteRecordRedirectOption, In as stringifyQuery, It as RouteLocationResolvedTyped, Jt as ParamValueZeroOrOne, Kt as ParamValueOneOrMore, Ln as TypesConfig, Lt as RouteLocationResolvedTypedList, Mn as LocationQueryRaw, Mt as RouteLocationNormalizedTypedList, Nn as LocationQueryValue, Nt as RouteLocationRaw, On as _PathParserOptions, Ot as RouteLocationNormalizedLoadedGeneric, Pn as LocationQueryValueRaw, Pt as RouteLocationResolved, Q as createWebHashHistory, Qt as RouteMapGeneric, R as START_LOCATION_NORMALIZED, Rt as RouteLocationTyped, Sn as _RouteRecordBase, St as RouteLocationAsStringTyped, Tn as RouterMatcher, Tt as RouteLocationNormalized, Ut as _RouteRecordProps, Vt as RouteRecordNameGeneric, Wt as _Awaitable, X as RouterScrollBehavior, Xt as RouteParamsRaw, Yt as RouteParams, Zt as RouteMap, _ as routerViewLocationKey, _n as RouteRecordRaw, _t as RouteLocationAsRelative, a as RouterLink, an as RouteLocationMatched, at as NavigationGuardWithThis, b as RouterOptions, bn as RouteRecordSingleViewWithChildren, bt as RouteLocationAsRelativeTypedList, c as UseLinkReturn, cn as RouteLocationPathRaw, ct as NavigationFailure, d as loadRouteLocation, dn as RouteParamValueRaw, dt as isNavigationFailure, en as RouteRecordInfoGeneric, et as createWebHistory, f as onBeforeRouteLeave, fn as RouteParamsGeneric, ft as RouteLocation, g as routerKey, gn as RouteRecordMultipleViewsWithChildren, gt as RouteLocationAsPathTypedList, h as routeLocationKey, hn as RouteRecordMultipleViews, ht as RouteLocationAsPathTyped, i as RouterViewProps, in as RouteComponent, it as NavigationGuardReturn, jn as LocationQuery, jt as RouteLocationNormalizedTyped, kn as RouteRecord, kt as RouteLocationNormalizedLoadedTyped, l as _RouterLinkI, ln as RouteMeta, lt as NavigationFailureType, m as matchedRouteKey, mn as RouteQueryAndHash, mt as RouteLocationAsPathGeneric, n as useRouter, nn as MatcherLocation, nt as NavigationGuardNext, o as RouterLinkProps, on as RouteLocationNamedRaw, ot as NavigationHookAfter, p as onBeforeRouteUpdate, pn as RouteParamsRawGeneric, pt as RouteLocationAsPath, qt as ParamValueZeroOrMore, r as RouterView, rn as MatcherLocationAsPath, rt as NavigationGuardNextCallback, s as UseLinkOptions, sn as RouteLocationOptions, st as ErrorTypes, t as useRoute, tn as LocationAsRelativeRaw, tt as NavigationGuard, u as useLink, un as RouteParamValue, ut as NavigationRedirectError, v as viewDepthKey, vn as RouteRecordRedirect, vt as RouteLocationAsRelativeGeneric, wn as RouterHistory, wt as RouteLocationGeneric, x as createRouter, xn as _RouteLocationBase, xt as RouteLocationAsString, y as Router, yn as RouteRecordSingleView, yt as RouteLocationAsRelativeTyped, zt as RouteLocationTypedList } from "./useApi-D6ckOsFy.js";

//#region src/index.d.ts
declare module 'vue' {
  interface ComponentCustomOptions {
    /**
     * Guard called when the router is navigating to the route that is rendering
     * this component from a different route. Differently from `beforeRouteUpdate`
     * and `beforeRouteLeave`, `beforeRouteEnter` does not have access to the
     * component instance through `this` because it triggers before the component
     * is even mounted.
     *
     * @param to - RouteLocationRaw we are navigating to
     * @param from - RouteLocationRaw we are navigating from
     * @param next - function to validate, cancel or modify (by redirecting) the
     * navigation
     */
    beforeRouteEnter?: TypesConfig extends Record<'beforeRouteEnter', infer T> ? T : NavigationGuardWithThis<undefined>;
    /**
     * Guard called whenever the route that renders this component has changed, but
     * it is reused for the new route. This allows you to guard for changes in
     * params, the query or the hash.
     *
     * @param to - RouteLocationRaw we are navigating to
     * @param from - RouteLocationRaw we are navigating from
     * @param next - function to validate, cancel or modify (by redirecting) the
     * navigation
     */
    beforeRouteUpdate?: TypesConfig extends Record<'beforeRouteUpdate', infer T> ? T : NavigationGuard;
    /**
     * Guard called when the router is navigating away from the current route that
     * is rendering this component.
     *
     * @param to - RouteLocationRaw we are navigating to
     * @param from - RouteLocationRaw we are navigating from
     * @param next - function to validate, cancel or modify (by redirecting) the
     * navigation
     */
    beforeRouteLeave?: TypesConfig extends Record<'beforeRouteLeave', infer T> ? T : NavigationGuard;
  }
  interface ComponentCustomProperties {
    /**
     * Normalized current location. See {@link RouteLocationNormalizedLoaded}.
     */
    $route: TypesConfig extends Record<'$route', infer T> ? T : RouteLocationNormalizedLoaded;
    /**
     * {@link Router} instance used by the application.
     */
    $router: TypesConfig extends Record<'$router', infer T> ? T : Router;
  }
  interface GlobalComponents {
    RouterView: TypesConfig extends Record<'RouterView', infer T> ? T : typeof RouterView;
    RouterLink: TypesConfig extends Record<'RouterLink', infer T> ? T : typeof RouterLink;
  }
}
//#endregion
export { type ErrorTypes, type HistoryState, type LocationAsRelativeRaw, type LocationQuery, type LocationQueryRaw, type LocationQueryValue, type LocationQueryValueRaw, type MatcherLocation, type MatcherLocationAsPath, type NavigationFailure, NavigationFailureType, type NavigationGuard, type NavigationGuardNext, type NavigationGuardNextCallback, type NavigationGuardReturn, type NavigationGuardWithThis, type NavigationHookAfter, type NavigationRedirectError, type ParamValue, type ParamValueOneOrMore, type ParamValueZeroOrMore, type ParamValueZeroOrOne, type PathParserOptions, type RouteComponent, type RouteLocation, type RouteLocationAsPath, type RouteLocationAsPathGeneric, type RouteLocationAsPathTyped, type RouteLocationAsPathTypedList, type RouteLocationAsRelative, type RouteLocationAsRelativeGeneric, type RouteLocationAsRelativeTyped, type RouteLocationAsRelativeTypedList, type RouteLocationAsString, type RouteLocationAsStringTyped, type RouteLocationAsStringTypedList, type RouteLocationGeneric, type RouteLocationMatched, type RouteLocationNamedRaw, type RouteLocationNormalized, type RouteLocationNormalizedGeneric, type RouteLocationNormalizedLoaded, type RouteLocationNormalizedLoadedGeneric, type RouteLocationNormalizedLoadedTyped, type RouteLocationNormalizedLoadedTypedList, type RouteLocationNormalizedTyped, type RouteLocationNormalizedTypedList, type RouteLocationOptions, type RouteLocationPathRaw, type RouteLocationRaw, type RouteLocationResolved, type RouteLocationResolvedGeneric, type RouteLocationResolvedTyped, type RouteLocationResolvedTypedList, type RouteLocationTyped, type RouteLocationTypedList, type RouteMap, type RouteMapGeneric, type RouteMeta, type RouteParamValue, type RouteParamValueRaw, type RouteParams, type RouteParamsGeneric, type RouteParamsRaw, type RouteParamsRawGeneric, type RouteQueryAndHash, type RouteRecord, type RouteRecordInfo, type RouteRecordInfoGeneric, type RouteRecordMultipleViews, type RouteRecordMultipleViewsWithChildren, type RouteRecordName, type RouteRecordNameGeneric, type RouteRecordNormalized, type RouteRecordRaw, type RouteRecordRedirect, type RouteRecordRedirectOption, type RouteRecordSingleView, type RouteRecordSingleViewWithChildren, type Router, type RouterHistory, RouterLink, type RouterLinkProps, type RouterMatcher, type RouterOptions, type RouterScrollBehavior, RouterView, type RouterViewProps, START_LOCATION_NORMALIZED as START_LOCATION, type TypesConfig, type UseLinkOptions, type UseLinkReturn, type _Awaitable, type _PathParserOptions, type _RouteLocationBase, type _RouteRecordBase, type _RouteRecordProps, type _RouterLinkI, createMemoryHistory, createRouter, createRouterMatcher, createWebHashHistory, createWebHistory, isNavigationFailure, loadRouteLocation, matchedRouteKey, onBeforeRouteLeave, onBeforeRouteUpdate, parseQuery, routeLocationKey, routerKey, routerViewLocationKey, stringifyQuery, useLink, useRoute, useRouter, viewDepthKey };