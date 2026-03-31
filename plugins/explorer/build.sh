NODE_OPTIONS=--openssl-legacy-provider ./node_modules/.bin/ng build --prod --base-href /yadacoinstatic/explorer/ --output-path ../../static/explorer
cp ../../static/explorer/index.html ../../templates/explorer/index.html
