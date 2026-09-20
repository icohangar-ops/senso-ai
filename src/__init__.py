"""senso-ai platform sources.

Layout (see README "Project Structure"):

    auth0_fga         -- Auth0 FGA fine-grained authorization package
                         (FGAClient, models, dual-stage retrieval filter)
    retrieval         -- Privacy-aware RAG engine (PrivateRAGEngine)
    airbyte_ingestion -- Airbyte document ingestion + bulk RAG ingestion

The ``auth0_fga`` package uses absolute imports, so put this directory on
``sys.path`` (e.g. ``PYTHONPATH=src``) before importing ``auth0_fga``.
"""
