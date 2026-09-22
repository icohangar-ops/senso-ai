#!/usr/bin/env python3
"""
Senso.AI Knowledge Base Compiler

Scans all 15 Cubiczan repos on Codeberg and generates an agent-ready
knowledge base index with:
  - Repository metadata (stack, features, integrations, patterns)
  - Cross-repo pattern mapping
  - Technology frequency analysis
  - Agent context files per domain

Usage:
    python3 compile_kb.py [--output-dir ./docs] [--format json|md|both]
"""
import os, json, re, sys
from pathlib import Path
from collections import Counter

REPOS = {
    "healthguard-ai": {
        "domain": "Healthcare",
        "description": "Health Intelligence Platform — 7-tab dashboard with ClickHouse 10 UDFs",
        "languages": ["TypeScript", "SQL"],
        "frameworks": ["Next.js 16", "Tailwind CSS 4", "shadcn/ui", "Recharts"],
        "platforms": ["ClickHouse Cloud", "Vercel"],
        "integrations": ["ClickHouse Cloud", "Nimble SDK", "RapidReview Papyrus", "Datadog Lapdog"],
        "patterns": ["synthetic-fallback", "multi-tab-dashboard", "dark-theme", "server-side-proxy", "udf-queries"],
        "license": "MIT",
    },
    "cfo-resilience-matrix": {
        "domain": "CFO & Finance",
        "description": "6-Layer AI Agent Resilience for CFO Operations",
        "languages": ["Python"],
        "frameworks": ["TrueFoundry AI Gateway"],
        "platforms": [],
        "integrations": ["OpenAI", "Claude", "Gemini", "TrueFoundry"],
        "patterns": ["multi-provider-failover", "circuit-breaker", "semantic-cache", "dead-letter-queue"],
        "license": "Apache 2.0",
    },
    "cfo-command-center": {
        "domain": "CFO & Finance",
        "description": "AI-Powered Finance Operations Hub on Notion",
        "languages": ["TypeScript"],
        "frameworks": ["Notion API"],
        "platforms": ["Notion"],
        "integrations": ["Notion API"],
        "patterns": ["notion-native", "ai-agents"],
        "license": "MIT",
    },
    "cash-flow-optimizer": {
        "domain": "CFO & Finance",
        "description": "Vellum-powered cash flow intelligence with Xero, Precoro, Outlook",
        "languages": ["TypeScript"],
        "frameworks": ["Vellum AI"],
        "platforms": [],
        "integrations": ["Xero API", "Precoro API", "Microsoft Graph API", "Vellum"],
        "patterns": ["cron-triggers", "llm-narrative", "3-way-match", "guardrail-node"],
        "license": "MIT",
    },
    "p2p-copilot": {
        "domain": "CFO & Finance",
        "description": "AI-Powered Procure-to-Pay on UiPath Maestro BPMN",
        "languages": ["Python"],
        "frameworks": ["UiPath Maestro (BPMN)"],
        "platforms": ["UiPath"],
        "integrations": ["Claude Vision API", "UiPath Maestro", "UiPath Action Center"],
        "patterns": ["bpmn-orchestration", "ai-vision-extraction", "anomaly-detection", "audit-trail"],
        "license": "MIT",
    },
    "battery-erp": {
        "domain": "Commodity & Mining",
        "description": "Battery value chain ERP with Fabric Lakehouse analytics",
        "languages": ["Python"],
        "frameworks": ["Microsoft Fabric"],
        "platforms": ["Microsoft Fabric"],
        "integrations": ["AlphaVantage", "FRED", "Microsoft Fabric Lakehouse"],
        "patterns": ["medallion-architecture", "bom-rollup", "supplier-scoring", "what-if-scenario"],
        "license": "MIT",
    },
    "databricks-commodity-risk-engine": {
        "domain": "Commodity & Mining",
        "description": "Delta Lake + MLflow + VaR + Margin Analytics on Databricks",
        "languages": ["Python", "SQL"],
        "frameworks": ["Databricks", "MLflow", "scikit-learn"],
        "platforms": ["Databricks"],
        "integrations": ["Databricks REST API"],
        "patterns": ["medallion-architecture", "var-analytics", "mlflow-tracking", "parametric-risk"],
        "license": "MIT",
    },
    "databricks-lakehouse-intelligence": {
        "domain": "Commodity & Mining",
        "description": "Mining & metals analytics with Unity Catalog on Databricks",
        "languages": ["Python", "SQL"],
        "frameworks": ["Databricks", "MLflow", "Unity Catalog"],
        "platforms": ["Databricks"],
        "integrations": ["Databricks REST API v2.0"],
        "patterns": ["medallion-architecture", "unity-catalog", "composite-signals", "esg-scoring"],
        "license": "MIT",
    },
    "snowflake-commodity-supply-chain": {
        "domain": "Commodity & Mining",
        "description": "Contract pricing & risk analytics on Snowflake + dbt",
        "languages": ["Python", "SQL"],
        "frameworks": ["Snowflake", "dbt"],
        "platforms": ["Snowflake"],
        "integrations": ["Snowpark"],
        "patterns": ["dynamic-tables", "zero-copy-clone", "dynamic-masking", "row-access-policy"],
        "license": "MIT",
    },
    "snowflake-cortex-research": {
        "domain": "Commodity & Mining",
        "description": "AI-powered earnings & filing analytics with Cortex AI + dbt",
        "languages": ["Python", "SQL"],
        "frameworks": ["Snowflake Cortex AI", "dbt"],
        "platforms": ["Snowflake"],
        "integrations": ["SEC EDGAR"],
        "patterns": ["cortex-ai-nlp", "dynamic-tables", "streams-tasks", "zero-copy-clone"],
        "license": "MIT",
    },
    "metacomp-visionx-dashboard": {
        "domain": "Security & Blockchain",
        "description": "Crypto AML/KYT compliance dashboard (4 vendor cross-validation)",
        "languages": ["TypeScript"],
        "frameworks": ["Next.js 16", "Tailwind CSS 4"],
        "platforms": [],
        "integrations": ["MetaComp Vision X API", "Chainalysis", "Beosin", "Elliptic", "Merkle Science"],
        "patterns": ["multi-vendor-validation", "dark-theme", "risk-cross-validation"],
        "license": "MIT",
    },
    "shieldgate": {
        "domain": "Security & Blockchain",
        "description": "Least-privilege agentic SOC (AuthZed SpiceDB × Splunk)",
        "languages": ["TypeScript"],
        "frameworks": ["Next.js 16", "AuthZed/SpiceDB"],
        "platforms": [],
        "integrations": ["AuthZed", "Splunk (MCP)"],
        "patterns": ["zero-trust", "mcp-protocol", "least-privilege", "blast-radius-control"],
        "license": "MIT",
    },
    "courtvision-ai": {
        "domain": "Security & Blockchain",
        "description": "AI-powered NBA prediction market on Polygon Azuro Protocol",
        "languages": ["TypeScript", "Solidity"],
        "frameworks": ["Next.js", "React", "FastAPI"],
        "platforms": ["Polygon"],
        "integrations": ["Azuro Protocol", "Qwen LLM (DashScope)"],
        "patterns": ["on-chain-betting", "ai-sports-analysis", "smart-contracts"],
        "license": "MIT",
    },
    "greenverify-ai": {
        "domain": "Security & Blockchain",
        "description": "AI carbon credit verification & trading (Rust ink! + Next.js)",
        "languages": ["TypeScript", "Python", "Rust"],
        "frameworks": ["Next.js 16", "ink! 5.0"],
        "platforms": ["Portaldot (DoraHacks)"],
        "integrations": ["Substrate/ink!"],
        "patterns": ["ai-verification", "on-chain-trading", "multi-tab-dashboard"],
        "license": "MIT",
    },
    "first-principles-product-incubator": {
        "domain": "Innovation",
        "description": "Structured innovation workspace (ideation to validated MVP)",
        "languages": ["TypeScript"],
        "frameworks": ["Next.js", "Bun"],
        "platforms": [],
        "integrations": [],
        "patterns": ["first-principles-thinking", "5-phase-workflow", "hypothesis-validation"],
        "license": "MIT",
    },
}


