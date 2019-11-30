# DEV doc: events

New blocks being inserted do trigger events.

Things depending on block should hook themselve on these events to be notified.

Two handlers are defined so far

## config.on_new_block (config.py)

This event is triggered on every block DB insert, even in the context of a batch update (bootstrap, retrace, catching up)  
It's to be used for internal state update, not to notify peers or external processes.

It currently updates the BU BlockchainUtils instance.

## Peers.on_block_insert (peers.py)

This event is triggered after a block insert (individual block context) and after a batch insert (batch context).  
It's the handler to use for outside notification.

This handler sends the new block info to the peers (clients and servers) we're connected to.  
It also updates the pool and notifies the miners. 


# Notes

- These handlers probably would benefit from a rename to have them more explicit

- More events may be defined later on to handle or act upon other events (plugin system) 