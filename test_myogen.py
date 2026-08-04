import os
import builtins
import pytest
import json

# Workaround for genlayer-test Windows PermissionError on os.unlink temp file
original_unlink = os.unlink
def safe_unlink(path, *args, **kwargs):
    try:
        original_unlink(path, *args, **kwargs)
    except PermissionError:
        pass
os.unlink = safe_unlink

def test_proposal_accepted_and_withdrawn(direct_deploy, direct_vm, direct_alice, direct_bob):
    contract = direct_deploy("myogen_contract.py")
    
    # 1. Fund treasury from Bob
    with direct_vm.prank(direct_bob):
        direct_vm.value = 10 * 10**18
        contract.fund_treasury()
    assert contract.treasury == 10 * 10**18
    
    # 2. Mock web and llm for Alice's proposal
    evidence_url = "https://medical-dictionary.com/titin"
    direct_vm.mock_web(evidence_url, {"body": "Titin is a structural protein in muscles.", "method": "GET", "status": 200})
    
    import genlayer.gl as gl
    
    # We mock prompt_non_comparative directly because direct_vm.mock_llm doesn't support ExecPromptTemplate yet
    acceptance_json = json.dumps({
        "is_accurate": True,
        "reasoning": "The definition matches the source exactly.",
        "term": "titin",
        "definition": "A giant structural protein in muscle.",
        "category": "Anatomy & Physiology",
        "detailed_explanation": "Titin acts like a molecular spring.",
        "key_facts": ["Largest known protein"],
        "related_terms": ["sarcomere"],
        "clinical_relevance": "Titin mutations cause cardiomyopathies.",
        "muscle_groups_involved": ["skeletal", "cardiac"]
    })
    
    # Save the original method to restore later just in case
    original_prompt_non_comparative = gl.eq_principle.prompt_non_comparative
    
    # Create a dummy return value that mimics Lazy/string depending on what the contract expects
    # In myogen_contract.py we do: result_str = gl.eq_principle.prompt_non_comparative(...)
    gl.eq_principle.prompt_non_comparative = lambda prompt, task, criteria: acceptance_json
    
    try:
        # 3. Alice proposes term with 1 GEN stake
        with direct_vm.prank(direct_alice):
            direct_vm.value = 1 * 10**18
            contract.propose_term("Titin", "A giant structural protein in muscle.", evidence_url)
    
        # The stake is 1 GEN. Wait, if accepted, the reward is 2 GEN. So treasury loses 1 GEN.
        # We assert that the pending rewards for Alice is now 2 GEN.
        # Alice's address is lower case string
        alice_str = direct_alice.hex().lower()
        if not alice_str.startswith("0x"):
            alice_str = "0x" + alice_str
    
        pending_rewards = int(contract.pending_rewards.get(alice_str, "0"))
        assert pending_rewards == 2 * 10**18
        assert contract.treasury == 9 * 10**18  # Deducted 1 GEN reward
    
        # 4. Alice withdraws the reward
        with direct_vm.prank(direct_alice):
            # We don't send value here
            direct_vm.value = 0
            contract.withdraw_rewards()
        
        pending_rewards_after = int(contract.pending_rewards.get(alice_str, "0"))
        assert pending_rewards_after == 0
        # On the blockchain, Alice's GEN balance should have increased by 2 GEN, 
        # but we don't need to test GenVM's native transfer mechanism internally here, 
        # just that the contract executed it successfully without throwing.
    finally:
        gl.eq_principle.prompt_non_comparative = original_prompt_non_comparative
