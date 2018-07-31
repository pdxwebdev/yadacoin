from rpc import app, config
app.run(host=config.get('host'), port=config.get('http_port'), threaded=True)