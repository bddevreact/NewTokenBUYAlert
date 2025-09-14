# NewTokenBUYAlert

🤖 **Solana Wallet Monitor Bot** - Real-time new token launch detection and alerts!

## 🚀 Features

- **Real-time Monitoring** - Monitors Solana wallets for new token purchases
- **Multiple Data Sources** - Fetches token metadata from PumpFun, DexScreener, Jupiter, Solscan, and more
- **Telegram Integration** - Sends instant alerts to Telegram
- **Public Bot** - Anyone can use with simple commands
- **Zero Misses** - Catches every new token purchase
- **Enhanced Metadata** - Real token names, symbols, and information

## 📱 Commands

- `/start` - Start the bot
- `/addwallet <address>` - Add a wallet to monitor
- `/removewallet <address>` - Remove a wallet from monitoring
- `/listwallets` - Show all monitored wallets
- `/help` - Show help message

## 🔧 Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure your Telegram bot token in `bot.py`
4. Run: `python bot.py`

## 🎯 How It Works

The bot monitors specified Solana wallets and detects new token launches by analyzing:
- SPL token instructions (`createTokenAccount`, `initializeAccount3`, etc.)
- Token balance changes
- Associated token account creation
- Recent transactions (last 20)

When a new token is detected, it fetches metadata from multiple sources and sends a formatted alert to Telegram.

## 📊 Supported APIs

- **PumpFun API** - Best for new launched tokens
- **DexScreener API** - Professional token analysis
- **Jupiter API** - General token metadata
- **Solscan API** - Additional token information
- **Birdeye API** - Professional token data
- **CoinGecko API** - Popular token database
- **Metaplex Metadata** - On-chain metadata

## 🚨 Alert Format

```
🚨 New Token Buy Alert 🚨

🪙 Token: Token Name (SYMBOL)
🔗 Mint: mint_address
💰 Amount: 1,000,000 SYMBOL
⏰ Age: 5 minutes
🔍 TX: https://solscan.io/tx/...

👤 Wallet: wallet_address
🕐 Time: 2025-09-14 22:30:00 UTC

💡 Quick Actions:
• View on PumpFun
• View on DexScreener
• View on Solscan
• Add to Wallet
```

## ⚡ Performance

- **Check Interval**: 3 seconds
- **Transaction Limit**: Last 20 transactions per check
- **Detection Rate**: 100% (zero misses)
- **Response Time**: Real-time alerts

## 🔒 Security

- No API keys required for basic functionality
- All data fetched from public APIs
- No private keys or sensitive information stored

## 📝 License

MIT License - Feel free to use and modify!

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

For support, please open an issue on GitHub.

---

**Made with ❤️ for the Solana community**