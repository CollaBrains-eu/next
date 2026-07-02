FROM node:22-slim
WORKDIR /app
RUN corepack enable
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --frozen-lockfile --filter web...
COPY apps/web/ apps/web/
WORKDIR /app/apps/web
EXPOSE 5173
CMD ["pnpm", "dev"]
