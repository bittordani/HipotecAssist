# Imagen base Nginx
FROM nginx:alpine

# Copiar archivos estáticos
COPY web /usr/share/nginx/html
COPY ./nginx.conf /etc/nginx/nginx.conf

# Exponer puerto web
EXPOSE 80

# Nginx ya arranca por defecto