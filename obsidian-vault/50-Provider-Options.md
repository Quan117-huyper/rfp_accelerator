# Provider Options
## LLM Providers

### Gemini API

- Best hosted option for the current proposal workflow.
- Good for extraction, proposal drafting, and clarification questions.

### Local Fallback

- No external API key required.
- Good for offline demoing and quick local testing.

## Storage Options

### Local Disk

- Best fit for the current demo.
- Stores uploaded files and generated PPTX output locally.

### S3 or Similar Object Storage

- Good if the project later needs cloud-hosted file storage.

## Search / Retrieval Options

### FAISS

- Local vector search for quick prototypes.

### Chroma

- Simple vector store for document retrieval.

### Qdrant

- Better suited to larger vector workloads.

### PostgreSQL + pgvector

- Good when structured proposal metadata and embeddings should live together.
