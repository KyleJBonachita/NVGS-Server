FROM node:22-alpine

ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=3000 \
    GERY_DATA_DIR=/app/data

WORKDIR /app

COPY --chown=node:node backend/package.json backend/package-lock.json ./backend/
RUN cd backend && npm ci --omit=dev

COPY --chown=node:node backend/src ./backend/src
COPY --chown=node:node frontend ./frontend
COPY --chown=node:node knowledge ./knowledge
RUN mkdir -p /app/data/uploads && chown -R node:node /app/data

USER node
WORKDIR /app/backend

EXPOSE 3000

CMD ["node", "src/server.js"]
