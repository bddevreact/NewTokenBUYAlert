import asyncio
import requests
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SolanaWalletMonitor:
    def __init__(self, wallet_address: str, bot_token: str, chat_id: str, rpc_url: str = "https://api.mainnet-beta.solana.com"):
        self.wallet_address = wallet_address
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.rpc_url = rpc_url
        self.processed_signatures = set()
        
    def get_recent_transactions(self, limit: int = 50) -> List[Dict]:
        """Get recent transactions for the monitored wallet using RPC"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [
                    self.wallet_address,
                    {"limit": limit}
                ]
            }
            
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    return data['result']
            return []
        except Exception as e:
            logger.error(f"Error fetching transactions: {e}")
            return []
    
    def get_transaction_details(self, signature: str) -> Optional[Dict]:
        """Get detailed transaction information using RPC with jsonParsed encoding"""
        try:
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
            
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    return data['result']
            return None
        except Exception as e:
            logger.error(f"Error fetching transaction details for {signature}: {e}")
            return None
    
    def is_new_token_created(self, transaction: Dict) -> bool:
        """Check if transaction creates a new token account - ANY match will trigger alert"""
        try:
            if not transaction or 'transaction' not in transaction:
                return False
                
            transaction_data = transaction['transaction']
            message = transaction_data.get('message', {})
            instructions = message.get('instructions', [])
            
            print(f"🔍 Analyzing transaction with {len(instructions)} instructions")
            
            # Check main instructions for token account creation
            for i, instruction in enumerate(instructions):
                program_id = instruction.get('program', '')
                parsed = instruction.get('parsed', {})
                instruction_type = parsed.get('type', '')
                
                print(f"📋 Instruction {i}: Program = {program_id}, Type = {instruction_type}")
                
                # ANY of these instructions will trigger alert
                if program_id == "spl-token" and instruction_type in [
                    "createAccount", 
                    "createTokenAccount",
                    "initializeAccount",
                    "initializeAccount3"
                ]:
                    print(f"✅ Found token account creation: {instruction_type}")
                    return True
                
                if program_id == "spl-associated-token-account" and instruction_type in [
                    "create",
                    "createIdempotent"
                ]:
                    print(f"✅ Found associated token account creation: {instruction_type}")
                    return True
            
            # Check inner instructions
            meta = transaction.get('meta', {})
            inner_instructions = meta.get('innerInstructions', [])
            
            print(f"📋 Checking {len(inner_instructions)} inner instruction groups")
            
            for inner_group in inner_instructions:
                for inner_instruction in inner_group.get('instructions', []):
                    program_id = inner_instruction.get('program', '')
                    parsed = inner_instruction.get('parsed', {})
                    instruction_type = parsed.get('type', '')
                    
                    print(f"📋 Inner Instruction: Program = {program_id}, Type = {instruction_type}")
                    
                    # ANY of these instructions will trigger alert
                    if program_id == "spl-token" and instruction_type in [
                        "createAccount", 
                        "createTokenAccount",
                        "initializeAccount",
                        "initializeAccount3"
                    ]:
                        print(f"✅ Found inner token account creation: {instruction_type}")
                        return True
                    
                    if program_id == "spl-associated-token-account" and instruction_type in [
                        "create",
                        "createIdempotent"
                    ]:
                        print(f"✅ Found inner associated token account creation: {instruction_type}")
                        return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking if transaction creates new token: {e}")
            return False
    
    def extract_new_token_info(self, transaction: Dict) -> Optional[Dict]:
        """Extract new token information from transaction"""
        try:
            if not transaction or 'meta' not in transaction:
                return None
                
            meta = transaction['meta']
            post_token_balances = meta.get('postTokenBalances', [])
            
            # Find first token with positive balance
            for balance in post_token_balances:
                mint = balance['mint']
                ui_amount = balance.get('uiTokenAmount', {}).get('uiAmount', 0)
                
                if ui_amount is not None and ui_amount > 0:
                    return {
                        'mint': mint,
                        'amount': balance.get('uiTokenAmount', {}).get('amount', '0'),
                        'decimals': balance.get('uiTokenAmount', {}).get('decimals', 0),
                        'ui_amount': ui_amount
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting new token info: {e}")
            return None
    
    def get_token_metadata(self, mint_address: str) -> Dict:
        """Get token metadata from Jupiter API"""
        try:
            url = f"https://quote-api.jup.ag/v6/tokens/{mint_address}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'name': data.get('name', 'Unknown'),
                    'symbol': data.get('symbol', 'Unknown'),
                    'decimals': data.get('decimals', 9)
                }
            
            return {
                'name': 'Unknown Token',
                'symbol': 'UNKNOWN',
                'decimals': 9
            }
            
        except Exception as e:
            logger.error(f"Error fetching token metadata for {mint_address}: {e}")
            return {
                'name': 'Unknown Token',
                'symbol': 'UNKNOWN',
                'decimals': 9
            }
    
    def get_token_age(self, mint_address: str) -> str:
        """Get token age by checking when it was first created"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [
                    mint_address,
                    {"limit": 1000}
                ]
            }
            
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and data['result']:
                    oldest_tx = data['result'][-1]
                    first_tx_time = oldest_tx.get('blockTime', 0)
                    current_time = time.time()
                    age_seconds = current_time - first_tx_time
                    
                    if age_seconds < 60:
                        return f"{int(age_seconds)} seconds"
                    elif age_seconds < 3600:
                        return f"{int(age_seconds/60)} minutes"
                    elif age_seconds < 86400:
                        return f"{int(age_seconds/3600)} hours"
                    else:
                        return f"{int(age_seconds/86400)} days"
            
            return "Unknown"
            
        except Exception as e:
            logger.error(f"Error getting token age for {mint_address}: {e}")
            return "Unknown"
    
    def format_amount(self, amount: str, decimals: int) -> str:
        """Format token amount with proper decimal places"""
        try:
            amount_int = int(amount)
            formatted_amount = amount_int / (10 ** decimals)
            return f"{formatted_amount:,.6f}".rstrip('0').rstrip('.')
        except:
            return amount
    
    def create_alert_message(self, token_info: Dict, token_metadata: Dict, token_age: str, signature: str) -> str:
        """Create formatted alert message"""
        amount = self.format_amount(token_info['amount'], token_info['decimals'])
        
        message = f"""🚨 *NEW TOKEN LAUNCH DETECTED!* 🚨

✅ *Token Name:* {token_metadata['name']} ({token_metadata['symbol']})
✅ *Mint Address:* `{token_info['mint']}`
✅ *Amount:* {amount} {token_metadata['symbol']}
✅ *Token Age:* {token_age}
✅ *TX Link:* https://solscan.io/tx/{signature}

*Wallet:* `{self.wallet_address}`
*Time:* {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"""
        return message.strip()
    
    def send_telegram_alert(self, message: str):
        """Send alert to Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                logger.info("✅ Telegram notification sent successfully")
                print("✅ Alert sent to Telegram!")
            else:
                logger.error(f"❌ Failed to send Telegram notification: {response.status_code}")
                print(f"❌ Failed to send to Telegram: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Error sending Telegram notification: {e}")
            print(f"❌ Error: {e}")
    
    def monitor_wallet(self, check_interval: int = 10):
        """Main monitoring loop - optimized to catch ALL new token purchases"""
        logger.info(f"Starting wallet monitoring for: {self.wallet_address}")
        logger.info(f"Check interval: {check_interval} seconds")
        print(f"🔍 Monitoring wallet: {self.wallet_address}")
        print(f"⏰ Check interval: {check_interval} seconds")
        print("🎯 Catching ALL new token purchases - no misses!")
        print("Press Ctrl+C to stop...")
        
        while True:
            try:
                # Get recent transactions (increased limit)
                transactions = self.get_recent_transactions(100)
                print(f"📊 Found {len(transactions)} recent transactions")
                
                new_token_count = 0
                
                for tx in transactions:
                    signature = tx['signature']
                    
                    # Skip if already processed
                    if signature in self.processed_signatures:
                        continue
                    
                    # Check if transaction is recent (within last 5 minutes)
                    tx_time = tx.get('blockTime', 0)
                    current_time = time.time()
                    if current_time - tx_time > 300:  # 5 minutes
                        print(f"⏰ Skipping old transaction: {signature[:8]}... (age: {int(current_time - tx_time)}s)")
                        continue
                    
                    print(f"🔍 Checking transaction: {signature[:8]}...")
                    
                    # Get detailed transaction info
                    tx_details = self.get_transaction_details(signature)
                    
                    if tx_details and self.is_new_token_created(tx_details):
                        token_info = self.extract_new_token_info(tx_details)
                        
                        if token_info:
                            new_token_count += 1
                            logger.info(f"New token launch detected: {token_info['mint']}")
                            print(f"🆕 NEW TOKEN LAUNCH DETECTED! (#{new_token_count})")
                            
                            # Get token metadata and age
                            token_metadata = self.get_token_metadata(token_info['mint'])
                            token_age = self.get_token_age(token_info['mint'])
                            
                            # Create and send alert
                            alert_message = self.create_alert_message(
                                token_info, token_metadata, token_age, signature
                            )
                            
                            self.send_telegram_alert(alert_message)
                    
                    # Mark as processed
                    self.processed_signatures.add(signature)
                
                if new_token_count > 0:
                    print(f"🎉 Found {new_token_count} new token purchases in this check!")
                else:
                    print("📭 No new token purchases found in this check")
                
                # Wait before next check
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                print("\n🛑 Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                print(f"❌ Error: {e}")
                time.sleep(check_interval)

def main():
    """Main function to run the wallet monitor"""
    # Configuration
    WALLET_ADDRESS = "gasTzr94Pmp4Gf8vknQnqxeYxdgwFjbgdJa4msYRpnB"
    TELEGRAM_BOT_TOKEN = "8009064444:AAHznjdM0wkphTbhsP_kOWOqxdatXS1w4C0"
    TELEGRAM_CHAT_ID = "6251161332"
    RPC_URL = "https://api.mainnet-beta.solana.com"
    CHECK_INTERVAL = 10  # Check every 10 seconds
    
    # Validate wallet address
    if len(WALLET_ADDRESS) < 32:
        print(f"❌ Invalid wallet address format. Expected at least 32 characters, got {len(WALLET_ADDRESS)}")
        return
    
    print(f"✅ Wallet address is valid: {WALLET_ADDRESS}")
    
    # Create and start monitor
    monitor = SolanaWalletMonitor(WALLET_ADDRESS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, RPC_URL)
    
    try:
        monitor.monitor_wallet(CHECK_INTERVAL)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🤖 Solana Wallet Monitor Bot")
    print("=" * 50)
    print("Monitoring for NEW TOKEN LAUNCHES!")
    print("=" * 50)
    
    # Run the bot
    main()