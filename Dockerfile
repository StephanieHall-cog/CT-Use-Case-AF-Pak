# AfPak Target Tracker GUI — Fly.io image. Ships the prebuilt demo DB (python3 scripts/build_db.py --synthetic ... --db db/afpak_demo.sqlite); analyst DB lives on the /data volume.
FROM node:22-bookworm-slim
WORKDIR /app
COPY gui/package*.json gui/
RUN cd gui && npm ci --omit=dev
COPY synthetic synthetic
COPY db/afpak_demo.sqlite db/afpak_demo.sqlite
COPY isw/images isw/images
COPY gui gui
ENV PORT=8080 DATA_DIR=/data NODE_ENV=production
EXPOSE 8080
CMD ["node", "gui/server.mjs"]
