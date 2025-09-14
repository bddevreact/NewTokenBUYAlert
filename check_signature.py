import requests
import json

def check_transaction(signature):
    """Check a specific transaction signature"""
    rpc_url = "https://api.mainnet-beta.solana.com"
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [
            signature,
            {
                "encoding": "jsonParsed",
                "maxSupportedTransactionVersion": 0,
                "commitment": "confirmed"
            }
        ]
    }
    
    try:
        response = requests.post(rpc_url, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'result' in data:
                return data['result']
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def analyze_transaction(transaction):
    """Analyze transaction for create_token_account"""
    if not transaction:
        print("❌ No transaction data found")
        return
    
    print(f"🔍 Transaction Analysis:")
    print(f"Signature: {transaction.get('transaction', {}).get('signatures', ['N/A'])[0]}")
    
    # Check main instructions
    instructions = transaction.get('transaction', {}).get('message', {}).get('instructions', [])
    print(f"\n📋 Main Instructions ({len(instructions)}):")
    
    for i, instruction in enumerate(instructions):
        program_id = instruction.get('program', '')
        parsed = instruction.get('parsed', {})
        instruction_type = parsed.get('type', '')
        
        print(f"  {i}: Program = {program_id}, Type = {instruction_type}")
        
        if program_id == "spl-token" and instruction_type == "createTokenAccount":
            print(f"    ✅ FOUND createTokenAccount!")
            print(f"    Info: {parsed.get('info', {})}")
    
    # Check inner instructions
    meta = transaction.get('meta', {})
    inner_instructions = meta.get('innerInstructions', [])
    print(f"\n📋 Inner Instructions ({len(inner_instructions)} groups):")
    
    for group_idx, inner_group in enumerate(inner_instructions):
        print(f"  Group {group_idx}:")
        for inner_instruction in inner_group.get('instructions', []):
            program_id = inner_instruction.get('program', '')
            parsed = inner_instruction.get('parsed', {})
            instruction_type = parsed.get('type', '')
            
            print(f"    Program = {program_id}, Type = {instruction_type}")
            
            if program_id == "spl-token" and instruction_type == "createTokenAccount":
                print(f"    ✅ FOUND inner createTokenAccount!")
                print(f"    Info: {parsed.get('info', {})}")
    
    # Check token balances
    pre_balances = meta.get('preTokenBalances', [])
    post_balances = meta.get('postTokenBalances', [])
    
    print(f"\n📊 Token Balances:")
    print(f"  Pre: {len(pre_balances)} tokens")
    print(f"  Post: {len(post_balances)} tokens")
    
    for balance in post_balances:
        mint = balance.get('mint', '')
        ui_amount = balance.get('uiTokenAmount', {}).get('uiAmount', 0)
        print(f"    {mint}: {ui_amount}")

if __name__ == "__main__":
    signature = "3X7NzL8SeVGqbNN54DKBmDdUh4sTimG35dkUdzwuY1MzxiySVDLKkAi6LHfmoLopNtmpk8dZS3ZUudwfDpQKXjPq"
    
    print(f"🔍 Checking signature: {signature}")
    print("=" * 80)
    
    transaction = check_transaction(signature)
    analyze_transaction(transaction)
