# Xpense Tracking App (XTA)
**Secure, Self-Hosted Financial Data Pipeline**

## Architecture Blueprint

<div class="mermaid">
graph TD
    %% Define Styles
    classDef live stroke:#22c55e,stroke-width:2px,fill:#f0fdf4,color:#166534;
    classDef future stroke:#94a3b8,stroke-width:2px,stroke-dasharray: 5 5,fill:#f8fafc,color:#64748b;
    classDef external stroke:#3b82f6,stroke-width:2px,fill:#eff6ff,color:#1e3a8a;

    %% Nodes
    User((User / Mobile)):::external
    CF[Cloudflare Access<br>OTP / Zero Trust]:::live
    GH[GitHub Actions CI/CD<br>Build & Publish]:::external
    
    subgraph Synology NAS / Portainer
        Web[XTA Web Container<br>FastAPI / HTMX / Pandas]:::live
        DB[(PostgreSQL 16<br>xta_prod_data)]:::live
        LocalLLM[Local LLM Container<br>Ollama / Llama3]:::future
    end

    OpenAI[OpenAI API<br>gpt-4o & Vision]:::external
    Forex[Multi-Currency API]:::future

    %% Connections
    User -->|HTTPS| CF
    CF -->|Traffic routed to 8080| Web
    GH -->|GitOps Webhook| Synology NAS / Portainer
    
    Web <-->|SQLAlchemy| DB
    Web <-->|REST API| OpenAI
    
    %% Future Connections
    Web -.->|Local Inference| LocalLLM
    Web -.->|Forex Rates| Forex
    
    %% Styling note
    classDef default font-family:sans-serif;
</div>

<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<script>
    mermaid.initialize({ startOnLoad: true });
</script>

## Release Timeline

| Date | Feature | Status |
| :--- | :--- | :--- |
| **March 1, 2026** | **Native Camera Support** | **Done** |
| | **Entity Normalization** | **Done** |
| | **Cloudflare Identity Tagging** | **Done** |
| | **CSV & Excel Bank Statements** | **Done** |
| | Multi-Currency Engine | Planned |
| | Infinite Scroll / Pagination | Planned |
| | **Use local LLM** | **Next Priority** |
| **April 1, 2026** | PDF Handling (The Fork) | Planned |
| | The Bulk-Upload Queue | Planned |
| | AI Data Analyst | Planned |
| | Geospatial Visualization | Planned |
| | Data Export / Tax Readiness | Planned |
| | Itemization per receipt | Planned |
| | Hardening, Encrypt data, Scan for Crypto | Planned |
| | Scan Containers, Generate SBOMs, Generate CBOMs | Planned |