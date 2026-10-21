# Concordia: Generative agent-based modeling with actions grounded in physical, social, or digital space

- **Citation:** Vezhnevets A. S., Agapiou J. P., Aharon A., et al., arXiv 2023 (Google DeepMind). arXiv:2312.03664
- **Link:** https://arxiv.org/abs/2312.03664 · **Open access:** yes (full text read)
- **Code:** https://github.com/google-deepmind/concordia · **Code licence:** Apache-2.0 (LICENSE file checked)
- **Paper licence:** arXiv non-exclusive
- **Informs:** identity/formulation, memory and disclosure, evaluation

## Mechanism
A library for generative agent-based models. Each agent has a long-term associative memory (set of strings, embedding retrieval, as in Park et al.) and a working memory made of component states z. A component is a small module (identity, plan, observation-and-clock, goal, hunger, etc.) that updates its state by querying memory, usually with an LLM question; the agent's action is one LLM call over the concatenated component contexts. A Game Master (GM) with its own memory and components turns each natural-language action into an event statement, updates grounded variables (money, items, votes) that can use ordinary code (ODE, state machines), and emits observations to affected players. The agent frames behaviour as March and Olsen's three questions: what situation is this, what kind of person am I, what does such a person do here. Digital grounding: GM translates actions into app API calls (phone, calendar). Several LLM calls per agent step plus several per GM event. The paper has no experiments of its own; it gives design principles.

## Evidence
No quantitative results. It lists validation practice instead: measure generalisation against real human data, algorithmic fidelity per research question, model comparison, robustness to prompt wording, and parsimony ("minimal number of maximally general modelling choices"); flags open problems of train-test contamination, stereotypes, and validating a single individual.

## Limitations
- No empirical evaluation in the paper; claims are design arguments.
- Multi-call loops (agents plus GM) fit batch simulation, not a one-call live voice turn.
- Social and digital simulation, not clinical interviewing; no affect model beyond what a component prompt states.
- Authors list unsolved validity issues (contamination, stereotypes, individual-level fidelity).

## For Rapport
**Verdict:** idea-only. Apache-2.0 allows reuse, but the useful part is the pattern: independent components each producing a small piece of context, and grounded variables updated by plain code (matches state/trust/PAD updated in clamped steps outside the LLM). For self-play doctors, a component-built "doctor" with a GM that holds case state would be a tidy offline harness; the validity checklist (compare models, perturb wording, per-question fidelity) is worth copying into the evaluation plan.
