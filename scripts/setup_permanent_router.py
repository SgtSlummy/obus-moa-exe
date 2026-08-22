#!/usr/bin/env python3
"""
OBus Permanent Configuration Setup

Sets up Occult Router as the default provider-routing policy for:
- Local Hermes agents
- Standalone Codex
- Any OpenAI-compatible client

This script should be run once to establish the permanent MOA routing configuration.
"""
import os
import sys
import json
import shutil
from pathlib import Path

def setup_occult_router():
    """Set up permanent Occult Router configuration."""
    
    # Configuration paths
    hermes_home = Path.home() / '.hermes'
    config_dir = hermes_home / 'config'
    plugins_dir = hermes_home / 'plugins'
    
    # Create directories
    config_dir.mkdir(parents=True, exist_ok=True)
    plugins_dir.mkdir(parents=True, exist_ok=True)
    
    # Create router configuration
    router_config = {
        "default_router": "occultbus",
        "routing_mode": "tarot-router",
        "agency": "local",
        "identity_rule": "Tarot cards are agent personas. Solomon's Keys are LLM/provider handles. RAG selects pairings per task; no static card/key pairing exists.",
        "auto_approve": True,
        "verified_keys": [
            "key-codex-oauth",
            "key-local-ollama", 
            "key-nous-oauth",
            "key-nvidia-nim"
        ],
        "max_parallel_specialists": 20,
        "cooldown_behavior": "skip_and_retry_later",
        "aggregator": "key-codex-oauth",
        "fallback_chain": ["key-local-ollama", "key-nous-oauth"]
    }
    
    # Write router config
    router_config_path = config_dir / 'occult_router.json'
    with open(router_config_path, 'w') as f:
        json.dump(router_config, f, indent=2)
    
    # Create provider routing config
    provider_routing = {
        "providers": {
            "openai-codex": {
                "priority": 1,
                "use_for": ["aggregation", "synthesis"],
                "fallback": "local-ollama"
            },
            "nvidia": {
                "priority": 2,
                "use_for": ["reasoning", "research", "coding"]
            },
            "nous": {
                "priority": 3,
                "use_for": ["creative", "planning", "general"]
            },
            "local-ollama": {
                "priority": 4,
                "use_for": ["routing", "scouting", "retrieval"],
                "always_available": True
            }
        },
        "routing_policies": {
            "default": "tarot-router",
            "creative_tasks": "nous-first",
            "technical_tasks": "nvidia-first",
            "analysis_tasks": "nvidia-nous",
            "aggregation_tasks": "codex-only"
        }
    }
    
    provider_routing_path = config_dir / 'provider_routing.json'
    with open(provider_routing_path, 'w') as f:
        json.dump(provider_routing, f, indent=2)
    
    print("✓ Created router configuration:")
    print(f"  - {router_config_path}")
    print(f"  - {provider_routing_path}")
    
    # Set environment variable
    os.environ['OCCULTBUS_HOME'] = str(Path.home() / '.occultbus')
    
    print("✓ Set OCCULTBUS_HOME environment variable")
    print("✓ Occult Router is now the default routing policy")
    
    return True

if __name__ == '__main__':
    setup_occult_router()