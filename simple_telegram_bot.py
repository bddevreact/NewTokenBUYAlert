import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
import requests
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey as PublicKey
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SolanaWalletMonitor:
    def __init__(self, wallet_address: str, bot_token: str, chat_id: str, rpc_url: str = "https://api.mainnet-beta.solana.com"):
        self.wallet_address = wallet_address
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.rpc_client = AsyncClient(rpc_url, timeout=30)
        self.wallet_pubkey = PublicKey.from_string(wallet_address)
        self.processed_signatures = set()
        
    async def get_recent_transactions(self, limit: int = 50) -> List[Dict]:
        """Get recent transactions for the monitored wallet"""
        try:
            signatures = await self.rpc_client.get_signatures_for_address(
                self.wallet_pubkey, 
                limit=limit
            )
            return signatures.value
        except Exception as e:
            logger.error(f"Error fetching transactions: {e}")
            return []
    
    async def get_transaction_details(self, signature: str) -> Optional[Dict]:
        """Get detailed transaction information"""
        try:
            tx_info = await self.rpc_client.get_transaction(signature)
            return tx_info.value
        except Exception as e:
            logger.error(f"Error fetching transaction details for {signature}: {e}")
            return None
    
    def is_token_purchase(self, transaction: Dict) -> bool:
        """Check if transaction is a token purchase"""
        try:
            if not transaction or 'meta' not in transaction:
                return False
                
            meta = transaction['meta']
            pre_balances = meta.get('preBalances', [])
            post_balances = meta.get('postBalances', [])
            
            # Check if SOL balance decreased (indicating a purchase)
            if len(pre_balances) > 0 and len(post_balances) > 0:
                sol_decrease = pre_balances[0] - post_balances[0]
                return sol_decrease > 0
                
            return False
        except Exception as e:
            logger.error(f"Error checking if transaction is token purchase: {e}")
            return False
    
    def extract_token_info(self, transaction: Dict) -> Optional[Dict]:
        """Extract token information from transaction"""
        try:
            if not transaction or 'meta' not in transaction:
                return None
                
            meta = transaction['meta']
            pre_token_balances = meta.get('preTokenBalances', [])
            post_token_balances = meta.get('postTokenBalances', [])
            
            # Find new token balances (tokens that weren't there before)
            new_tokens = []
            existing_mints = {balance['mint'] for balance in pre_token_balances}
            
            for balance in post_token_balances:
                mint = balance['mint']
                if mint not in existing_mints:
                    new_tokens.append({
                        'mint': mint,
                        'amount': balance.get('uiTokenAmount', {}).get('amount', '0'),
                        'decimals': balance.get('uiTokenAmount', {}).get('decimals', 0)
                    })
            
            return new_tokens[0] if new_tokens else None
            
        except Exception as e:
            logger.error(f"Error extracting token info: {e}")
            return None
    
    async def get_token_metadata(self, mint_address: str) -> Dict:
        """Get token metadata including name and creation date"""
        try:
            # Try to get token metadata from Jupiter API
            jupiter_url = f"https://quote-api.jup.ag/v6/tokens/{mint_address}"
            response = requests.get(jupiter_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'name': data.get('name', 'Unknown'),
                    'symbol': data.get('symbol', 'Unknown'),
                    'decimals': data.get('decimals', 9)
                }
            
            # Fallback to basic info
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
    
    async def get_token_age(self, mint_address: str) -> str:
        """Get token age by checking when it was first created"""
        try:
            # Get the first transaction for this mint address
            mint_pubkey = PublicKey(mint_address)
            signatures = await self.rpc_client.get_signatures_for_address(
                mint_pubkey, 
                limit=1
            )
            
            if signatures.value:
                first_tx = signatures.value[0]
                first_tx_time = first_tx.get('blockTime', 0)
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
        
        message = f"""🚨 *NEW TOKEN PURCHASE DETECTED!* 🚨

✅ *Token Name:* {token_metadata['name']} ({token_metadata['symbol']})
✅ *Mint Address:* `{token_info['mint']}`
✅ *Amount:* {amount} {token_metadata['symbol']}
✅ *Token Age:* {token_age}
✅ *TX Link:* https://solscan.io/tx/{signature}

*Wallet:* `{self.wallet_address}`
*Time:* {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"""
        return message.strip()
    
    async def send_telegram_alert(self, message: str):
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
    
    async def monitor_wallet(self, check_interval: int = 30):
        """Main monitoring loop"""
        logger.info(f"Starting wallet monitoring for: {self.wallet_address}")
        logger.info(f"Check interval: {check_interval} seconds")
        print(f"🔍 Monitoring wallet: {self.wallet_address}")
        print(f"⏰ Check interval: {check_interval} seconds")
        print("Press Ctrl+C to stop...")
        
        while True:
            try:
                # Get recent transactions
                transactions = await self.get_recent_transactions(50)
                
                for tx in transactions:
                    signature = tx['signature']
                    
                    # Skip if already processed
                    if signature in self.processed_signatures:
                        continue
                    
                    # Check if transaction is recent (within last 10 minutes)
                    tx_time = tx.get('blockTime', 0)
                    current_time = time.time()
                    if current_time - tx_time > 600:  # 10 minutes
                        continue
                    
                    # Get detailed transaction info
                    tx_details = await self.get_transaction_details(signature)
                    
                    if tx_details and self.is_token_purchase(tx_details):
                        token_info = self.extract_token_info(tx_details)
                        
                        if token_info:
                            logger.info(f"New token purchase detected: {token_info['mint']}")
                            print(f"🆕 New token purchase detected!")
                            
                            # Get token metadata and age
                            token_metadata = await self.get_token_metadata(token_info['mint'])
                            token_age = await self.get_token_age(token_info['mint'])
                            
                            # Create and send alert
                            alert_message = self.create_alert_message(
                                token_info, token_metadata, token_age, signature
                            )
                            
                            await self.send_telegram_alert(alert_message)
                    
                    # Mark as processed
                    self.processed_signatures.add(signature)
                
                # Wait before next check
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                print(f"❌ Error: {e}")
                await asyncio.sleep(check_interval)
    
    async def close(self):
        """Close the RPC client"""
        await self.rpc_client.close()

