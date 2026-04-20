FROM node:20-alpine

WORKDIR /src

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# At runtime we copy build output into a shared volume mounted at /dist.
CMD ["sh", "-c", "rm -rf /dist/* && cp -r /src/dist/* /dist/ && printf \"window.__METACAM_ENV__ = window.__METACAM_ENV__ || {};\\nwindow.__METACAM_ENV__.API_URL = '%s';\\n\" \"${METACAM_API_URL:-}\" > /dist/env.js && echo \"frontend: assets copied; METACAM_API_URL='${METACAM_API_URL:-}'\" && sleep infinity"]
