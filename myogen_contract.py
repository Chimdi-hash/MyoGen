# v0.3.0
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
import json


class MyogenDictionary(gl.Contract):
    """
    MYOGEN: A decentralized AI-powered dictionary for muscle physiology.

    ECONOMIC MODEL:
    - Users stake exactly 1 GEN per proposal.
    - If the AI validators ACCEPT the definition, the user immediately receives 2 GEN back
      (original 1 GEN stake + 1 GEN reward) via gl.transfer — no claim step needed.
    - If the AI validators REJECT the definition, the 1 GEN stake is permanently slashed
      and held in the contract treasury.
    - Slashed GEN accumulates in the contract as a treasury for future governance rewards.
    """

    # ─────────────────────── Storage ───────────────────────
    query_history: TreeMap[str, str]   # lowercase(address) -> JSON history
    all_terms_cache: TreeMap[str, str] # lowercase(term) -> JSON term data
    treasury: u256                     # Accumulated slashed GEN (in wei)
    total_queries: u256
    popular_terms_list: str

    def __init__(self):
        self.treasury = 0
        self.total_queries = 0
        self.popular_terms_list = "[]"

    # ─────────────────────── Core Staking + AI Validation ───────────────────────

    @gl.public.write.payable
    def propose_term(self, term: str, proposed_definition: str, evidence_url: str):
        """
        Propose a new muscle physiology term.
        Must send exactly 1 GEN. If accepted, 2 GEN returned immediately.
        If rejected, 1 GEN is slashed to treasury.
        """
        caller = gl.message.sender_address
        stake = gl.message.value
        ONE_GEN = 1000000000000000000  # 1e18 wei = 1 GEN

        # Validate stake amount
        if stake < ONE_GEN:
            raise Exception("Must stake at least 1 GEN to propose a term.")

        term_clean = term.strip()
        term_lower = term_clean.lower()

        if term_lower == "":
            raise Exception("Term cannot be empty.")

        # Prevent re-proposing an existing term (saves user's GEN)
        if term_lower in self.all_terms_cache:
            raise Exception(
                f"'{term_clean}' already exists in the MYOGEN dictionary. "
                f"Your stake was not charged. (No GEN deducted for this check — but since "
                f"this contract is payable, please avoid re-submitting existing terms.)"
            )

        # ── AI Validation via GenLayer eq_principle ──
        def build_prompt() -> str:
            return gl.nondet.exec_prompt(
                f"""You are MYOGEN, an expert AI system for muscle physiology and anatomy.
A student has proposed the following term for the decentralized MYOGEN dictionary.

Term: "{term_clean}"
Proposed definition: "{proposed_definition}"
Evidence URL: "{evidence_url}"

Your task:
1. Fetch the evidence URL and read the content.
2. Determine if the proposed definition is scientifically accurate based on that content.
3. Return ONLY a valid JSON object (no markdown fences, no extra text):
{{
    "is_accurate": true,
    "reasoning": "Concise explanation referencing the evidence URL.",
    "term": "{term_clean}",
    "definition": "A refined 2-3 sentence definition suitable for medical students.",
    "category": "Anatomy & Physiology",
    "detailed_explanation": "4-6 sentences on the biological mechanism and clinical relevance.",
    "key_facts": ["fact 1", "fact 2", "fact 3"],
    "related_terms": ["related term 1", "related term 2"],
    "clinical_relevance": "1-2 sentences on clinical importance.",
    "muscle_groups_involved": ["muscle 1"]
}}"""
            )

        explanation_result = gl.eq_principle.prompt_non_comparative(
            build_prompt,
            task=(
                "Verify the proposed muscle physiology term against the evidence URL "
                "and return valid JSON."
            ),
            criteria=(
                "The leader's response is a valid JSON object "
                "(starts with '{' and ends with '}') "
                "containing at minimum the keys 'is_accurate' and 'reasoning'."
            )
        )

        # ── Parse AI response safely ──
        try:
            cleaned = explanation_result.strip()
            if "```" in cleaned:
                start = cleaned.find("{")
                end = cleaned.rfind("}") + 1
                if start >= 0 and end > start:
                    cleaned = cleaned[start:end]
            explanation_data = json.loads(cleaned)
            if not isinstance(explanation_data, dict):
                explanation_data = {}
        except Exception:
            explanation_data = {}

        is_accurate = bool(explanation_data.get("is_accurate", False))

        # Build safe flat record for storage
        key_facts      = explanation_data.get("key_facts", [])
        related_terms  = explanation_data.get("related_terms", [])
        muscles        = explanation_data.get("muscle_groups_involved", [])

        safe_explanation = {
            "term":                  explanation_data.get("term", term_clean),
            "definition":            explanation_data.get("definition", proposed_definition),
            "category":              explanation_data.get("category", "General"),
            "detailed_explanation":  explanation_data.get("detailed_explanation", ""),
            "clinical_relevance":    explanation_data.get("clinical_relevance", ""),
            "reasoning":             explanation_data.get("reasoning", ""),
            "key_facts":             key_facts     if isinstance(key_facts, list)     else [],
            "related_terms":         related_terms if isinstance(related_terms, list) else [],
            "muscle_groups_involved":muscles       if isinstance(muscles, list)       else [],
            "visualization_type":    "fiber_diagram",
            "color_theme":           "red-orange",
        }

        # Always use lowercase for address keys to avoid checksum mismatches
        caller_str = str(caller).lower()

        if is_accurate:
            # ── ACCEPTED: Immediately return 2x stake to proposer ──
            reward_amount = int(stake) * 2  # 2 GEN in wei
            gl.transfer(caller, reward_amount)

            # Persist the verified term
            self.all_terms_cache[term_lower] = json.dumps({
                "explanation":        safe_explanation,
                "validator_consensus": True,
                "proposer":           caller_str,
            })

            # Update popular terms list
            try:
                popular = json.loads(self.popular_terms_list)
                if not isinstance(popular, list):
                    popular = []
            except Exception:
                popular = []
            if term_clean not in popular:
                popular.append(term_clean)
                self.popular_terms_list = json.dumps(popular)

            self._record_query(
                caller_str, term_lower, term_clean,
                safe_explanation.get("definition", ""),
                safe_explanation.get("reasoning", ""),
                True
            )

        else:
            # ── REJECTED: Stake slashed to treasury ──
            self.treasury += stake
            reasoning = explanation_data.get("reasoning", "Definition did not match evidence.")
            self._record_query(
                caller_str, term_lower, term_clean,
                proposed_definition, reasoning, False
            )

        self.total_queries += 1

    # ─────────────────────── Internal Helpers ───────────────────────

    def _record_query(
        self,
        caller_str: str,    # already lowercased
        term_lower: str,
        term_display: str,
        definition: str,
        reasoning: str,
        accepted: bool,
    ):
        try:
            history = json.loads(self.query_history[caller_str]) if caller_str in self.query_history else []
            if not isinstance(history, list):
                history = []
        except Exception:
            history = []

        history.append({
            "term":       term_display,
            "term_lower": term_lower,
            "definition": definition,
            "reasoning":  reasoning,
            "accepted":   accepted,
        })

        if len(history) > 50:
            history = history[-50:]

        self.query_history[caller_str] = json.dumps(history)

    # ─────────────────────── View Functions ───────────────────────

    @gl.public.view
    def get_cached_term(self, term: str) -> str:
        """Returns the cached term data or {found: false} if not found."""
        term_lower = term.strip().lower()
        if term_lower in self.all_terms_cache:
            return self.all_terms_cache[term_lower]
        return json.dumps({"found": False, "term": term})

    @gl.public.view
    def get_user_history(self, user_address: str) -> str:
        """Returns the proposal history for a given address."""
        key = user_address.strip().lower()
        if key in self.query_history:
            return self.query_history[key]
        return "[]"

    @gl.public.view
    def get_proposal_status(self, user_address: str, term: str) -> str:
        """Returns ACCEPTED/REJECTED/PENDING status for the most recent proposal of a term."""
        term_lower = term.strip().lower()
        key = user_address.strip().lower()
        if key in self.query_history:
            try:
                history = json.loads(self.query_history[key])
                if isinstance(history, list):
                    for entry in reversed(history):
                        if entry.get("term_lower", "") == term_lower:
                            if entry.get("accepted", False):
                                return json.dumps({
                                    "status":    "ACCEPTED",
                                    "reasoning": entry.get("reasoning", "Definition verified."),
                                    "reward":    2,
                                })
                            else:
                                return json.dumps({
                                    "status":    "REJECTED",
                                    "reasoning": entry.get("reasoning", "Inaccurate definition."),
                                    "reward":    0,
                                })
            except Exception:
                pass
        return json.dumps({"status": "PENDING", "reasoning": "Not yet processed.", "reward": 0})

    @gl.public.view
    def get_treasury_balance(self) -> str:
        """Returns total slashed GEN held in contract treasury (in wei)."""
        return str(int(self.treasury))

    @gl.public.view
    def get_stats(self) -> str:
        return json.dumps({
            "total_queries":   int(self.total_queries),
            "platform":        "MYOGEN",
            "network":         "GenLayer Studio",
            "treasury_wei":    int(self.treasury),
        })

    @gl.public.view
    def get_popular_terms(self) -> str:
        return self.popular_terms_list