async def main():
    """Main function to run the wallet monitor"""
    # Configuration - Update these values
    WALLET_ADDRESS = "gasTzr94Pmp4Gf8vknQnqxeYxdgwFjbgdJa4msYRpnB"
    TELEGRAM_BOT_TOKEN = "8009064444:AAHznjdM0wkphTbhsP_kOWOqxdatXS1w4C0"
    TELEGRAM_CHAT_ID = "6251161332"
    RPC_URL = "https://api.mainnet-beta.solana.com"
    CHECK_INTERVAL = 30  # Check every 30 seconds
    
    # Validate wallet address
    try:
        # Convert string to bytes for PublicKey validation
        if len(WALLET_ADDRESS) >= 32:  # Base58 encoded address (32-44 chars)
            from solders.pubkey import Pubkey
            pubkey = Pubkey.from_string(WALLET_ADDRESS)
            print(f"✅ Wallet address is valid: {WALLET_ADDRESS}")
        else:
            print(f"❌ Invalid wallet address format. Expected at least 32 characters, got {len(WALLET_ADDRESS)}")
            return
    except Exception as e:
        print(f"❌ Invalid wallet address: {e}")
        return
    
    # Create and start monitor
    monitor = SolanaWalletMonitor(WALLET_ADDRESS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, RPC_URL)
    
    try:
        await monitor.monitor_wallet(CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
        print("\n🛑 Monitoring stopped by user")
    finally:
        await monitor.close()

if __name__ == "__main__":
    print("🤖 Solana Wallet Monitor Bot (Telegram Only)")
    print("=" * 50)
    
    # Run the bot
    asyncio.run(main())
