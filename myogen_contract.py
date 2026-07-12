# v0.2.17
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
import json


class MyogenDictionary(gl.Contract):
    """
    MYOGEN: A decentralized AI-powered dictionary for muscle physiology.
    Uses real GEN staking: 1 GEN staked per proposal.
    Accurate proposals earn 2x stake back. Inaccurate proposals are slashed.
    """

    # ─────────────────────── Storage ───────────────────────
    registered_users: TreeMap[Address, str]
    query_history: TreeMap[Address, str]
    all_terms_cache: TreeMap[str, str]
    pending_rewards: TreeMap[str, str]   # str(address) -> str(amount_wei)

    total_queries: u256
    total_users: u256
    popular_terms_list: str

    ONE_GEN: u256

    def __init__(self):
        self.total_queries = 0
        self.total_users = 0
        self.popular_terms_list = "[]"
        self.ONE_GEN = 1000000000000000000  # 1 GEN in wei

    # ─────────────────────── Registration ───────────────────────

    @gl.public.write
    def register_user(self, display_name: str):
        caller = gl.message.sender_address
        if caller not in self.registered_users:
            self.registered_users[caller] = json.dumps({
                "display_name": display_name if display_name else "Anonymous",
                "query_count": 0,
                "is_registered": True
            })
            self.total_users += 1

    @gl.public.view
    def is_registered(self, user_address: Address) -> bool:
        return user_address in self.registered_users

    @gl.public.view
    def get_user_info(self, user_address: Address) -> str:
        if user_address in self.registered_users:
            return self.registered_users[user_address]
        return json.dumps({
            "is_registered": False,
            "display_name": "Unknown",
            "query_count": 0
        })

    # ─────────────────────── Core Staking Function ───────────────────────

    @gl.public.write.payable
    def propose_term(self, term: str, proposed_definition: str, evidence_url: str):
        caller = gl.message.sender_address
        stake = gl.message.value       # Amount of GEN sent (in wei)

        if stake < self.ONE_GEN:
            raise Exception("Must stake at least 1 GEN to propose a term.")

        term_clean = term.strip()
        term_lower = term_clean.lower()

        if term_lower == "":
            raise Exception("Term cannot be empty.")

        if term_lower in self.all_terms_cache:
            raise Exception(f"Term '{term_clean}' already exists in the dictionary.")

        def build_prompt() -> str:
            return gl.nondet.exec_prompt(
                f"""You are MYOGEN, an expert AI system for muscle physiology and anatomy.
A student proposes this term: "{term_clean}"
Proposed definition: "{proposed_definition}"
Evidence URL: "{evidence_url}"

Fetch the evidence URL and verify if the proposed definition is accurate.
Return ONLY a valid JSON object (no markdown, no extra text):
{{
    "is_accurate": true,
    "reasoning": "Clear explanation of why this is accurate based on the evidence.",
    "term": "{term_clean}",
    "definition": "A refined 2-3 sentence definition for medical students.",
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
            task="Verify the proposed muscle physiology term against the evidence URL and return valid JSON only.",
            criteria="The response must be valid JSON with the exact keys requested. is_accurate must be true only if the definition is confirmed by the evidence URL."
        )

        # Parse AI response safely
        try:
            cleaned = explanation_result.strip()
            # Strip any markdown code fences
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

        # Build safe flat summary to store
        key_facts = explanation_data.get("key_facts", [])
        related_terms = explanation_data.get("related_terms", [])
        muscles = explanation_data.get("muscle_groups_involved", [])

        safe_explanation = {
            "term": explanation_data.get("term", term_clean),
            "definition": explanation_data.get("definition", proposed_definition),
            "category": explanation_data.get("category", "General"),
            "detailed_explanation": explanation_data.get("detailed_explanation", ""),
            "clinical_relevance": explanation_data.get("clinical_relevance", ""),
            "reasoning": explanation_data.get("reasoning", ""),
            "key_facts": key_facts if isinstance(key_facts, list) else [],
            "related_terms": related_terms if isinstance(related_terms, list) else [],
            "muscle_groups_involved": muscles if isinstance(muscles, list) else [],
            "visualization_type": "fiber_diagram",
            "color_theme": "red-orange"
        }

        caller_str = str(caller)

        if is_accurate:
            # ── REWARD: return stake + 1 GEN reward (2x total) ──
            existing_str = self.pending_rewards[caller_str] if caller_str in self.pending_rewards else "0"
            try:
                existing = int(existing_str)
            except Exception:
                existing = 0
            reward = int(stake) * 2
            self.pending_rewards[caller_str] = str(existing + reward)

            # Store in global terms cache
            self.all_terms_cache[term_lower] = json.dumps({
                "explanation": safe_explanation,
                "validator_consensus": True,
                "proposer": caller_str
            })

            # Update popular terms list
            try:
                current_popular = json.loads(self.popular_terms_list)
                if not isinstance(current_popular, list):
                    current_popular = []
            except Exception:
                current_popular = []
            if term_clean not in current_popular:
                current_popular.append(term_clean)
                self.popular_terms_list = json.dumps(current_popular)

            self._record_query(caller, term_lower, term_clean,
                               safe_explanation.get("definition", ""),
                               safe_explanation.get("reasoning", ""),
                               True)
        else:
            # ── SLASH: stake is forfeited ──
            reasoning = explanation_data.get("reasoning", "Definition did not match evidence.")
            self._record_query(caller, term_lower, term_clean,
                               proposed_definition, reasoning, False)

        self.total_queries += 1

    # ─────────────────────── Claim Rewards ───────────────────────

    @gl.public.write
    def claim_reward(self):
        """Claim pending rewards earned from successful proposals."""
        caller = gl.message.sender_address
        caller_str = str(caller)
        if caller_str not in self.pending_rewards:
            raise Exception("No pending rewards to claim.")
        amount_str = self.pending_rewards[caller_str]
        try:
            amount = int(amount_str)
        except Exception:
            amount = 0
        if amount <= 0:
            raise Exception("No rewards available.")
        self.pending_rewards[caller_str] = "0"
        gl.transfer(caller, amount)

    @gl.public.view
    def get_pending_reward(self, user_address: Address) -> str:
        addr_str = str(user_address)
        if addr_str in self.pending_rewards:
            return self.pending_rewards[addr_str]
        return "0"

    # ─────────────────────── Internal Helpers ───────────────────────

    def _record_query(
        self,
        caller: Address,
        term_lower: str,
        term_display: str,
        definition: str,
        reasoning: str,
        accepted: bool
    ):
        try:
            if caller in self.query_history:
                history = json.loads(self.query_history[caller])
                if not isinstance(history, list):
                    history = []
            else:
                history = []
        except Exception:
            history = []

        history.append({
            "term": term_display,
            "term_lower": term_lower,
            "definition": definition,
            "reasoning": reasoning,
            "accepted": accepted
        })

        if len(history) > 20:
            history = history[-20:]

        self.query_history[caller] = json.dumps(history)

    # ─────────────────────── View Functions ───────────────────────

    @gl.public.view
    def get_cached_term(self, term: str) -> str:
        term_lower = term.strip().lower()
        if term_lower in self.all_terms_cache:
            return self.all_terms_cache[term_lower]
        return json.dumps({"found": False, "term": term})

    @gl.public.view
    def get_user_history(self, user_address: Address) -> str:
        if user_address in self.query_history:
            return self.query_history[user_address]
        return "[]"

    @gl.public.view
    def get_proposal_status(self, user_address: Address, term: str) -> str:
        term_lower = term.strip().lower()
        if user_address in self.query_history:
            try:
                history = json.loads(self.query_history[user_address])
                if isinstance(history, list):
                    for entry in reversed(history):
                        if entry.get("term_lower", "") == term_lower:
                            if entry.get("accepted", False):
                                return json.dumps({
                                    "status": "ACCEPTED",
                                    "reasoning": entry.get("reasoning", "Definition verified."),
                                    "reward": 2
                                })
                            else:
                                return json.dumps({
                                    "status": "REJECTED",
                                    "reasoning": entry.get("reasoning", "Inaccurate definition."),
                                    "reward": 0
                                })
            except Exception:
                pass

        return json.dumps({
            "status": "PENDING",
            "reasoning": "Not yet processed.",
            "reward": 0
        })

    @gl.public.view
    def get_stats(self) -> str:
        return json.dumps({
            "total_queries": int(self.total_queries),
            "total_users": int(self.total_users),
            "platform": "MYOGEN",
            "network": "GenLayer Studio"
        })

    @gl.public.view
    def get_popular_terms(self) -> str:
        return self.popular_terms_list
