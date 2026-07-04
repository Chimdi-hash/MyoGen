# v0.2.17
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
# MYOGEN Intelligent Contract — GenLayer Studio
# Decentralized Muscle Physiology & Anatomy Dictionary
# Validators powered by Optimistic Democracy & LLM consensus

# NOTE: Deploy this contract to GenLayer Studio
# Network: https://studio.genlayer.com/api | Chain ID: 61999

from genlayer import *
import json

class MyogenDictionary(gl.Contract):
    """
    MYOGEN: A decentralized AI-powered dictionary for muscle physiology
    and anatomy terminology. Uses GenLayer's Intelligent Contracts with
    LLM-powered validators to deliver accurate, consensus-verified
    medical explanations on-chain.
    """

    # ─────────────────────── Storage ───────────────────────
    registered_users: TreeMap[Address, str]  # addr → JSON str of {timestamp, name, query_count}
    query_history: TreeMap[Address, str]     # addr → JSON str of [{term, explanation, timestamp}]
    all_terms_cache: TreeMap[str, str]       # term → JSON str of {explanation, graphical_data, validated_at}
    total_queries: u256
    total_users: u256

    def __init__(self):
        """Initialize the MYOGEN contract storage."""
        self.total_queries = u256(0)
        self.total_users = u256(0)
        self.registered_users = TreeMap()
        self.query_history = TreeMap()
        self.all_terms_cache = TreeMap()

    # ─────────────────────── Registration ───────────────────────

    @gl.public.write
    def register_user(self, display_name: str):
        """
        Register a new user wallet address.
        Called when a user first connects their wallet.
        """
        caller = gl.message.sender
        if caller not in self.registered_users:
            self.registered_users[caller] = json.dumps({
                "display_name": display_name if display_name else "Anonymous",
                "registered_at": gl.message.timestamp if hasattr(gl.message, 'timestamp') else 0,
                "query_count": 0,
                "is_registered": True
            })
            self.total_users += 1

    @gl.public.view
    def is_registered(self, user_address: Address) -> bool:
        """Check if a wallet address is registered."""
        return user_address in self.registered_users

    @gl.public.view
    def get_user_info(self, user_address: Address) -> str:
        """Get public info about a user (if registered)."""
        if user_address in self.registered_users:
            return self.registered_users[user_address]
        return json.dumps({
            "is_registered": False,
            "display_name": "Unknown",
            "query_count": 0
        })

    @gl.public.view
    def get_cached_term(self, term: str) -> dict:
        """Fetch a term directly from the cache if it has been validated."""
        term_lower = term.strip().lower()
        if term_lower in self.all_terms_cache:
            return json.loads(self.all_terms_cache[term_lower])
        return {}

    # ─────────────────────── Core Study Function ───────────────────────

    @gl.public.write
    def study_term(self, term: str, web_data: str):
        """
        Primary function: User submits a muscle physiology/anatomy term.
        Validators analyze the term using LLM and reach consensus via
        Optimistic Democracy. Result is stored on-chain.

        This is the function triggered when user clicks 'Study' and signs the tx.
        """
        caller = gl.message.sender
        term_lower = term.strip().lower()

        # Check if result is already cached (avoid duplicate AI calls)
        if term_lower in self.all_terms_cache:
            cached = json.loads(self.all_terms_cache[term_lower])
            self._record_query(caller, term, cached["explanation"], cached["graphical_data"])
            return

        # ── AI Validator Analysis ──
        # Each validator runs this LLM prompt independently.
        # Optimistic Democracy ensures consensus across validators.
        def build_prompt() -> str:
            return f"""You are MYOGEN, an expert AI system specializing in muscle physiology,
anatomy, kinesiology, and sports science. A student wants to understand: "{term}"

Here is some web data scraped by the frontend to provide context:
{web_data}

Provide a comprehensive, accurate, educational explanation following this EXACT JSON structure:

{{
    "term": "{term}",
    "definition": "A clear 2-3 sentence definition suitable for medical students",
    "category": "one of: Muscle Fiber Types | Muscle Mechanics | Anatomy & Physiology | Biochemistry | Neural Control | Pathology | Exercise Physiology",
    "detailed_explanation": "A thorough 4-6 sentence explanation covering the biological mechanism, function, and clinical relevance",
    "key_facts": [
        "Key fact 1",
        "Key fact 2",
        "Key fact 3",
        "Key fact 4",
        "Key fact 5"
    ],
    "related_terms": ["related_term_1", "related_term_2", "related_term_3"],
    "clinical_relevance": "1-2 sentences about clinical or athletic relevance",
    "muscle_groups_involved": ["muscle1", "muscle2"],
    "visualization_type": "one of: fiber_diagram | contraction_cycle | cross_section | neural_pathway | biochemical_cycle | joint_mechanics | cellular_diagram",
    "color_theme": "one of: red-orange | blue-cyan | green-teal | purple-violet | gold-amber"
}}

If the term is NOT related to muscle physiology, anatomy, or exercise science (evaluate based on the term and the web data context), return exactly this JSON:
{{
    "term": "{term}",
    "definition": "this is not a muscle term",
    "category": "Out of Scope",
    "detailed_explanation": "MYOGEN specializes exclusively in muscle physiology, anatomy, kinesiology, and related sports science. Please enter a relevant anatomical or physiological term.",
    "key_facts": [],
    "related_terms": ["actin", "myosin", "sarcomere", "motor neuron", "muscle fiber"],
    "clinical_relevance": "N/A",
    "muscle_groups_involved": [],
    "visualization_type": "fiber_diagram",
    "color_theme": "red-orange"
}}

Return ONLY the JSON object, no other text."""

        explanation_result = gl.eq_principle.prompt_non_comparative(
            build_prompt,
            task="Analyze the medical term based on context and return the requested JSON object.",
            criteria="""
                The response must be valid JSON matching the exact structure requested.
                The explanation must be medically accurate and relevant to the term provided.
                It should correctly classify if the term is out of scope.
            """
        )

        # Parse the LLM result
        try:
            explanation_data = json.loads(explanation_result)
        except (json.JSONDecodeError, TypeError):
            explanation_data = {
                "term": term,
                "definition": f"Analysis of '{term}' in the context of muscle physiology.",
                "category": "General",
                "detailed_explanation": explanation_result if isinstance(explanation_result, str) else "Explanation processed by validators.",
                "key_facts": ["Analyzed by GenLayer AI validators", "Consensus reached via Optimistic Democracy"],
                "related_terms": [],
                "clinical_relevance": "Consult a medical professional for clinical advice.",
                "muscle_groups_involved": [],
                "visualization_type": "fiber_diagram",
                "color_theme": "red-orange"
            }

        # Generate graphical data for frontend visualization
        graphical_data = self._generate_graphical_data(explanation_data)

        # Cache the result
        self.all_terms_cache[term_lower] = json.dumps({
            "explanation": explanation_data,
            "graphical_data": graphical_data,
            "validated_at": gl.message.timestamp if hasattr(gl.message, 'timestamp') else 0,
            "validator_consensus": True
        })

        # Record query in user history
        self._record_query(caller, term, explanation_data, graphical_data)
        self.total_queries += 1

        # Update user query count
        if caller in self.registered_users:
            user_data = json.loads(self.registered_users[caller])
            user_data["query_count"] = user_data.get("query_count", 0) + 1
            self.registered_users[caller] = json.dumps(user_data)

    def _generate_graphical_data(self, explanation_data: dict) -> dict:
        """Generate structured data for frontend visual animations."""
        viz_type = explanation_data.get("visualization_type", "fiber_diagram")
        color_theme = explanation_data.get("color_theme", "red-orange")
        category = explanation_data.get("category", "General")

        # Color mappings for visualization
        color_map = {
            "red-orange": {"primary": "#FF6B2C", "secondary": "#FF9500", "glow": "#FFD700"},
            "blue-cyan": {"primary": "#00BFFF", "secondary": "#0080FF", "glow": "#00FFFF"},
            "green-teal": {"primary": "#00FF88", "secondary": "#00BFA5", "glow": "#39FF14"},
            "purple-violet": {"primary": "#9B59B6", "secondary": "#6C3483", "glow": "#FF00FF"},
            "gold-amber": {"primary": "#FFD700", "secondary": "#FF8C00", "glow": "#FFF176"}
        }

        colors = color_map.get(color_theme, color_map["red-orange"])

        return {
            "visualization_type": viz_type,
            "colors": colors,
            "category": category,
            "animation_speed": "normal",
            "complexity": "high" if len(explanation_data.get("key_facts", [])) >= 4 else "medium",
            "elements": self._get_visualization_elements(viz_type, colors),
            "label": explanation_data.get("term", "")
        }

    def _get_visualization_elements(self, viz_type: str, colors: dict) -> list:
        """Return element definitions for different visualization types."""
        elements_map = {
            "fiber_diagram": [
                {"type": "muscle_fiber", "count": 6, "animated": True},
                {"type": "sarcomere_bands", "count": 8, "animated": True},
                {"type": "z_disc", "count": 4, "animated": False}
            ],
            "contraction_cycle": [
                {"type": "actin_filament", "count": 2, "animated": True},
                {"type": "myosin_head", "count": 4, "animated": True},
                {"type": "atp_molecule", "count": 3, "animated": True}
            ],
            "cross_section": [
                {"type": "epimysium", "count": 1, "animated": False},
                {"type": "fascicle", "count": 5, "animated": True},
                {"type": "endomysium", "count": 8, "animated": False}
            ],
            "neural_pathway": [
                {"type": "motor_neuron", "count": 1, "animated": True},
                {"type": "axon_branch", "count": 4, "animated": True},
                {"type": "neuromuscular_junction", "count": 4, "animated": True}
            ],
            "biochemical_cycle": [
                {"type": "molecule", "count": 6, "animated": True},
                {"type": "enzyme", "count": 3, "animated": True},
                {"type": "energy_arrow", "count": 4, "animated": True}
            ],
            "joint_mechanics": [
                {"type": "bone", "count": 2, "animated": False},
                {"type": "muscle_belly", "count": 2, "animated": True},
                {"type": "tendon", "count": 2, "animated": True}
            ],
            "cellular_diagram": [
                {"type": "cell_membrane", "count": 1, "animated": False},
                {"type": "organelle", "count": 5, "animated": True},
                {"type": "protein_complex", "count": 3, "animated": True}
            ]
        }
        return elements_map.get(viz_type, elements_map["fiber_diagram"])

    def _record_query(self, caller: Address, term: str, explanation: dict, graphical_data: dict):
        """Record a user's query in their history."""
        if caller not in self.query_history:
            history = []
        else:
            history = json.loads(self.query_history[caller])

        history.append({
            "term": term,
            "explanation": explanation,
            "graphical_data": graphical_data,
            "queried_at": gl.message.timestamp if hasattr(gl.message, 'timestamp') else 0
        })
        # Keep last 50 queries per user
        if len(history) > 50:
            history = history[-50:]
        self.query_history[caller] = json.dumps(history)

    # ─────────────────────── View Functions ───────────────────────

    @gl.public.view
    def get_cached_term(self, term: str) -> str:
        """Get cached explanation for a term (no AI call needed)."""
        term_lower = term.strip().lower()
        if term_lower in self.all_terms_cache:
            return self.all_terms_cache[term_lower]
        return json.dumps({"found": False, "term": term})

    @gl.public.view
    def get_user_history(self, user_address: Address) -> str:
        """Get study history for a specific user."""
        if user_address in self.query_history:
            return self.query_history[user_address]
        return "[]"

    @gl.public.view
    def get_recent_queries(self, limit: int) -> str:
        """Get recently queried terms across all users (from cache)."""
        terms = list(self.all_terms_cache.keys())
        return json.dumps(terms[-int(limit):] if limit else terms[-20:])

    @gl.public.view
    def get_stats(self) -> str:
        """Get global MYOGEN platform statistics."""
        return json.dumps({
            "total_queries": int(self.total_queries),
            "total_users": int(self.total_users),
            "terms_cached": len(list(self.all_terms_cache.keys())),
            "platform": "MYOGEN",
            "network": "GenLayer Studio",
            "chain_id": 61999
        })

    @gl.public.view
    def get_popular_terms(self) -> str:
        """Get all cached terms (acts as a catalog of studied terms)."""
        return json.dumps(list(self.all_terms_cache.keys()))
