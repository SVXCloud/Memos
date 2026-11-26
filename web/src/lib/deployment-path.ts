// Vite uses the same fixed mount as the Go HTTP entry point.
declare const __MEMOS_BASE_PATH__: string;
const basePath = __MEMOS_BASE_PATH__;

/** Convert a router-relative path to a browser-visible URL path. */
export const appPath = (path: string) => `${basePath}${path}`;

/** Remove the mount from a browser pathname before handing it to the router. */
export const routePath = (pathname: string) =>
  pathname === basePath ? "/" : pathname.startsWith(`${basePath}/`) ? pathname.slice(basePath.length) : pathname;

/** Build an absolute URL for a route from a browser or canonical instance URL. */
export const appURL = (path: string, instanceURL?: string) => new URL(appPath(path), instanceURL || window.location.origin).href;
