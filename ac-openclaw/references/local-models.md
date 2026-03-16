# Local LLM Models for OpenClaw — Reference

> **Last updated:** 2026-03-14
> **Sources:**
>
> - [ollama.ai](https://ollama.ai/) (accessed 2026-03-14)
> - [localllm.in — VRAM requirements](https://localllm.in/blog/ollama-vram-requirements-for-local-llms) (2026-01)
> - [Contabo — Open Source LLMs 2026](https://contabo.com/blog/open-source-llms/) (2026-02)
> - [Ollama architecture deep dive](https://dasroot.net/posts/2026/01/ollama-behind-the-scenes-architecture/) (2026-01)

## Ollama on ARM64 (CPU-only)

Ollama runs natively on ARM64/aarch64. Most cloud ARM servers (Hetzner CAX, AWS Graviton, Oracle Ampere, etc.) are **CPU-only** unless a GPU instance is selected.

**Performance expectations (CPU-only, ARM64):**

- 3-4B models: ~15-25 tok/s (usable for chat)
- 7-8B models: ~8-15 tok/s (usable for messaging, slow for long text)
- 14B models: ~4-8 tok/s (functional but noticeable delay)
- 20B+ models: ~2-4 tok/s (slow, not recommended for interactive use)

> These are rough estimates. Actual performance varies by model architecture, quantization, and context length.

## Model Recommendations by Server RAM

### 4 GB RAM (e.g., Hetzner CAX11, DigitalOcean Basic 4 GB, Vultr 4 GB)

| Model | Params | Quant | RAM usage | Quality | Notes |
|-------|--------|-------|-----------|---------|-------|
| Qwen 3 4B | 4B | Q4_K_M | ~3 GB | Basic | Leaves ~1 GB for OS + OpenClaw |
| Phi-3 Mini | 3.8B | Q4_K_M | ~2.5 GB | Basic | Microsoft, good at reasoning |

> **Warning:** 4 GB RAM is tight. OpenClaw + Node.js + OS use ~1-1.5 GB. Only ~2.5 GB left for the model. Expect swapping with larger models.

### 8 GB RAM (e.g., Hetzner CAX21, DigitalOcean Basic 8 GB, Vultr 8 GB)

| Model | Params | Quant | RAM usage | Quality | Notes |
|-------|--------|-------|-----------|---------|-------|
| Llama 3.1 8B | 8B | Q4_K_M | ~5-6 GB | Good | Meta, strong general assistant |
| Qwen 3 8B | 8B | Q4_K_M | ~5-6 GB | Good | Alibaba, excellent multilingual |
| Gemma 2 9B | 9B | Q4_K_M | ~5-6 GB | Good | Google, strong reasoning |
| Mistral 7B | 7B | Q4_K_M | ~4-5 GB | Good | Fast, good at instruction following |

> **Sweet spot for local models.** 8B models run comfortably with room for OpenClaw.

### 16 GB RAM (e.g., Hetzner CAX31, DigitalOcean Basic 16 GB, Vultr 16 GB)

| Model | Params | Quant | RAM usage | Quality | Notes |
|-------|--------|-------|-----------|---------|-------|
| Qwen3 14B | 14B | Q4_K_M | ~9-10 GB | Very good | Best bang for buck |
| GPT-OSS 20B | 20B | Q4_K_M | ~12-13 GB | Very good | Strong instruction following |
| Llama 3.1 8B | 8B | Q8_0 | ~9 GB | Good+ | Higher quality quantization |
| DeepSeek-V3-0324 | 14B | Q4_K_M | ~9-10 GB | Very good | Strong at code |

> **Best value for quality.** 14B models offer a significant quality jump over 8B.

### 32 GB RAM (e.g., Hetzner CAX41, DigitalOcean Premium 32 GB, Vultr 32 GB)

| Model | Params | Quant | RAM usage | Quality | Notes |
|-------|--------|-------|-----------|---------|-------|
| Qwen3 32B | 32B | Q4_K_M | ~20 GB | Excellent | Near-frontier quality |
| Llama 3.1 70B | 70B | Q2_K | ~28 GB | Excellent | Heavily quantized but still strong |
| Command R+ | 35B | Q4_K_M | ~22 GB | Excellent | Cohere, good for agentic tasks |

> **Diminishing returns.** 32B models are great but CPU inference is slow (~2-5 tok/s). Consider BYOK at this price point.

## Quantization Quick Reference

| Quantization | Bits | Quality | Size (vs FP16) | Speed |
|-------------|------|---------|----------------|-------|
| Q2_K | 2 | Poor | ~15% | Fastest |
| Q4_K_M | 4 | Good | ~30% | Fast |
| Q5_K_M | 5 | Very good | ~35% | Medium |
| Q8_0 | 8 | Excellent | ~55% | Slow |
| FP16 | 16 | Original | 100% | Slowest |

**Q4_K_M** is the recommended default — best balance of quality, speed, and memory.

## BYOK vs Local: Cost Comparison

Prices below use Hetzner CAX as an example; other providers have comparable tiers. Research actual pricing for the user's chosen provider.

| Setup | Monthly server cost | Model cost | Total | Quality |
|-------|-------------------|------------|-------|---------|
| 4 GB VPS + BYOK (Claude Sonnet) | ~4-6 EUR | ~5-20 EUR (usage) | ~10-25 EUR | Frontier |
| 4 GB VPS + BYOK (GPT-5) | ~4-6 EUR | ~5-20 EUR (usage) | ~10-25 EUR | Frontier |
| 8 GB VPS + Ollama 8B | ~7-12 EUR | 0 EUR | ~7-12 EUR | Good |
| 16 GB VPS + Ollama 14B | ~14-20 EUR | 0 EUR | ~14-20 EUR | Very good |
| 32 GB VPS + Ollama 32B | ~25-40 EUR | 0 EUR | ~25-40 EUR | Excellent (but slow) |
| 4 GB VPS + OpenRouter (pay-per-use) | ~4-6 EUR | ~2-10 EUR | ~7-15 EUR | Any model |

> **Recommendation:** For most users, **small VPS + BYOK** is the best value. You get frontier-quality models (Claude Opus, GPT-5) for a few euros more than running a mediocre local model. Local models shine when **privacy is paramount** or for **offline/air-gapped** setups.

## OpenClaw Model Provider Configuration

### Ollama (local)

```bash
# Install
curl -fsSL https://ollama.ai/install.sh | sh

# Pull model
ollama pull llama3.1:8b

# OpenClaw auto-detects at http://127.0.0.1:11434/v1
openclaw models set ollama/llama3.1:8b
```

### BYOK Providers

| Provider | Env variable | Config key | Example model |
|----------|-------------|------------|---------------|
| Anthropic | `ANTHROPIC_API_KEY` | `anthropic/claude-opus-4-6` | Claude Opus 4.6 |
| OpenAI | `OPENAI_API_KEY` | `openai/gpt-5.1-codex` | GPT-5.1 Codex |
| Google Gemini | `GEMINI_API_KEY` | `google/gemini-3-pro-preview` | Gemini 3 Pro |
| OpenRouter | `OPENROUTER_API_KEY` | `openrouter/<provider>/<model>` | Any model |
| xAI | `XAI_API_KEY` | `xai/grok-3` | Grok 3 |
| Groq | `GROQ_API_KEY` | `groq/<model>` | Fast inference |
| Mistral | `MISTRAL_API_KEY` | `mistral/<model>` | Mistral Large |

### Key Rotation

OpenClaw supports automatic key rotation on rate-limit (429) errors:

```bash
export ANTHROPIC_API_KEY="sk-ant-primary"
export ANTHROPIC_API_KEY_1="sk-ant-backup1"
export ANTHROPIC_API_KEY_2="sk-ant-backup2"
```

### Priority Chain

When multiple providers are configured, OpenClaw uses this priority:
Anthropic > OpenAI > OpenRouter > Gemini > OpenCode > GitHub Copilot > xAI > Groq > Mistral > Cerebras > Venice > Moonshot > Ollama
