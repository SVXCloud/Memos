// Package deployment defines the fixed HTTP mount shared with the SPA build.
package deployment

import (
	_ "embed"
	"net/http"
	"net/url"
	"strings"
)

//go:embed base-path.txt
var basePath string

// BasePath is the fixed mount without a trailing slash.
func BasePath() string {
	return strings.TrimSpace(basePath)
}

// Unprefix translates a mounted path to an internal path, preserving legacy
// paths such as those stored in Markdown.
func Unprefix(path string) string {
	if rest, ok := strings.CutPrefix(path, BasePath()+"/"); ok {
		return "/" + rest
	}
	return path
}

// PublicURL appends the fixed mount to a validated instance origin.
func PublicURL(instanceURL string) string {
	parsed, err := url.Parse(instanceURL)
	if err != nil || parsed.Host == "" {
		return ""
	}
	return parsed.Scheme + "://" + parsed.Host + BasePath()
}

// Mount dispatches only requests addressed to the fixed mount. StripPrefix
// clones the URL and preserves escaping, queries, and the response writer.
func Mount(next http.Handler) http.Handler {
	prefix := BasePath()
	mounted := http.StripPrefix(prefix, next)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch escapedPath := r.URL.EscapedPath(); {
		case escapedPath == prefix:
			target := prefix + "/"
			if r.URL.RawQuery != "" || r.URL.ForceQuery {
				target += "?" + r.URL.RawQuery
			}
			http.Redirect(w, r, target, http.StatusPermanentRedirect)
		case strings.HasPrefix(escapedPath, prefix+"/"):
			mounted.ServeHTTP(w, r)
		default:
			http.NotFound(w, r)
		}
	})
}
