# meteora-wallet-analysis
Soft for analysis activity in meteora.ag
<img width="843" alt="image" src="https://github.com/user-attachments/assets/a794e3ed-c2f6-4604-b79a-5412fb5a4c24" />

### 1) You need to create [Quicknode](https://dashboard.quicknode.com/) and [Helius](https://dashboard.helius.dev/) keys:
1) On https://dashboard.quicknode.com/
   ![image](https://github.com/user-attachments/assets/fdecab6e-7f1c-4e3b-b721-6242ec37158e)
You should get http provider link.           
Example: `https://horse-yellow-lemon.solana-mainnet.quiknode.pro/23jk589df7g98sdf443k5j2o23h489df79g92834/`

2) On https://dashboard.helius.dev/
   ![image](https://github.com/user-attachments/assets/6da0663c-5b07-4883-9796-b503540a5600)
On Helius you should get Apy Key ID.           
Example: `87cv87sd-2h59-0v0c-2389-90cvb987987g`

### 2) Setup server:
```
sudo apt update && sudo apt upgrade -y
sudo apt-get install nano mc git tmux
sudo apt install python3-pip
pip install aiogram aiohttp cachetools
pip install requests python-dotenv
pip install requests-cache
pip install solana requests solders
pip install -U solana solders
pip install --force-reinstall -v "aiogram==2.23.1"
```
### 3) Setup variables:
```
RPC_URL="Your_Quiknode_Link"
HELIUS_API_KEY="Your_HELIUS_API_KEY"
```
Where:
- `Your_Quiknode_Link` - The https API link from  https://dashboard.quicknode.com/ 
- `HELIUS_API_KEY` - API Key ID from https://dashboard.helius.dev/
  
Then add it to $HOME/.bash_profile:
```
echo 'export RPC_URL='\"${RPC_URL}\" >> $HOME/.bash_profile
echo 'export HELIUS_API_KEY='\"${HELIUS_API_KEY}\" >> $HOME/.bash_profile
source $HOME/.bash_profile
echo $RPC_URL $HELIUS_API_KEY
```

### 4) Prepare directory and files:
```
mkdir meteora-wallet-analysis
cd meteora-wallet-analysis
wget -O meteora.py https://raw.githubusercontent.com/AlexToTheSun/-meteora-wallet-analysis/refs/heads/main/meteora.py
wget -O kelsier_addresses.csv https://raw.githubusercontent.com/MeteoraAg/ops/refs/heads/main/kelsier_addresses.csv
```
kelsier_addresses.csv is [here](https://github.com/MeteoraAg/ops)

### 5) Start the script:
Enter wallets separated by spaces.
```
 python3 meteora.py {wallet1} {wallet2} {wallet3} ... 
```
Example: `python3 meteora.py DefcyKc4yAjRsCLZjdxWuSUzVohXtLna9g22y3pBCm2z`

The script will offer 3 report options, enter the number and press enter:
```
Choose output format:
1. CSV file
2. Text report
3. Both formats
```
CSV file is generated in the folder with the script.

