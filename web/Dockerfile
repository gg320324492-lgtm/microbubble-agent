# base image pinned on 2026-07-29 for CVE tracking (W86-C-1 Trivy)
FROM node:20.19.6-alpine as builder

WORKDIR /app

# 类 20.133 显式固定输入通道 (web/vite.config.js 读 VITE_BUILD_ID / VITE_BUILD_TIMESTAMP):
# docker 构建上下文没有 .git → `npm run build` 的 git 派生按类 20.133 fail-loud,
# 此处显式提供固定哨兵值让镜像构建完成 (类 20.133 原文允许的"CI 显式固定输入")。
# 哨兵值 **仅存在于镜像内的 dist** —— image-scan 扫描用副本, 不入库、不参与部署
# (生产前端用入库的 web/dist, 恒在完整 git 仓库内构建)。
# 两值必须成对给出 (只给一个时, 缺的那个仍走 git 派生 → 无 .git 环境照旧 fail-loud);
# 可 --build-arg 覆盖; 显式传空 = 未提供 → 回落 git 派生并 fail-loud。
ARG VITE_BUILD_ID=docker-no-git
ARG VITE_BUILD_TIMESTAMP=docker-no-git
ENV VITE_BUILD_ID=${VITE_BUILD_ID} \
    VITE_BUILD_TIMESTAMP=${VITE_BUILD_TIMESTAMP}

COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:1.31.2-alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
