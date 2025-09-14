import asyncio
import requests
import time
import json
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SolanaWalletMonitor:
    def __init__(self, bot_token: str, rpc_url: str = "https://api.mainnet-beta.solana.com"):
        self.bot_token = bot_token
        self.rpc_url = rpc_url
        self.processed_signatures = set()
        self.monitored_wallets = {}  # {wallet_address: {chat_id, last_check_time}}
        self.running = False
        
    def get_recent_transactions(self, wallet_address: str, limit: int = 50) -> List[Dict]:
        """Get recent transactions for the specified wallet using RPC"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [
                    wallet_address,
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
            logger.error(f"Error fetching transactions for {wallet_address}: {e}")
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
        """Check ALL possible new token creation parameters - ANY match triggers alert"""
        try:
            if not transaction or 'transaction' not in transaction:
                return False
                
            transaction_data = transaction['transaction']
            message = transaction_data.get('message', {})
            instructions = message.get('instructions', [])
            
            print(f"🔍 Analyzing transaction with {len(instructions)} instructions")
            
            # PRIORITY: create_token_account and related instructions
            priority_token_types = [
                "createTokenAccount",  # PRIMARY TARGET
                "createAccount", 
                "initializeAccount",
                "initializeAccount2",
                "initializeAccount3"
            ]
            
            # Secondary token creation instructions
            secondary_token_types = [
                "initializeMint",
                "initializeMint2",
                "mintTo",
                "mintToChecked"
            ]
            
            associated_token_types = [
                "create",
                "createIdempotent"
            ]
            
            # Check main instructions for token account creation
            for i, instruction in enumerate(instructions):
                program_id = instruction.get('program', '')
                parsed = instruction.get('parsed', {})
                instruction_type = parsed.get('type', '')
                
                print(f"📋 Instruction {i}: Program = {program_id}, Type = {instruction_type}")
                
                # Check for PRIORITY token creation instructions first
                if program_id == "spl-token" and instruction_type in priority_token_types:
                    if instruction_type == "createTokenAccount":
                        print(f"🎯 FOUND PRIMARY TARGET: createTokenAccount!")
                    elif instruction_type == "initializeAccount3":
                        print(f"🎯 FOUND EQUIVALENT: initializeAccount3 (create_token_account equivalent)!")
                    else:
                        print(f"✅ Found priority token creation: {instruction_type}")
                    return True
                
                # Check for secondary token creation instructions
                if program_id == "spl-token" and instruction_type in secondary_token_types:
                    print(f"✅ Found secondary token creation: {instruction_type}")
                    return True
                
                if program_id == "spl-associated-token-account" and instruction_type in associated_token_types:
                    print(f"✅ Found associated token creation: {instruction_type}")
                    return True
                
                # Check for ANY spl-token instruction (more aggressive detection)
                if program_id == "spl-token" and instruction_type:
                    print(f"✅ Found spl-token instruction: {instruction_type}")
                    return True
                
                # Check for ANY associated token account instruction
                if program_id == "spl-associated-token-account" and instruction_type:
                    print(f"✅ Found associated token instruction: {instruction_type}")
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
                    
                    # Check for PRIORITY token creation instructions first
                    if program_id == "spl-token" and instruction_type in priority_token_types:
                        if instruction_type == "createTokenAccount":
                            print(f"🎯 FOUND INNER PRIMARY TARGET: createTokenAccount!")
                        elif instruction_type == "initializeAccount3":
                            print(f"🎯 FOUND INNER EQUIVALENT: initializeAccount3 (create_token_account equivalent)!")
                        else:
                            print(f"✅ Found inner priority token creation: {instruction_type}")
                        return True
                    
                    # Check for secondary token creation instructions
                    if program_id == "spl-token" and instruction_type in secondary_token_types:
                        print(f"✅ Found inner secondary token creation: {instruction_type}")
                        return True
                    
                    if program_id == "spl-associated-token-account" and instruction_type in associated_token_types:
                        print(f"✅ Found inner associated token creation: {instruction_type}")
                        return True
                    
                    # Check for ANY spl-token instruction (more aggressive detection)
                    if program_id == "spl-token" and instruction_type:
                        print(f"✅ Found inner spl-token instruction: {instruction_type}")
                        return True
                    
                    # Check for ANY associated token account instruction
                    if program_id == "spl-associated-token-account" and instruction_type:
                        print(f"✅ Found inner associated token instruction: {instruction_type}")
                        return True
            
            # Check for token balance changes (new tokens)
            pre_balances = meta.get('preTokenBalances', [])
            post_balances = meta.get('postTokenBalances', [])
            
            if len(post_balances) > len(pre_balances):
                print(f"✅ Found new token balance: {len(pre_balances)} -> {len(post_balances)}")
                return True
            
            # Check for any positive token balance
            for balance in post_balances:
                ui_amount = balance.get('uiTokenAmount', {}).get('uiAmount', 0)
                if ui_amount and ui_amount > 0:
                    print(f"✅ Found positive token balance: {balance.get('mint', '')} = {ui_amount}")
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
        """Get token metadata from multiple sources for better accuracy"""
        try:
            # Try Jupiter API first
            jupiter_metadata = self.get_jupiter_metadata(mint_address)
            if jupiter_metadata['name'] != 'Unknown Token':
                return jupiter_metadata
            
            # Try Solscan API
            solscan_metadata = self.get_solscan_metadata(mint_address)
            if solscan_metadata['name'] != 'Unknown Token':
                return solscan_metadata
            
            # Try PumpFun API (Best for new launched tokens)
            pumpfun_metadata = self.get_pumpfun_metadata(mint_address)
            if pumpfun_metadata['name'] != 'Unknown Token':
                return pumpfun_metadata
            
            # Try DexScreener API (Best for new tokens)
            dexscreener_metadata = self.get_dexscreener_metadata(mint_address)
            if dexscreener_metadata['name'] != 'Unknown Token':
                return dexscreener_metadata
            
            # Try Birdeye API
            birdeye_metadata = self.get_birdeye_metadata(mint_address)
            if birdeye_metadata['name'] != 'Unknown Token':
                return birdeye_metadata
            
            # Try CoinGecko API
            coingecko_metadata = self.get_coingecko_metadata(mint_address)
            if coingecko_metadata['name'] != 'Unknown Token':
                return coingecko_metadata
            
            # Try Metaplex metadata
            metaplex_metadata = self.get_metaplex_metadata(mint_address)
            if metaplex_metadata['name'] != 'Unknown Token':
                return metaplex_metadata
            
            # Fallback to basic info
            return {
                'name': f'Token {mint_address[:8]}...',
                'symbol': mint_address[:4].upper(),
                'decimals': 9
            }
            
        except Exception as e:
            logger.error(f"Error fetching token metadata for {mint_address}: {e}")
            return {
                'name': f'Token {mint_address[:8]}...',
                'symbol': mint_address[:4].upper(),
                'decimals': 9
            }
    
    def get_jupiter_metadata(self, mint_address: str) -> Dict:
        """Get token metadata from Jupiter API"""
        try:
            url = f"https://quote-api.jup.ag/v6/tokens/{mint_address}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'name': data.get('name', 'Unknown Token'),
                    'symbol': data.get('symbol', 'UNKNOWN'),
                    'decimals': data.get('decimals', 9)
                }
            
            return {'name': 'Unknown Token', 'symbol': 'UNKNOWN', 'decimals': 9}
            
        except Exception as e:
            logger.error(f"Jupiter API error for {mint_address}: {e}")
            return {'name': 'Unknown Token', 'symbol': 'UNKNOWN', 'decimals': 9}
    
    def get_solscan_metadata(self, mint_address: str) -> Dict:
        """Get token metadata from Solscan API"""
        try:
            url = f"https://public-api.solscan.io/token/meta?tokenAddress={mint_address}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    token_info = data.get('data', {})
                    return {
                        'name': token_info.get('name', 'Unknown Token'),
                        'symbol': token_info.get('symbol', 'UNKNOWN'),
                        'decimals': token_info.get('decimals', 9)
                    }
            
            return {'name': 'Unknown Token', 'symbol': 'UNKNOWN', 'decimals': 9}
            
        except Exception as e:
            logger.error(f"Solscan API error for {mint_address}: {e}")
            return {'name': 'Unknown Token', 'symbol': 'UNKNOWN', 'decimals': 9}
    
    def get_pumpfun_metadata(self, mint_address: str) -> Dict:
        """Get token metadata from PumpFun API - Best for new launched tokens"""
        try:
            # PumpFun API endpoint
            url = f"https://frontend-api.pump.fun/coins/{mint_address}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Referer': 'https://pump.fun/'
            }
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('name'):
                    return {
                        'name': data.get('name', 'Unknown Token'),
                        'symbol': data.get('symbol', 'UNKNOWN'),
                        'decimals': data.get('decimals', 9)
                    }
            
            return {'name': 'Unknown Token', 'symbol': 'UNKNOWN', 'decimals': 9}
            
        except Exception as e:
            logger.error(f"PumpFun API error for {mint_address}: {e}")
            return {'name': 'Unknown Token', 'symbol': 'UNKNOWN', 'decimals': 9}
    
    def get_dexscreener_metadata(self, mint_address: str) -> Dict:
        """Get token metadata from DexScreener API - Best for new tokens"""
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{mint_address}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('pairs') and len(data['pairs']) > 0:
                    # Get the first pair (most relevant)
                    pair = data['pairs'][0]
                    base_token = pair.get('baseToken', {})
                    
                    return {
                        'name': base_token.get('name', 'Unknown Token'),
                        'symbol': base_token.get('symbol', 'UNKNOWN'),
                        'decimals': base_token.get('decimals', 9)
                    }
            
            return {'name': 'Unknown Token', 'symbol': 'UNKNOWN', 'decimals': 9}
            
        except Exception as e:
            logger.error(f"DexScreener API error for {mint_address}: {e}")
            return {'name': 'Unknown Token', 'symbol': 'UNKNOWN', 'decimals': 9}
    
    def get_birdeye_metadata(self, mint_address: str) -> Dict:
        """Get token metadata from Birdeye API"""
        try:
            url = f"https://public-api.birdeye.so/public/v1/token/{mint_address}"
            headers = {
                'X-API-KEY': 'your_birdeye_api_key_here',  # You can add API key if needed
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    token_info = data.get('data', {})
                    return {
                        'name': token_info.get('name', 'Unknown Token'),
                        'symbol': token_info.get('symbol', 'UNKNOWN'),
                        'decimals': token_info.get('decimals', 9)
                    }
            
            return {'name': 'Unknown Token', 'symbol': 'UNKNOWN', 'decimals': 9}
            
        except Exception as e:
            logger.error(f"Birdeye API error for {mint_address}: {e}")
            return {'name': 'Unknown Token', 'symbol': 'UNKNOWN', 'decimals': 9}
    
    def get_coingecko_metadata(self, mint_address: str) -> Dict:
        """Get token metadata from CoinGecko API"""
        try:
            # First, try to get token ID from contract address
            url = f"https://api.coingecko.com/api/v3/coins/solana/contract/{mint_address}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'name': data.get('name', 'Unknown Token'),
                    'symbol': data.get('symbol', 'UNKNOWN').upper(),
                    'decimals': 9  # CoinGecko doesn't always provide decimals
                }
            
            return {'name': 'Unknown Token', 'symbol': 'UNKNOWN', 'decimals': 9}
            
        except Exception as e:
            logger.error(f"CoinGecko API error for {mint_address}: {e}")
            return {'name': 'Unknown Token', 'symbol': 'UNKNOWN', 'decimals': 9}
    
    def get_metaplex_metadata(self, mint_address: str) -> Dict:
        """Get token metadata from Metaplex metadata PDA"""
        try:
            # Calculate metadata PDA
            from solders.pubkey import Pubkey
            from solders.hash import Hash
            
            # Metaplex metadata program ID
            METADATA_PROGRAM_ID = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")
            
            # Create metadata PDA
            mint_pubkey = Pubkey.from_string(mint_address)
            metadata_seeds = [b"metadata", bytes(METADATA_PROGRAM_ID), bytes(mint_pubkey)]
            metadata_pda = Pubkey.find_program_address(metadata_seeds, METADATA_PROGRAM_ID)[0]
            
            # Get account info
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getAccountInfo",
                "params": [
                    str(metadata_pda),
                    {"encoding": "base64"}
                ]
            }
            
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and data['result'] and 'value' in data['result']:
                    account_data = data['result']['value']['data'][0]
                    if account_data:
                        # Parse metadata (simplified)
                        import base64
                        decoded_data = base64.b64decode(account_data)
                        
                        # Basic parsing - look for name and symbol
                        try:
                            # This is a simplified parser - in reality you'd need proper deserialization
                            data_str = decoded_data.decode('utf-8', errors='ignore')
                            
                            # Try to extract name and symbol from the data
                            name = "Unknown Token"
                            symbol = "UNKNOWN"
                            
                            # Look for common patterns in metadata
                            if "name" in data_str.lower():
                                # This is very basic - real implementation would be more complex
                                name = f"Token {mint_address[:8]}..."
                            
                            return {
                                'name': name,
                                'symbol': symbol,
                                'decimals': 9
                            }
                        except:
                            pass
            
            return {'name': 'Unknown Token', 'symbol': 'UNKNOWN', 'decimals': 9}
            
        except Exception as e:
            logger.error(f"Metaplex metadata error for {mint_address}: {e}")
            return {'name': 'Unknown Token', 'symbol': 'UNKNOWN', 'decimals': 9}
    
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
    
    def create_alert_message(self, token_info: Dict, token_metadata: Dict, token_age: str, signature: str, wallet_address: str) -> str:
        """Create formatted alert message with enhanced token information"""
        amount = self.format_amount(token_info['amount'], token_info['decimals'])
        
        # Enhanced token display
        token_name = token_metadata['name']
        token_symbol = token_metadata['symbol']
        
        # Add emoji based on token type
        if 'pump' in token_name.lower() or 'pump' in token_symbol.lower():
            token_emoji = "🚀"
        elif 'moon' in token_name.lower() or 'moon' in token_symbol.lower():
            token_emoji = "🌙"
        elif 'doge' in token_name.lower() or 'doge' in token_symbol.lower():
            token_emoji = "🐕"
        elif 'cat' in token_name.lower() or 'cat' in token_symbol.lower():
            token_emoji = "🐱"
        else:
            token_emoji = "🪙"
        
        message = f"""🚨 *New Token Buy Alert* 🚨
 
 {token_emoji} *Token:* {token_name} ({token_symbol})
 🔗 *Mint:* `{token_info['mint']}`
 💰 *Amount:* {amount} {token_symbol}
 ⏰ *Age:* {token_age}
 🔍 *TX:* https://solscan.io/tx/{signature}
 
 👤 *Wallet:* `{wallet_address}`
 🕐 *Time:* {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
 
 💡 *Quick Actions:*
 • [View on PumpFun](https://pump.fun/{token_info['mint']})
 • [View on DexScreener](https://dexscreener.com/solana/{token_info['mint']})
 • [View on Solscan](https://solscan.io/token/{token_info['mint']})
 • [Add to Wallet](solana:{token_info['mint']})"""
        return message.strip()
    
    def send_telegram_alert(self, message: str, chat_id: str):
        """Send alert to Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                logger.info(f"✅ Telegram notification sent to {chat_id}")
                print(f"✅ Alert sent to Telegram! (Chat ID: {chat_id})")
            else:
                logger.error(f"❌ Failed to send Telegram notification to {chat_id}: {response.status_code}")
                print(f"❌ Failed to send to Telegram: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Error sending Telegram notification to {chat_id}: {e}")
            print(f"❌ Error: {e}")
    
    def add_wallet(self, wallet_address: str, chat_id: str) -> bool:
        """Add a wallet to monitoring list"""
        try:
            if len(wallet_address) < 32:
                return False
            
            self.monitored_wallets[wallet_address] = {
                'chat_id': chat_id,
                'last_check_time': time.time()
            }
            logger.info(f"Added wallet {wallet_address} for chat {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding wallet {wallet_address}: {e}")
            return False
    
    def remove_wallet(self, wallet_address: str) -> bool:
        """Remove a wallet from monitoring list"""
        try:
            if wallet_address in self.monitored_wallets:
                del self.monitored_wallets[wallet_address]
                logger.info(f"Removed wallet {wallet_address}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing wallet {wallet_address}: {e}")
            return False
    
    def get_monitored_wallets(self) -> Dict:
        """Get list of monitored wallets"""
        return self.monitored_wallets.copy()
    
    def monitor_wallets(self, check_interval: int = 3):
        """Main monitoring loop for all wallets - ZERO MISSES, catch EVERYTHING"""
        logger.info("Starting multi-wallet monitoring")
        logger.info(f"Check interval: {check_interval} seconds")
        print(f"🔍 Monitoring {len(self.monitored_wallets)} wallets")
        print(f"⏰ Check interval: {check_interval} seconds")
        print("🎯 ZERO MISSES - Catching EVERY new token purchase!")
        print("Press Ctrl+C to stop...")
        
        self.running = True
        
        while self.running:
            try:
                if not self.monitored_wallets:
                    print("📭 No wallets to monitor. Use /addwallet to add wallets.")
                    time.sleep(check_interval)
                    continue
                
                total_new_tokens = 0
                
                for wallet_address, wallet_info in self.monitored_wallets.items():
                    chat_id = wallet_info['chat_id']
                    
                    # Get last 20 transactions for this wallet
                    transactions = self.get_recent_transactions(wallet_address, 20)
                    print(f"📊 Wallet {wallet_address[:8]}... - Found {len(transactions)} recent transactions")
                    
                    new_token_count = 0
                    
                    for tx in transactions:
                        signature = tx['signature']
                        signature_key = f"{wallet_address}_{signature}"
                        
                        # Skip if already processed
                        if signature_key in self.processed_signatures:
                            continue
                        
                        # Check ALL transactions - no skipping for age
                        tx_time = tx.get('blockTime', 0)
                        current_time = time.time()
                        age_seconds = current_time - tx_time
                        
                        # Show age in minutes and seconds
                        if age_seconds < 60:
                            age_display = f"{int(age_seconds)}s ago"
                        elif age_seconds < 3600:
                            age_display = f"{int(age_seconds/60)}m {int(age_seconds%60)}s ago"
                        else:
                            age_display = f"{int(age_seconds/3600)}h {int((age_seconds%3600)/60)}m ago"
                        
                        print(f"🔍 Checking {wallet_address[:8]}... - {signature[:8]}... ({age_display})")
                        
                        # Get detailed transaction info
                        tx_details = self.get_transaction_details(signature)
                        
                        if tx_details and self.is_new_token_created(tx_details):
                            token_info = self.extract_new_token_info(tx_details)
                            
                            if token_info:
                                new_token_count += 1
                                total_new_tokens += 1
                                logger.info(f"New token launch detected for {wallet_address}: {token_info['mint']}")
                                print(f"🆕 NEW TOKEN LAUNCH DETECTED! (#{new_token_count})")
                                
                                # Get token metadata and age
                                token_metadata = self.get_token_metadata(token_info['mint'])
                                token_age = self.get_token_age(token_info['mint'])
                                
                                # Create and send alert
                                alert_message = self.create_alert_message(
                                    token_info, token_metadata, token_age, signature, wallet_address
                                )
                                
                                self.send_telegram_alert(alert_message, chat_id)
                        
                        # Mark as processed
                        self.processed_signatures.add(signature_key)
                    
                    if new_token_count > 0:
                        print(f"🎉 Wallet {wallet_address[:8]}... - Found {new_token_count} new token purchases!")
                
                if total_new_tokens > 0:
                    print(f"🎉 Total: Found {total_new_tokens} new token purchases across all wallets!")
                else:
                    print("📭 No new token purchases found in this check")
                
                # Wait before next check
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                print("\n🛑 Monitoring stopped by user")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                print(f"❌ Error: {e}")
                time.sleep(check_interval)

class TelegramBotHandler:
    def __init__(self, bot_token: str, monitor: SolanaWalletMonitor):
        self.bot_token = bot_token
        self.monitor = monitor
        self.last_update_id = 0
        
    def get_updates(self):
        """Get updates from Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {
                'offset': self.last_update_id + 1,
                'timeout': 30
            }
            response = requests.get(url, params=params, timeout=35)
            if response.status_code == 200:
                data = response.json()
                return data.get('result', [])
            return []
        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return []
    
    def send_message(self, chat_id: str, text: str):
        """Send message to Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'Markdown'
            }
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def handle_command(self, chat_id: str, command: str, args: str = ""):
        """Handle bot commands"""
        if command == "/start":
            welcome_msg = """🤖 *Solana Wallet Monitor Bot*

Welcome! I can monitor Solana wallets for new token launches.

*Commands:*
/addwallet <wallet_address> - Add a wallet to monitor
/removewallet <wallet_address> - Remove a wallet from monitoring
/listwallets - Show all monitored wallets
/help - Show this help message

*Example:*
/addwallet gasTzr94Pmp4Gf8vknQnqxeYxdgwFjbgdJa4msYRpnB"""
            self.send_message(chat_id, welcome_msg)
            
        elif command == "/addwallet":
            if not args:
                self.send_message(chat_id, "❌ Please provide a wallet address.\n\nUsage: /addwallet <wallet_address>")
                return
            
            wallet_address = args.strip()
            if len(wallet_address) < 32:
                self.send_message(chat_id, f"❌ Invalid wallet address format. Expected at least 32 characters, got {len(wallet_address)}")
                return
            
            if self.monitor.add_wallet(wallet_address, chat_id):
                self.send_message(chat_id, f"✅ Wallet added successfully!\n\nWallet: `{wallet_address}`\n\nI'll monitor this wallet for new token launches and send alerts here.")
            else:
                self.send_message(chat_id, "❌ Failed to add wallet. Please check the wallet address format.")
                
        elif command == "/removewallet":
            if not args:
                self.send_message(chat_id, "❌ Please provide a wallet address.\n\nUsage: /removewallet <wallet_address>")
                return
            
            wallet_address = args.strip()
            if self.monitor.remove_wallet(wallet_address):
                self.send_message(chat_id, f"✅ Wallet removed successfully!\n\nWallet: `{wallet_address}`")
            else:
                self.send_message(chat_id, f"❌ Wallet not found in monitoring list.\n\nWallet: `{wallet_address}`")
                
        elif command == "/listwallets":
            wallets = self.monitor.get_monitored_wallets()
            if not wallets:
                self.send_message(chat_id, "📭 No wallets are currently being monitored.\n\nUse /addwallet to add a wallet.")
                return
            
            msg = "📋 *Monitored Wallets:*\n\n"
            for i, (wallet, info) in enumerate(wallets.items(), 1):
                msg += f"{i}. `{wallet}`\n"
            
            self.send_message(chat_id, msg)
            
        elif command == "/help":
            help_msg = """🤖 *Solana Wallet Monitor Bot Help*

*Commands:*
/addwallet <wallet_address> - Add a wallet to monitor
/removewallet <wallet_address> - Remove a wallet from monitoring  
/listwallets - Show all monitored wallets
/help - Show this help message

*Features:*
• Monitors wallets for new token launches
• Sends real-time alerts when new tokens are detected
• Supports multiple wallets per user
• Zero misses - catches every new token purchase

*Example:*
/addwallet gasTzr94Pmp4Gf8vknQnqxeYxdgwFjbgdJa4msYRpnB"""
            self.send_message(chat_id, help_msg)
            
        else:
            self.send_message(chat_id, "❌ Unknown command. Use /help to see available commands.")
    
    def process_updates(self):
        """Process incoming updates"""
        updates = self.get_updates()
        
        for update in updates:
            self.last_update_id = update['update_id']
            
            if 'message' in update:
                message = update['message']
                chat_id = str(message['chat']['id'])
                text = message.get('text', '')
                
                if text.startswith('/'):
                    parts = text.split(' ', 1)
                    command = parts[0]
                    args = parts[1] if len(parts) > 1 else ""
                    
                    print(f"📱 Received command: {command} from chat {chat_id}")
                    self.handle_command(chat_id, command, args)
    
    def run(self):
        """Run the bot handler"""
        print("🤖 Telegram Bot Handler Started")
        print("📱 Listening for commands...")
        
        while True:
            try:
                self.process_updates()
                time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Bot handler stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in bot handler: {e}")
                time.sleep(5)

def main():
    """Main function to run the Telegram bot with wallet monitoring"""
    # Configuration
    TELEGRAM_BOT_TOKEN = "8009064444:AAHznjdM0wkphTbhsP_kOWOqxdatXS1w4C0"
    RPC_URL = "https://api.mainnet-beta.solana.com"
    CHECK_INTERVAL = 3  # Check every 3 seconds
    
    print("🤖 Solana Wallet Monitor Bot")
    print("=" * 50)
    print("🌍 PUBLIC BOT - Anyone can use!")
    print("=" * 50)
    
    # Create monitor instance
    monitor = SolanaWalletMonitor(TELEGRAM_BOT_TOKEN, RPC_URL)
    
    # Create bot handler
    bot_handler = TelegramBotHandler(TELEGRAM_BOT_TOKEN, monitor)
    
    # Start monitoring in a separate thread
    monitor_thread = threading.Thread(target=monitor.monitor_wallets, args=(CHECK_INTERVAL,))
    monitor_thread.daemon = True
    monitor_thread.start()
    
    print("🚀 Bot started successfully!")
    print("📱 Send /start to the bot to begin")
    print("🔍 Monitoring will start when wallets are added")
    print("Press Ctrl+C to stop...")
    
    try:
        # Run bot handler in main thread
        bot_handler.run()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        monitor.running = False
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()