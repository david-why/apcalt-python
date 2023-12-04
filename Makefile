all: apcalt_python/static/index.html client/dist/index.html

client/dist/index.html: client/index.html client/*.json client/*.ts $(shell find client/src)
	cd client && npm install
	cd client && npm run build

apcalt_python/static/index.html: client/dist/index.html
	rm -rf apcalt_python/static
	mkdir -p apcalt_python/static
	cp -r client/dist/* apcalt_python/static/
