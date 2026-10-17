FROM node:20-slim AS build
WORKDIR /app
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
# vite.config.ts's dev-server proxy (relative "/predict") does not exist
# in this production static build -- VITE_API_BASE_URL is baked in here
# at build time (Vite inlines import.meta.env.* at build, it cannot be
# changed at container-run time) so the browser calls the backend's own
# published URL instead. Confirmed via a real docker-compose run (Month 2
# engineering pipeline) that omitting this makes /predict silently return
# the frontend's own index.html instead of a real backend response.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM node:20-slim
WORKDIR /app
RUN npm install -g serve
COPY --from=build /app/dist ./dist
EXPOSE 5173
CMD ["serve", "-s", "dist", "-l", "5173"]
