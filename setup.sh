# Install MongoDB
sudo mkdir /data/db -p
sudo chmod 777 /data/db
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 9DA31620334BD75D9DCB49F368818C72E52529D4
echo "deb [ arch=amd64 ] https://repo.mongodb.org/apt/ubuntu bionic/mongodb-org/4.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-4.0.list
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
sudo pip3 install -r requirements-python3.txt

python3 utils/generate_config.py auto > config/config.json
python3 utils/generate_services.py
sudo chmod +x scripts/start_node.sh
sudo cp services/* /lib/systemd/system/.
sudo systemctl daemon-reload
sudo systemctl enable yadacoin-node
sudo service yadacoin-node start
