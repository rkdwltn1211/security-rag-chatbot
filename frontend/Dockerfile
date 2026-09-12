FROM node:20-alpine

WORKDIR /app

COPY package*.json .
RUN npm ci

COPY . .

ARG VITE_API_URL
ARG BUILD_MODE=production
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build -- --mode "$BUILD_MODE"

FROM nginx:alpine
COPY --from=0 /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
