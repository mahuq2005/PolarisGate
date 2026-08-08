#!/usr/bin/env python3
"""Web crawler to gather latest competitive intelligence from AI safety vendors."""
import re
import json
import sys
from typing import Optional, Dict, List
from urllib.request import Request, urlopen
from urllib.error import URLError

USER_AGENT = "Mozilla/5.0 (compatible; PolarisGateResearch/1.0)"

COMPETITORS = {
    "guardrails_ai": {
        "name": "Guardrails AI",
        "urls": [
            "https://guardrailsai.com",
            "https://docs.guardrailsai.com",
        ],
    },
    "lakera": {
        "name": "Lakera Guard",
        "urls": [
            "https://www.lakera.ai",
            "https://www.lakera.ai/pricing",
        ],
    },
    "llm_guard": {
        "name": "LLM Guard",
        "urls": [
            "https://llm-guard.com",
        ],
    },
    "langfuse": {
        "name": "Langfuse",
        "urls": [
            "https://langfuse.com",
            "https://langfuse.com/pricing",
        ],
    },
    "azure_content_safety": {
        "name": "Azure AI Content Safety",
        "urls": [
            "https://azure.microsoft.com/en-us/products/ai-services/ai-content-safety",
        ],
    },
    "nvidia_nemo": {
        "name": "NVIDIA NeMo Guardrails",
        "urls": [
            "https://developer.nvidia.com/nemo-guardrails",
        ],
    },
    "credo_ai": {
        "name": "Credo AI",
        "urls": [
            "https://www.credo.ai",
        ],
    },
}

KEYWORDS = [
    "pricing", "enterprise", "deploy", "self-hosted", "cloud",
    "open source", "oss", "api", "sdk", "library",
    "toxicity", "pii", "injection", "guardrail", "safety",
    "hallucination", "budget", "cost", "token",
    "bedrock", "comprehend", "aws", "azure", "gcp",
    "on-prem", "air-gap", "airgap", "offline",
    "docker", "kubernetes", "helm",
    "free", "trial", "demo", "starter",
]


def clean_html(html: str) -> str:
    """Remove CSS, JS, and HTML tags to extract readable text."""
    # Remove style blocks
    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove script blocks
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_url(url: str) -> Optional[str]:
    """Fetch URL content with timeout and error handling."""
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except URLError as e:
        print(f"  ⚠ Failed: {e.reason}", file=sys.stderr)
        return None


def extract_findings(text: str) -> List[str]:
    """Extract sentences containing competitive intelligence keywords."""
    findings = []
    sentences = text.split(".")
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 20:
            continue
        lower = sentence.lower()
        for kw in KEYWORDS:
            if kw in lower:
                findings.append(sentence[:300])
                break
    return findings


def crawl_competitor(comp_id: str, comp_data: Dict) -> Dict:
    """Crawl all URLs for a competitor and extract findings."""
    print(f"\n{'='*60}")
    print(f"🔍 Crawling: {comp_data['name']}")
    print(f"{'='*60}")

    all_findings = []
    urls_tried = 0
    urls_failed = 0

    for url in comp_data["urls"]:
        print(f"  📡 {url}")
        html = fetch_url(url)
        if html is None:
            urls_failed += 1
            continue
        urls_tried += 1

        text = clean_html(html)
        findings = extract_findings(text)
        all_findings.extend(findings)
        print(f"     → {len(findings)} relevant sentences found ({len(text)} chars extracted)")

    # Deduplicate
    unique = list(dict.fromkeys(all_findings))

    return {
        "name": comp_data["name"],
        "urls_tried": urls_tried,
        "urls_failed": urls_failed,
        "relevant_sentences": len(unique),
        "findings": unique[:50],  # Limit to top 50
    }


def main():
    print("=" * 60)
    print("🔬 PolarisGate Competitive Intelligence Crawler")
    print("=" * 60)

    results = {}
    for comp_id, comp_data in COMPETITORS.items():
        try:
            results[comp_id] = crawl_competitor(comp_id, comp_data)
        except Exception as e:
            print(f"  ❌ Error: {e}", file=sys.stderr)
            results[comp_id] = {
                "name": comp_data["name"],
                "error": str(e),
            }

    # Summary
    print(f"\n{'='*60}")
    print("📊 CRAWL SUMMARY")
    print(f"{'='*60}")
    for comp_id, result in results.items():
        name = result.get("name", comp_id)
        if "error" in result:
            print(f"  ❌ {name}: {result['error']}")
        else:
            print(f"  ✅ {name}: {result['relevant_sentences']} findings from {result['urls_tried']} pages")

    # Save results
    output_path = "reports/competitor_crawl_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n📁 Full results saved to: {output_path}")


if __name__ == "__main__":
    main()