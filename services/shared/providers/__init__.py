"""PolarisGate Provider Implementations.

Each provider implements one or more interface contracts from
``services/shared/interfaces/``.

Providers:
    - LocalSafetyProvider  — on-prem safety (BERT, regex, NLI)
    - LocalAuthProvider    — on-prem auth (JWT + bcrypt)
    - LocalInfraProvider   — on-prem infra (Docker Compose / K8s)
    
    (Cloud providers added later):
    - AWSSafetyProvider    — AWS Comprehend + Bedrock
    - AzureSafetyProvider  — Azure AI Content Safety + AI Language
    - GCPSafetyProvider    — GCP Cloud DLP + Vertex AI
"""