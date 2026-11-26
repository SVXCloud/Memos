package deployment

import (
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestMount(t *testing.T) {
	handler := Mount(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.WriteString(w, r.Method+" "+r.URL.RequestURI())
	}))
	for _, path := range []string{"/", "/healthz", "/memo-no/healthz", "/memo%2Fhealthz", "/%6demo/healthz"} {
		response := httptest.NewRecorder()
		handler.ServeHTTP(response, httptest.NewRequest(http.MethodGet, path, nil))
		require.Equal(t, http.StatusNotFound, response.Code, path)
	}

	redirect := httptest.NewRecorder()
	handler.ServeHTTP(redirect, httptest.NewRequest(http.MethodPost, "/memo?a=%2B", nil))
	require.Equal(t, http.StatusPermanentRedirect, redirect.Code)
	require.Equal(t, "/memo/?a=%2B", redirect.Header().Get("Location"))

	response := httptest.NewRecorder()
	handler.ServeHTTP(response, httptest.NewRequest(http.MethodPost, "/memo/file/a%2Fb?q=c", nil))
	require.Equal(t, http.StatusOK, response.Code)
	require.Equal(t, "POST /file/a%2Fb?q=c", response.Body.String())
}
