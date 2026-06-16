# JimQ web 容器(卡 #10;改版 S0 升 Node 20 + pnpm,Tailwind v4 需 Node 20+)。
# build context = web/。Vite 5 / LWC v5 build → nginx 靜態伺服 + 反代 /api、/ws
# 到 api 服務(同源契約,前端 fetch('/api/..')、new WebSocket('/ws/stream') 不必改)。
FROM node:20-bookworm AS build
WORKDIR /web

RUN corepack disable >/dev/null 2>&1 || true; npm install -g pnpm@9 >/dev/null 2>&1

# 先 lockfile,最大化 cache。
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
# 全棧 demo 用 build:nocheck 避免 vue-tsc 在容器內版本差異卡關(#9 已型別綠;
# CI / 本機跑 pnpm run build 做型別檢查)。
RUN pnpm run build:nocheck

FROM nginx:1.27-alpine AS serve
COPY --from=build /web/dist /usr/share/nginx/html
COPY infra-nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
