# Generative Agents: Interactive Simulacra of Human Behavior

- **Citation:** Park JS, O'Brien JC, Cai CJ, et al., UIST '23. arXiv 2304.03442.
- **Link:** https://arxiv.org/abs/2304.03442 · **Open access:** yes (full text read)
- **Code:** https://github.com/joonspk-research/generative_agents · **Code licence:** Apache-2.0 (LICENSE file checked)
- **Paper licence:** arXiv non-exclusive
- **Informs:** cross-session memory, memory and disclosure

## Mechanism
Each agent has a memory stream of natural-language observations, each stamped with an LLM-rated importance (1-10, one call at creation). Retrieval scores every memory as recency (exponential decay, factor 0.995 per hour since last access) + importance + relevance (cosine similarity of embeddings to the query), each min-max scaled to [0,1], all weights 1; top items that fit the context window go in the prompt. Reflection fires when summed importance of recent events passes 150 (about 2-3 times per game day): the LLM gets the 100 latest records, proposes 3 salient questions, each question retrieves memories, and the LLM writes insights with citations to evidence; reflections are stored back as memories and can nest into a tree. Planning is top-down (day, hour, minutes) and re-planned on reactions. Many LLM calls per agent step.

## Evidence
Interview study, n=100 Prolific raters ranking 5 conditions (TrueSkill): full architecture mu=29.89 (sigma 0.72); no reflection 26.88; no reflection or planning 25.64; human crowdworker authors 22.95; no memory, planning or reflection 21.21 (Cohen d=8.16 full vs. none). Kruskal-Wallis H(4)=150.29, p<0.001. 25-agent, 2-game-day run: awareness of the party rose 4% to 52% (1 to 13 agents), of the mayoral candidacy 4% to 32%; network density 0.167 to 0.74; 1.3% (6 of 453) relationship claims were hallucinated. Failures: missed retrieval, partial fragments, embellishment from world knowledge. Run cost "thousands of dollars" of tokens for 25 agents over two days.

## Limitations
- Cost and latency: several LLM calls per step; authors call real-time use future work.
- Believability judged against crowdworker authors, not expert humans; short timescale.
- Embellishment and retrieval misses; authors flag prompt and memory hacking as open risks.
- Sandbox life simulation, not a clinical interview.

## For Rapport
**Verdict:** idea-only. The importance-gated reflection (sum of importance past a threshold) and the recency+importance+relevance retrieval are a clean recipe for cross-session memory, run offline between sessions, not per turn. Apache-2.0 code is reusable but its simulation stack does not fit. Warning: embellishment is exactly the failure that locked memory items and clinical facts must prevent; reflections must never overwrite facts.