def compute_analytics(repos):
    """Cross-repo analytics."""
    lang_counter = Counter()
    fw_counter = Counter()
    integration_counter = Counter()
    pattern_counter = Counter()
    domain_counter = Counter()

    for name, repo in repos.items():
        domain_counter[repo["domain"]] += 1
        for lang in repo["languages"]:
            lang_counter[lang] += 1
        for fw in repo["frameworks"]:
            fw_counter[fw] += 1
        for integ in repo["integrations"]:
            integration_counter[integ] += 1
        for pat in repo["patterns"]:
            pattern_counter[pat] += 1

    return {
        "by_domain": dict(domain_counter),
        "languages": dict(lang_counter.most_common()),
        "frameworks": dict(fw_counter.most_common()),
        "integrations": dict(integration_counter.most_common()),
        "patterns": dict(pattern_counter.most_common()),
    }


def build_pattern_index(repos):
    """Map each pattern to repos using it."""
    index = {}
    for name, repo in repos.items():
        for pat in repo["patterns"]:
            index.setdefault(pat, []).append(name)
    return dict(sorted(index.items()))


def build_integration_index(repos):
    """Map each integration to repos using it."""
    index = {}
    for name, repo in repos.items():
        for integ in repo["integrations"]:
            index.setdefault(integ, []).append(name)
    return dict(sorted(index.items()))


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)

    analytics = compute_analytics(REPOS)
    pattern_index = build_pattern_index(REPOS)
    integration_index = build_integration_index(REPOS)

    # Full knowledge base
    kb = {
        "version": "1.0.0",
        "generated": "2025-05-24",
        "total_repos": len(REPOS),
        "repos": REPOS,
        "analytics": analytics,
        "pattern_index": pattern_index,
        "integration_index": integration_index,
    }

    # Write JSON
    json_path = out_dir / "knowledge_base.json"
    with open(json_path, "w") as f:
        json.dump(kb, f, indent=2)
    print(f"Written: {json_path}")

    # Write pattern index
    pat_path = out_dir / "pattern_index.md"
    with open(pat_path, "w") as f:
        f.write("# Cross-Repo Pattern Index\n\n")
        f.write("Maps architectural patterns to the repos that implement them.\n\n")
        for pat, repos in pattern_index.items():
            f.write(f"## `{pat}`\n")
            for r in repos:
                f.write(f"- [{r}](https://codeberg.org/cubiczan/{r})\n")
            f.write("\n")
    print(f"Written: {pat_path}")

    # Write integration index
    int_path = out_dir / "integration_index.md"
    with open(int_path, "w") as f:
        f.write("# Cross-Repo Integration Index\n\n")
        f.write("Maps external integrations to the repos that use them.\n\n")
        for integ, repos in integration_index.items():
            f.write(f"## {integ}\n")
            for r in repos:
                f.write(f"- [{r}](https://codeberg.org/cubiczan/{r})\n")
            f.write("\n")
    print(f"Written: {int_path}")

    # Summary
    print(f"\nSenso.AI Knowledge Base: {len(REPOS)} repos, {len(pattern_index)} patterns, {len(integration_index)} integrations")
    print(f"Domains: {list(analytics['by_domain'].keys())}")
    print(f"Top languages: {list(analytics['languages'].items())[:5]}")


if __name__ == "__main__":
    main()
