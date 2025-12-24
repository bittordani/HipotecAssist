# Imagen base Nginx
FROM nginx:alpine

RUN chmod -R 755 /usr/share/nginx/html

# Copiar archivos estáticos
COPY web /usr/share/nginx/html
# COPY ./nginx.conf /etc/nginx/nginx.conf

# Exponer puerto web
EXPOSE 80

# Nginx ya arranca por defecto