## Seguir estos pasos:
- Clonar repo
```bash
git clone -b feature/front-back-dockercompose --single-branch git@github.com:bittordani/HipotecAssist.git
cd HipotecAssist
```
- Ejecutar 
```bash
docker compose up -d --build
```

- Acceder al contenedor y pegar API_KEY (La API key se encuentra en discord): 
```bash
docker exec -it hipotecas_backend /bin/bash
```
```bash
export GROQ_API_KEY="tu_clave_aqui"
```
- Ir a http:localhost:8080
- Y al back http:localhost:8000
