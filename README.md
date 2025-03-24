# meteora-wallet-analysis
Soft for analysis activity in meteora.ag
### You need to create keys:
1) On https://dashboard.quicknode.com/
   ![image](https://github.com/user-attachments/assets/fdecab6e-7f1c-4e3b-b721-6242ec37158e)
You should get http provider link. Example: `https://horse-yellow-lemon.solana-mainnet.quiknode.pro/23jk589df7g98sdf443k5j2o23h489df79g92834/`
3) On https://dashboard.helius.dev/
   ![image](https://github.com/user-attachments/assets/6da0663c-5b07-4883-9796-b503540a5600)
On Helius you should get Apy Key ID. Example: `87cv87sd-2h59-0v0c-2389-90cvb987987g`

### Setup variables
```
RPC_URL="Your_Quiknode_Link"
HELIUS_API_KEY="Your_HELIUS_API_KEY"
```
where
- `Your_Quiknode_Link` - The https API link from  https://dashboard.quicknode.com/ 
- `HELIUS_API_KEY` - API Key ID from https://dashboard.helius.dev/
  
Then add it to $HOME/.bash_profile:
```
echo 'export RPC_URL='\"${RPC_URL}\" >> $HOME/.bash_profile
echo 'export HELIUS_API_KEY='\"${HELIUS_API_KEY}\" >> $HOME/.bash_profile

source $HOME/.bash_profile
echo $RPC_URL $HELIUS_API_KEY
```
### Setup server
```
sudo apt update && sudo apt upgrade -y
sudo apt-get install nano mc git tmux
apt install python3-pip
pip install aiogram aiohttp cachetools
pip install requests python-dotenv
pip install requests-cache
pip install solana requests solders
pip install -U solana solders
pip install --force-reinstall -v "aiogram==2.23.1"
```
### Prepare directory
```
mkdir meteora-wallet-analysis
cd meteora-wallet-analysis
wget -O meteora.py https://raw.githubusercontent.com/AlexToTheSun/-meteora-wallet-analysis/refs/heads/main/meteora.py
wget -O kelsier_addresses.csv https://raw.githubusercontent.com/MeteoraAg/ops/refs/heads/main/kelsier_addresses.csv
```

## Start the software
```
 python3 meteora.py {wallet1} {wallet2} {wallet3} ... 
```
Example: `python3 meteora.py DefcyKc4yAjRsCLZjdxWuSUzVohXtLna9g22y3pBCm2z`
