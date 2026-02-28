# Philosophy

## Design Rationale

Most AI runs in data centers consuming megawatts of power and routing queries across continents. This is inefficient.

Your GPU sits idle most of the time. You already own it. You already pay for its electricity.

Peridot runs on hardware you own, using power you're already consuming. No corporate intermediaries. Local compute is faster (no network latency), more private (data never transmitted), and more efficient (right-sized models).

The technical capability has existed for years. The barrier was software accessibility. This project removes that barrier.

## Core Principle

**The user is sovereign.**

- No telemetry without explicit consent
- No autonomous action without authorization  
- No restrictions that cannot be modified or removed

`constitution.json` ships with sensible defaults. Make them stricter, looser, or delete the file entirely. Your choice.

## Why Local AI Matters

**For you:**
- Free (no subscription, no API costs, no usage limits)
- Private (data never leaves your machine, no logs, no training on your queries)
- Fast (no network latency, responses in milliseconds)
- Sovereign (you control the rules)

**For the broader ecosystem:**
- Distributed compute (thousands of personal GPUs instead of centralized data centers)
- Efficient resource use (existing hardware, only active when needed)
- Reduced infrastructure burden (no massive facilities consuming local resources)

## The Economic Reality

Cloud AI companies want you to believe local AI is "too hard" or "not good enough."

Local AI is hard *for them* because their business model depends on subscription revenue and API quotas. They've built valuations on the assumption you'll keep sending data to their servers.

Peridot demonstrates the opposite:
- Consumer laptop GPUs run models 90% as capable as GPT-3.5
- Processing at 50+ tokens/second (faster than human reading)
- Setup takes 10 minutes
- Operating cost: $0/month (electricity already paid)

The future of AI is distributed and local — running on hardware people already own, using power they're already paying for, with zero corporate intermediaries.

This is not idealism. This is pragmatic engineering. The hardware exists. The models exist. The software now exists.

**That's what Peridot is.**
