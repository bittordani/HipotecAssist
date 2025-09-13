## Seguir estos pasos:
- Clonar solo la rama "feature/dockerizar": 
```bash
git clone -b feature/dockerizar --single-branch git@github.com:bittordani/HipotecAssist.git
cd HipotecAssist
```
- en el directorio raiz (a la misma altura que el Dockerfile)
```bash
docker build -t mi-api .
docker run -p 8000:8000 -e GROQ_API_KEY="agrega-clave-que-os-paso-por-discord-entre-estas-comillas" mi-api
```
- Ir a http:localhost:8000
