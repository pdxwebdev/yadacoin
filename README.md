# yadacoin
## Setup
  In your terminal

  `pip install -r requirements.txt`
  
  `python generate_config.py`
  
  copy that json object and paste it into a file named `config.json`
  
  create a peers.json file containing the following json object. If you would like to be added to the peers list, contact us at info@yadacoin.io

`[
	{
		"host": "yadacoin.io",
		"port": "8000"
	}
]`

IMPORTANT: You must run all three of the below processes for mining to work.

## Run the miner
`python p2p.py miner config.json peers.json`

## run the consensus script
`python p2p.py consensus config.json peers.json`

## run the server
`python p2p.py serve config.json peers.json`

The consensus and server must be running to run the miner.
