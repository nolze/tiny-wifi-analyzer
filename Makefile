spec:
	poetry run pyi-makespec tiny_wifi_analyzer/__main__.py \
		--name 'Tiny Wi-Fi Analyzer' \
		--osx-bundle-identifier 'io.github.nolze.tiny-wifi-analyzer' \
		--target-architecture universal2 \
		--onefile \
		--noconsole \
		--add-data 'tiny_wifi_analyzer/view:view'

build:
	poetry run pyinstaller 'Tiny Wi-Fi Analyzer.spec' \
		--distpath build/dist \
		--noconfirm \
		--clean

.PHONY: build
