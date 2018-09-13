from rpc import app
from yadacoin import Config


print 'RUNNING SERVER WITH CONFIG:'
print Config.to_json()

app.run(host=Config.web_server_host, port=Config.web_server_port, threaded=True)