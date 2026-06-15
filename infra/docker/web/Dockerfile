# JimQ web 容器(卡 #10)。build context = web/。
# Node 18(#9 既有相容設定:Vite 5 / LWC v5)build → nginx 靜態伺服 + 反代
# /api、/ws 到 api 服務(對齊 vite dev proxy 的同源契約,前端 fetch('/api/..')、
# new WebSocket('/ws/stream') 不必改)。
FROM node:18-bullseye AS build
WORKDIR /web

# 先 lockfile,最大化 cache。
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# 全棧 demo 用 build:nocheck 避免 vue-tsc 在容器內版本差異卡關(#9 已型別綠;
# CI / 本機跑 npm run build 做型別檢查)。
RUN npm run build:nocheck

FROM nginx:1.27-alpine AS serve
COPY --from=build /web/dist /usr/share/nginx/html
COPY infra-nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
