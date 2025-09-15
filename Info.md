## Seguir estos pasos:
- Clonar repo
```bash
git clone -b feature/dockerizar --single-branch git@github.com:bittordani/HipotecAssist.git
cd HipotecAssist
```
- Ejecutar 
```bash
docker compose up -d --build
```

- Editar archivo .env y agrega la API_KEY (La API key se encuentra en discord): 


- Ir a http:localhost:8080 (web)
- Y al back http:localhost:8000 (api)
