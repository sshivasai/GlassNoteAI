# GlassNote Website — Docker (Cloud Run)
# Build:  docker build -t glassnote-web .
# Run:    docker run -p 3000:3000 -e NEXT_PUBLIC_API_URL=https://api.glassnoteai.com glassnote-web

# ── Stage 1: Install dependencies ────────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --frozen-lockfile

# ── Stage 2: Build ───────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app

# Copy deps from previous stage
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build-time env vars — baked into the static bundle
ARG NEXT_PUBLIC_API_URL=https://api.glassnoteai.com
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

ARG NEXT_PUBLIC_DOWNLOAD_URL=https://glassnoteai.com/download
ENV NEXT_PUBLIC_DOWNLOAD_URL=$NEXT_PUBLIC_DOWNLOAD_URL

RUN npm run build

# ── Stage 3: Production runtime ──────────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

# Non-root user
RUN addgroup --system --gid 1001 nodejs && \
  adduser --system --uid 1001 nextjs

# Copy standalone output (next.config.ts output: "standalone")
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

RUN chown -R nextjs:nodejs /app
USER nextjs

EXPOSE 3000

# Cloud Run injects PORT env var — Next.js standalone server reads it
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
