> ✨ Featured sponsor: [CodeRabbit — Industry-leading AI code reviews](https://coderabbit.link/usememos).

<h1 id="memos">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/usememos/.github/refs/heads/main/assets/brand/lockup-on-dark.svg" />
    <img src="https://raw.githubusercontent.com/usememos/.github/refs/heads/main/assets/brand/lockup.svg" alt="Memos" width="220" />
  </picture>
</h1>

### Simple note-taking for your everyday thoughts.

Memos is an open-source, self-hosted note-taking app that brings your everyday thoughts together in a personal timeline. Your data stays yours, and you choose what to keep private or share.

[Demo](https://demo.usememos.com) · [Install](#quick-start) · [Docs](https://usememos.com/docs) · [Discord](https://discord.gg/tfPJa4UmAv)

[![Docker pulls](https://img.shields.io/docker/pulls/neosmemo/memos?style=flat-square&logo=docker)](https://hub.docker.com/r/neosmemo/memos)
[![Latest release](https://img.shields.io/github/v/release/usememos/memos?style=flat-square&label=Release)](https://github.com/usememos/memos/releases)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/usememos/.github/refs/heads/main/assets/previews/timeline-dark.png" />
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/usememos/.github/refs/heads/main/assets/previews/timeline-light.png" />
  <img src="https://raw.githubusercontent.com/usememos/.github/refs/heads/main/assets/previews/timeline-light.png" alt="The Memos timeline with a memo composer and recent memos" />
</picture>

## About Memos

Memos is an open-source, self-hosted note-taking app for your everyday thoughts.

- **Everyday writing.** A single sentence can be a whole memo, or you can take your time with a longer entry, using Markdown to give your words more structure.
- **A personal timeline.** Each memo stays with the day you wrote it, bringing your thoughts together in a timeline you can look back through. Tags connect related thoughts across those days, making it easy to pick up a topic again or find something you remember writing.
- **Your own data.** Your record lives on your own server, and your data stays yours.
- **Sharing you control.** You choose what stays private, what to share with family and friends, and what to publish on the web. In shared spaces, you can write alongside others while each person keeps their own memos.

## Quick start

此 Fork 基于 Memos 26.11.2，应用固定挂载在 `/memo`。镜像包含前端和后端，支持 Linux AMD64 与 ARM64。

### Docker Run

```bash
docker run -d --name memos --restart unless-stopped \
  -p 127.0.0.1:5230:5230 \
  -v memos-data:/var/opt/memos \
  ghcr.io/svxcloud/memos:26.11.2-notes
```

本机打开 `http://localhost:5230/memo/`，首次启动时创建管理员。镜像使用 `/memo/healthz` 检查应用和数据库是否就绪。

### Docker Compose

```yaml
services:
  memos:
    image: ghcr.io/svxcloud/memos:26.11.2-notes
    restart: unless-stopped
    ports:
      - "127.0.0.1:5230:5230"
    volumes:
      - memos-data:/var/opt/memos
    environment:
      MEMOS_INSTANCE_URL: https://notes.example.com/memo

volumes:
  memos-data:
```

执行 `docker compose up -d`。示例使用 SQLite。使用 PostgreSQL 或 MySQL 时，保留数据卷及原有的 `MEMOS_DRIVER` 和 `MEMOS_DSN`，通过容器共享网络或专用数据库地址连接。生产环境从秘密管理系统提供数据库凭据。

`MEMOS_INSTANCE_URL` 是可选的公网地址，用于邮件、站点地图和分享链接。首次启动时，它也参与上游公开访问模式的初始化。已有实例应保留其访问设置，并将该地址更新为实际 HTTPS 入口。

### Nginx

将以下配置置于已配置 HTTPS 的站点中。保留 `proxy_pass` 地址后没有 URI 路径的写法。

```nginx
location = /memo {
    return 308 /memo/$is_args$args;
}

location ^~ /memo/ {
    proxy_pass http://127.0.0.1:5230;
    proxy_http_version 1.1;
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_buffering off;
    proxy_request_buffering off;
    proxy_read_timeout 1h;
    client_max_body_size 10m;
}
```

### Caddy

```caddyfile
notes.example.com {
    @memos path /memo /memo/*
    reverse_proxy @memos 127.0.0.1:5230
}
```

反向代理应把原请求路径转发给 Memos。代理、数据库和 Memos 在同一个 Compose 网络中时，将示例中的上游地址替换为 `memos:5230`。启用服务器的受信代理配置时，仅信任实际代理的地址。

| 接口 | 外部地址 |
| --- | --- |
| REST | `https://notes.example.com/memo/api/...` |
| Connect RPC | `https://notes.example.com/memo/memos.api.<Service>/<Method>` |
| SSE | `https://notes.example.com/memo/api/sse` |
| MCP | `https://notes.example.com/memo/mcp` |
| 健康检查 | `https://notes.example.com/memo/healthz` |

### Logto OAuth2 / OIDC

1. 在 Logto 中创建 **Traditional Web App** 应用，将 **Redirect URI** 设为 `https://notes.example.com/memo/auth/callback`。地址须与 Memos 页面所用的协议、域名、端口和路径完全一致。
2. 在 Memos 的实例设置中添加 OAuth2 身份提供商。填写 Logto App ID 和 App Secret。使用 Logto OIDC 发现文档中公布的端点，通常是 `https://<logto-domain>/oidc/auth`、`/oidc/token` 和 `/oidc/me`。
3. 将 Identifier 映射为 `sub`。使用 `openid profile` 范围，按需将昵称和头像映射为 `name`、`picture`。需要邮箱时加上 `email` 范围和字段映射。
4. 用 HTTPS 完成首次登录，或由已登录用户绑定其身份。按照实例访问策略开放新用户注册，已有账号建议先绑定现有身份。

## 从原版 Memos 迁移

1. 停止旧容器，备份 `/var/opt/memos` 及配置。使用 PostgreSQL 或 MySQL 时，同时备份外部数据库。使用 S3 时，保留存储端点、桶及原有对象和凭据。
2. 指向旧实例使用的同一数据卷和数据库，将镜像换为 `ghcr.io/svxcloud/memos:26.11.2-notes`，并部署上述反向代理配置。启动时 Memos 会执行上游数据库迁移。低于 v0.31.0 的版本需先启动 [v0.31.0](https://github.com/usememos/memos/releases/tag/v0.31.0)。迁移完成后如需回滚，使用迁移前的备份。参见 [上游迁移文档](store/migration/README.md)。
3. 访问 `/memo/healthz`，验证原笔记、附件及账号，然后更新客户端地址、Logto 回调和外部链接。清除旧站点的根路径 Cookie 并重新登录。
4. 已存笔记中相对旧根路径的内部笔记链接和受管理附件会按新路径加载。需要保留外部书签中的旧链接时，在代理中为已确认属于旧 Memos 的页面和附件路径配置重定向，并保留查询参数。已有 PWA 可重新安装以更新作用域。

## 已知限制

- 应用固定使用 `/memo`。旧版客户端需要能配置包含该前缀的服务器地址。
- 手工写入的旧绝对 URL 仍按原地址访问。可用反向代理重定向旧地址，或更新这些链接。S3 和其他外部地址按原值使用。
- Logto 使用上游的 OAuth2 授权码和 UserInfo 集成，需要显式填端点。应用继承上游的 PWA 能力，前缀内的 manifest 不增加离线功能。

## 构建与发布

在 GitHub Actions 中手动运行 **Publish Memos /memo image**，或推送 `26.11.2-notes` 版本标签。工作流在原生 AMD64 和 ARM64 runner 构建镜像，验证前后端与实际容器，再用 `GITHUB_TOKEN` 发布同一批通过验证的镜像。版本标签为 `26.11.2-notes`，`latest` 指向最近发布的已验证版本。GHCR 包首次创建后，包管理员可以将其设为公开，以便匿名拉取。

## Around Memos

- [Web Clipper](https://usememos.com/web-clipper) for [Chrome](https://chromewebstore.google.com/detail/memos-web-clipper/nebaoebnljalfegiidibihhkebeiklbl) and [Firefox](https://addons.mozilla.org/en-US/firefox/addon/memos-web-clipper/) saves pages, selections, and images to your memos as Markdown with a link to the source.
- [Memogram](https://github.com/usememos/telegram-integration) is a Telegram bot that saves your messages and images to Memos.
- The [API](https://usememos.com/docs/api/latest) and [MCP server](https://usememos.com/docs/integrations/mcp) connect Memos to your own scripts and AI tools.

## Sponsors

<p>
  <a href="https://coderabbit.link/usememos" target="_blank" rel="noopener"><picture><source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/usememos/.github/refs/heads/main/assets/sponsors/coderabbit/white-typemark.svg" /><img src="https://raw.githubusercontent.com/usememos/.github/refs/heads/main/assets/sponsors/coderabbit/orange-typemark.svg" alt="CodeRabbit" height="40" align="middle" /></picture></a>
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://www.testmuai.com/?utm_medium=sponsor&utm_source=memos" target="_blank" rel="noopener"><picture><source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/usememos/.github/refs/heads/main/assets/sponsors/testmuai/white.png" /><img src="https://raw.githubusercontent.com/usememos/.github/refs/heads/main/assets/sponsors/testmuai/black.png" alt="TestMu AI" height="30" align="middle" /></picture></a>
</p>

Sponsor Memos through [GitHub Sponsors](https://github.com/sponsors/usememos).

## Help and contributing

Questions go to the [docs](https://usememos.com/docs), [Discord](https://discord.gg/tfPJa4UmAv), or [GitHub Discussions](https://github.com/usememos/memos/discussions). Bugs and ideas go to [issues](https://github.com/usememos/memos/issues/new/choose). Code changes start with the [contributing guide](https://usememos.com/docs/development/contributing).

## Star History

<p>
  <a href="https://www.star-history.com/usememos/memos"><picture><source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/badge?repo=usememos/memos&type=rank&theme=dark" /><source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/badge?repo=usememos/memos&type=rank" /><img alt="Star History Rank" src="https://api.star-history.com/badge?repo=usememos/memos&type=rank" /></picture></a>
  <a href="https://www.star-history.com/usememos/memos"><picture><source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/badge?repo=usememos/memos&type=trending&theme=dark" /><source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/badge?repo=usememos/memos&type=trending" /><img alt="GitHub Trending Repository of the Day" src="https://api.star-history.com/badge?repo=usememos/memos&type=trending" /></picture></a>
</p>

## License

Memos is open source under the [MIT License](LICENSE).
