# yadacoin
## Setup
  Prerequisites:

  Requires MongoDB to be installed

  Ubuntu install instructions: https://docs.mongodb.com/manual/tutorial/install-mongodb-on-ubuntu/

  Debian/Ubuntu packages:
  - libxml2-dev
  - libxmlsec1-dev

  In your terminal

  `pip install -r requirements.txt`
  
  `python utils/generate_config.py`
  
  copy that json object and paste it into a file named `config.json`

  place that file in a directory called `config`

IMPORTANT: You must run all three of the below processes for mining to work.

## Run the miner
`./scripts/start_mine.sh`

## run the consensus script
`./scripts/start_consensus.sh`

## run the server
`./scripts/start_serve.sh`

The consensus and server must be running to run the miner.
