from qdrant_client import QdrantClient

client = QdrantClient(
    url="https://fb7ee88b-c1ea-42dd-be16-86b580350e01.europe-west3-0.gcp.cloud.qdrant.io",
    api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.7ER9HmetE3-Yvdd_B5W1jHWBd--nDPEpjHcRX4AxZas"
)

print(client.get_collections())
