# Install MongoDB
sudo mkdir /data/db -p
sudo chmod 777 /data/db
sudo apt install -y gnupg
wget -qO - https://www.mongodb.org/static/pgp/server-4.4.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/4.4 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-4.4.list
sudo apt update
sudo apt install -y mongodb-org
# Setup and start DB service
sudo systemctl enable mongod.service
sudo systemctl start mongod.service

# sudo apt install -y libxml2-dev libxmlsec1-dev python-dev build-essential

# Get and clone repo
cd ~
git clone https://github.com/pdxwebdev/yadacoin.git
cd yadacoin
# Install prerequisites
sudo apt update
sudo apt install -y libssl-dev cmake python3-pip libjpeg-dev
python3 -m pip install wheel
python3 -m pip install scikit-build
python3 -m pip install cmake
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements-python3.txt

python3 utils/generate_config.py auto > config/config.json
python3 yadacoin/app.py --config=config/config.json
