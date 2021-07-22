#/bin/bash

# Install MongoDB
sudo mkdir /data/db -p
sudo chmod 777 /data/db
sudo apt-get install -y gnupg
wget -qO - https://www.mongodb.org/static/pgp/server-4.4.asc | sudo apt-key add -
if [[ $(lsb_release -rs) == "20.04" ]]; then
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/4.4 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-4.4.list
else
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu bionic/mongodb-org/4.4 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-4.4.list
fi
sudo apt-get update
sudo apt-get install -y mongodb-org libssl-dev cmake python3-pip libjpeg-dev build-essential

# Setup and start DB service
sudo systemctl enable mongod.service
sudo systemctl start mongod.service

# Get and clone repo
cd /etc
sudo git clone https://github.com/pdxwebdev/yadacoin.git
cd yadacoin

# create sysemd file yadanode.service
sudo bash -c "cat > /lib/systemd/system/yadanode.service" << EOL
[Unit]
Description=Yada_Node
[Service]
Type=simple
WorkingDirectory=/etc/yadacoin
ExecStart=python3 yadacoin/app.py --config=config/config.json
KillMode=process
[Install]
WantedBy=multi-user.target
EOL

# Install python prerequisites
sudo -H python3 -m pip install --upgrade pip
sudo -H python3 -m pip install -r requirements-python3.txt
# get the correct chardet and urllib3 versions for yada code
sudo python3 -m pip install --upgrade requests

# hugepages reservation
sudo bash -c "echo vm.nr_hugepages=1280 >> /etc/sysctl.conf"

# enable systemd startup
sudo systemctl enable yadanode.service

# start the yadanode.service
sudo systemctl start yadanode.service

# display message post installation
sudo bash -c "cat > /etc/yadacoin/WELCOME" << EOL
Congrats you have installed a full node on the YADACOIN network!
Thank you for the support! With each new node, the network become more redundant
and resilient.
Now that the node has been installed, it will take up to a couple of hours for the
node to sync. The node is building a database of every block up to the current block.
This takes time, we appreciate your patience!
You may check on the status of the node at anytime by using the command:
'sudo systemctl status yadanode.service'
The service will be shown as "Active" and you can see the progress of the blocks
in the lines that follow.
IE. "New block inserted for height: 7800" this is the height for the most recent block
that the node has synced.
By visiting https://yadacoin.io/explorer you can see the current block height.
Once the block height in the output of sudo systemctl status yadanode.service matches
the current block height in yadacoin.io/explorer, the node is completely in sync.
You are now part of something much bigger!
Next you will want to import your "wif" into the Yadacoin app - https://yadacoin.io/app
To do this, you will need to retreive your 'wif" from the node config file.
This file is located here - /etc/yadacoin/config/config.json
Use this command - "sudo cat /etc/yadacoin/config/config.json"
This will display the config.json file in the terminal and you will find your 'wif' (Wallet Import Format).
Search for the 'wif' property resembling the following:
        "wif": "xXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxX",
Copy this string of characters and at https://yadacoin.io/app enter the 'wif' into the "Import Identity" field
then click "IMPORT IDENTITY". Next you will be asked to Set a Username. This name is arbitrary and
can be anything that you want, it is not directly tied to the 'wif'. Keep a recored of this 'wif'
somewhere safe as this is the private key of the address where the rewards of your mining will be sent.
There is a web UI running on your node, you may visit this UI from a web browser.
The url will be http://x.x.x.x:8001 (where x.x.x.x is the IP addres of the node).
If you are opening a web browser directly on the node http://localhost:8001 will work.
This node may be accessed by other devices on your LAN using the format above.
You may begin Solo mining on this node as soon as it is fully synced!
On the webpage of your node, there will be a link provided to download XMRigCC.
Download and install XMRigCC on any computer on your LAN. Once installed you will modify the
config.json file (ON THE XMRigCC Computer NOT THE NODE!) and use the IP of your node in the "url" of the
config.json file.
            "algo": "rx/yada",
            "coin": null,
            "url": "insertNodeIPhere:3333",
Once you begin Solo mining every block won pays directly to you and the coins will go directly to the wallet
that was created with your 'wif' earlier in this document.
To read this file again, it can be found here - /etc/yadacoin/WELCOME
cat /etc/yadacoin/WELCOME will display the test easily
Join our discord for help, news, and further information!
https://discord.gg/JEDJaFS
EOL

# Display the WELCOME file in the terminal post installation
cat /etc/yadacoin/WELCOME | more