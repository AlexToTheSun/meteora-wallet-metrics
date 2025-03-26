#!/bin/bash

# Function for input validation
validate_input() {
    if [ -z "$1" ]; then
        echo "Error: This value cannot be empty!"
        exit 1
    fi
}

# System update
sudo apt update && sudo apt upgrade -y

# Installing pip
sudo apt install python3-pip -y

# Query variables
read -p "Enter Your Quiknode RPC URL: " RPC_URL
validate_input "$RPC_URL"

read -p "Enter Your HELIUS API KEY: " HELIUS_API_KEY
validate_input "$HELIUS_API_KEY"

# Export variables
echo "export RPC_URL=\"$RPC_URL\"" >> ~/.bash_profile
echo "export HELIUS_API_KEY=\"$HELIUS_API_KEY\"" >> ~/.bash_profile
source ~/.bash_profile

# Checking variables
echo -e "\nConfigured environment variables:"
echo "RPC_URL: $RPC_URL"
echo "HELIUS_API_KEY: $HELIUS_API_KEY"

# Creating a working directory
mkdir -p meteora-wallet-analysis
cd meteora-wallet-analysis

# Uploading files
wget -O meteora.py https://raw.githubusercontent.com/AlexToTheSun/meteora-wallet-metrics/refs/heads/main/meteora.py
wget -O kelsier_addresses.csv https://raw.githubusercontent.com/MeteoraAg/ops/refs/heads/main/kelsier_addresses.csv

# Installing dependencies
pip install -r requirements.txt

echo -e "\nSetup completed successfully!"
