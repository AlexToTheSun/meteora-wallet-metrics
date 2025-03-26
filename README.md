# meteora-wallet-metrics

Script shows Meteora wallet metrics that may be interesting to the LP Army community. There are 3 options for presenting analytics to choose from:
```bash
 Choose output format:
1. CSV file
2. Text report
3. Both formats
Enter your choice (1-3): # Enter the number

1 Wallet:
9BY...NHR
💵 Total fees claimed: $135.71
🛀 Pools with claimed fees: 12
🗓 First tx: 22.12.2024
📅 Number of active weeks: 11
📅 Number of active months: 3
🖼 LP Army Certificate сNFT: Yes
🚫 Blacklist kelsier_addresses: No

CSV report generated: Meteora_20250325_0.csv
# CSV file will be generated in the script folder.
```
## Overview
In this tutorial
- [What can this script do?](https://github.com/AlexToTheSun/meteora-wallet-metrics/blob/main#what-can-this-script-do)
- [1) Create Quicknode and Helius keys](https://github.com/AlexToTheSun/meteora-wallet-metrics/blob/main/README.md#1-create-quicknode-and-helius-keys)
- [2) Installation](https://github.com/AlexToTheSun/meteora-wallet-metrics/blob/main/README.md#2-installation)
- [Auto install script if you use Ubuntu](https://github.com/AlexToTheSun/meteora-wallet-metrics/blob/main/README.md#auto-install-script-if-you-use-ubuntu)
- [To contact us](https://github.com/AlexToTheSun/meteora-wallet-metrics/blob/main/README.md#to-contact-us)

### What can this script do?

- You can check several wallets at once. Enter them separated by a space.
<img width="843" alt="image" src="https://github.com/user-attachments/assets/a794e3ed-c2f6-4604-b79a-5412fb5a4c24" />

### 1) Create [Quicknode](https://dashboard.quicknode.com/) and [Helius](https://dashboard.helius.dev/) keys.
First you need to create these keys.
1) On https://dashboard.quicknode.com/
   ![image](https://github.com/user-attachments/assets/fdecab6e-7f1c-4e3b-b721-6242ec37158e)
You should get http provider link.           
Example: `https://horse-yellow-lemon.solana-mainnet.quiknode.pro/23jk589df7g98sdf443k5j2o23h489df79g92834/`

2) On https://dashboard.helius.dev/
   ![image](https://github.com/user-attachments/assets/6da0663c-5b07-4883-9796-b503540a5600)
On Helius you should get Apy Key ID.           
Example: `87cv87sd-2h59-0v0c-2389-90cvb987987g`

### 2) Installation
#### Install libraries:
```
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip
pip install -r requirements.txt
```
#### Setup variables:
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

#### Prepare directory and files:
```
mkdir meteora-wallet-analysis
cd meteora-wallet-analysis
wget -O meteora.py https://raw.githubusercontent.com/AlexToTheSun/meteora-wallet-metrics/refs/heads/main/meteora.py
wget -O kelsier_addresses.csv https://raw.githubusercontent.com/MeteoraAg/ops/refs/heads/main/kelsier_addresses.csv
```
kelsier_addresses.csv is [here](https://github.com/MeteoraAg/ops)

#### Start the script:
Enter wallets separated by spaces.
```
 python3 meteora.py {wallet1} {wallet2} {wallet3} ... 
```
Example: `python3 meteora.py DefcyKc4yAjRsCLZjdxWuSUzVohXtLna9g22y3pBCm2z`.

Text Result:

![Снимок экрана 2025-03-25 135341111](https://github.com/user-attachments/assets/88857d8f-c2e3-425b-8cf7-56441072633b)

CSV file:

![426469534-a2220ae4-e82b-4362-b4f3-084a535a31fc](https://github.com/user-attachments/assets/8879a12f-d566-4311-bd6d-c2aaea748927)



## Auto install script if you use Ubuntu
```
wget -O ubunut_setup_script.sh https://raw.githubusercontent.com/AlexToTheSun/meteora-wallet-metrics/refs/heads/main/ubunut_setup_script.sh && chmod +x ubunut_setup_script.sh && ./ubunut_setup_script.sh
```

## To contact us
Discord: `alexturetskiy`

Telegram: https://t.me/AlexTuretskiy

Telegram channel: https://t.me/meteora_wallet_metrics

Twitter: https://twitter.com/Alex007hi
