# Solana Wallet Monitor Bot - Setup Instructions 🚀

## Quick Setup (3 Steps)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Your Wallet
1. Open `.env` file
2. Replace `YOUR_WALLET_ADDRESS_HERE` with your actual Solana wallet address
3. Save the file

### 3. Run the Bot
```bash
python bot.py
```

## Configuration Options

### Basic Settings
- `WALLET_ADDRESS` - The wallet address to monitor (REQUIRED)
- `RPC_URL` - Solana RPC endpoint (optional)
- `CHECK_INTERVAL` - How often to check for new transactions (seconds)

### Notification Settings (Optional)
- `DISCORD_WEBHOOK_URL` - For Discord notifications
- `TELEGRAM_BOT_TOKEN` - For Telegram notifications
- `TELEGRAM_CHAT_ID` - Telegram chat ID
- Email settings for email notifications

## Example .env File
```
WALLET_ADDRESS=gasTzr94Pmp4Gf8vknQnqxeYxdgwFjbgdJa4msYRpnB
RPC_URL=https://api.mainnet-beta.solana.com
CHECK_INTERVAL=30
```

## Features
- ✅ Real-time wallet monitoring
- ✅ New token purchase detection
- ✅ Token metadata fetching
- ✅ Token age calculation
- ✅ Bengali alert messages
- ✅ Solana Explorer links

## Troubleshooting
- Make sure your wallet address is valid
- Check your internet connection
- Verify RPC endpoint is working
- Check logs for any errors

## Support
If you encounter any issues, check the logs or create an issue on GitHub.
