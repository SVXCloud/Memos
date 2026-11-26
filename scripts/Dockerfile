FROM --platform=$BUILDPLATFORM golang:1.27.4-bookworm AS backend
WORKDIR /backend-build

# Copy go mod files and download dependencies (cached layer)
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

# Copy source code (use .dockerignore to exclude unnecessary files)
COPY . .

# Please build frontend first, so that the static files are available.
# Refer to `pnpm release` in package.json for the build command.
ARG TARGETOS TARGETARCH VERSION COMMIT=unknown
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    : "${VERSION:?Pass VERSION from scripts/release_version.sh development-version or a release tag}" && \
    CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH \
    go build \
      -trimpath \
      -ldflags="-s -w -X github.com/usememos/memos/internal/version.Version=${VERSION} -X github.com/usememos/memos/internal/version.Commit=${COMMIT} -extldflags '-static'" \
      -tags netgo,osusergo \
      -o memos \
      ./cmd/memos

# Reuse the exact 26.11.2 runtime (Alpine, CA bundle, su-exec and UID 10001).
# The new binary contains the frontend and the fixed HTTP mount.
FROM ghcr.io/usememos/memos:26.11.2@sha256:3c7bd779510403350465ecabb7e6fbc0887206f9d55b8decf51a205613fa5616 AS monolithic
COPY --from=backend /backend-build/memos /usr/local/memos/memos
COPY --chmod=755 scripts/entrypoint.sh /usr/local/memos/entrypoint.sh

HEALTHCHECK --interval=30s --timeout=3s --start-period=30s \
    CMD wget -Y off -q -O /dev/null "http://127.0.0.1:${MEMOS_PORT}/memo/healthz" || exit 1
