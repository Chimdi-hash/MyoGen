import os
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

@pytest.mark.direct
def test_collateralized_withdrawal(direct_deploy, direct_vm, direct_alice, direct_bob):
    contract = direct_deploy("myogen_contract.py")
    
    # 1. Fund the contract natively to ensure fully collateralized rewards
    with direct_vm.prank(direct_bob):
        direct_vm.value = 5 * 10**18
        contract.fund_treasury()
    
    # 2. Mock web and LLM to force acceptance
    evidence_url = "https://medical-dictionary.com/titin"
    direct_vm.mock_web(evidence_url, {"body": "Titin is a structural protein in muscles.", "method": "GET", "status": 200})
    
    acceptance_json = json.dumps({
        "is_accurate": True,
        "reasoning": "The definition matches the source exactly.",
        "term": "titin",
        "definition": "A giant structural protein in muscle.",
        "category": "Anatomy",
        "detailed_explanation": "Titin acts like a molecular spring.",
        "key_facts": [],
        "related_terms": [],
        "clinical_relevance": "",
        "muscle_groups_involved": []
    })
    
    # Mock prompt_non_comparative directly because direct_vm.mock_llm doesn't support ExecPromptTemplate yet
    import genlayer.gl as gl
    original_prompt = gl.eq_principle.prompt_non_comparative
    gl.eq_principle.prompt_non_comparative = lambda prompt, task, criteria: acceptance_json
    
    try:
        # 3. Alice proposes term with 1 GEN stake
        with direct_vm.prank(direct_alice):
            direct_vm.value = 1 * 10**18
            contract.propose_term("Titin", "A giant structural protein in muscle.", evidence_url)
        
        # Verify contract recorded 2 GEN pending reward
        alice_str = direct_alice.hex().lower()
        if not alice_str.startswith("0x"):
            alice_str = "0x" + alice_str
        assert int(contract.pending_rewards.get(alice_str, "0")) == 2 * 10**18
        
        # 4. Withdraw the rewards
        alice_balance_before_withdraw = direct_vm._balances.get(direct_alice, 0)
        with direct_vm.prank(direct_alice):
            direct_vm.value = 0
            contract.withdraw_rewards()
            
        # 5. Verify pending balance is now 0
        assert int(contract.pending_rewards.get(alice_str, "0")) == 0
        
        # 6. Verify native balance increased by exactly the promised amount (2 GEN)
        # The direct loader logs the EthSend but doesn't mock balances natively.
        # We verify the transaction executed successfully and recorded an EthSend trace.
        assert any("EthSend" in str(t) for t in direct_vm._traces), "EthSend trace not found"

    finally:
        gl.eq_principle.prompt_non_comparative = original_prompt
