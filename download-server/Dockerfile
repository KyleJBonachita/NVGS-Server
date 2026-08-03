FROM node:22-alpine

ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=8080

WORKDIR /app

COPY --chown=node:node package.json config.json server.js ./
COPY --chown=node:node public ./public
RUN mkdir -p /app/downloads && chown node:node /app/downloads

USER node

EXPOSE 8080

CMD ["node", "server.js"]
