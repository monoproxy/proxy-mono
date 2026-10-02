PYTHON ?= python3
SOURCES=$(wildcard sources/generator/*.py) $(wildcard sources/upstream/*.ttf)
FAMILY=Proxy Mono
# stem (units) -> style. One static font per weight; see sources/generator/az.py
WEIGHTS=46:Thin 68:ExtraLight 96:Light 110:Regular 126:Medium 144:SemiBold 162:Bold 180:ExtraBold 197:Black

help:
	@echo "###"
	@echo "# Build targets for $(FAMILY)"
	@echo "###"
	@echo
	@echo "  make build:  Builds the fonts and places them in the fonts/ directory"
	@echo "  make test:   Tests the fonts with fontspector"
	@echo "  make proof:  Creates HTML proof documents in the proof/ directory"
	@echo "  make images: Creates PNG specimen images in the documentation/ directory"
	@echo

build: build.stamp

venv: venv/touchfile

build.stamp: venv $(SOURCES)
	rm -rf fonts; mkdir -p fonts/ttf fonts/webfonts
	. venv/bin/activate; cd sources/generator && for w in $(WEIGHTS); do \
	  python3 az.py $${w%%:*} ../../fonts/ttf/ProxyMono-$${w##*:}.ttf plain || exit 1; \
	  mv ../../fonts/ttf/ProxyMono-$${w##*:}.woff2 ../../fonts/webfonts/; done
	# variable font: masters built with VF=1 (point-compatible), then merged
	mkdir -p fonts/variable build/masters
	. venv/bin/activate; cd sources/generator && for w in $(WEIGHTS); do \
	  VF=1 python3 az.py $${w%%:*} ../../build/masters/ProxyMono-$${w##*:}.ttf plain || exit 1; done && \
	  python3 vf.py ../../build/masters "../../fonts/variable/ProxyMono[wght].ttf" && \
	  mv "../../fonts/variable/ProxyMono[wght].woff2" ../../fonts/webfonts/
	# the same masters with a slant axis (0 to 10 degrees, an oblique). Kept out of fonts/variable: it is
	# not part of the Google Fonts submission, which is weight only
	mkdir -p fonts/slant
	. venv/bin/activate; cd sources/generator && \
	  SLANT=10 python3 vf.py ../../build/masters "../../fonts/slant/ProxyMono[slnt,wght].ttf" && \
	  mv "../../fonts/slant/ProxyMono[slnt,wght].woff2" ../../fonts/webfonts/
	touch build.stamp

venv/touchfile: requirements.txt
	test -d venv || $(PYTHON) -m venv venv
	. venv/bin/activate; pip install -Ur requirements.txt
	touch venv/touchfile

# Google Fonts layout (as in github.com/google/fonts/ofl/proxymono), so the metadata, article and
# licence checks run the way Google runs them
gfstage: build.stamp
	rm -rf out/gf; mkdir -p out/gf/proxymono/article
	cp fonts/variable/*.ttf OFL.txt documentation/METADATA.pb out/gf/proxymono/
	cp documentation/article/ARTICLE.en_us.html documentation/article/specimen.png out/gf/proxymono/article/

test: gfstage
	which fontspector || (echo "fontspector not found. Please install it with 'cargo binstall fontspector'." && exit 1)
	TOCHECK=$$(find out/gf/proxymono -name '*.ttf'); mkdir -p out/ out/fontspector; fontspector --profile googlefonts -l warn --full-lists --succinct --html out/fontspector/fontspector-report.html --ghmarkdown out/fontspector/fontspector-report.md --badges out/badges $$TOCHECK  || echo '::warning title=fontspector failures::The fontspector QA check reported errors in your font. Please check the generated report.'

proof: venv build.stamp
	which diff3proof || (echo "diff3proof not found. Please install it with 'cargo binstall diffenator3'." && exit 1)
	TOCHECK=$$(find fonts/variable -type f 2>/dev/null); if [ -z "$$TOCHECK" ]; then TOCHECK=$$(find fonts/ttf -type f 2>/dev/null); fi ; . venv/bin/activate; mkdir -p out/ out/proof; diff3proof $$TOCHECK --output out/proof

clean:
	rm -rf venv
	find . -name "*.pyc" -delete

update: venv
	venv/bin/pip install --upgrade pip-tools
	# See https://pip-tools.readthedocs.io/en/latest/#a-note-on-resolvers for
	# the `--resolver` flag below.
	venv/bin/pip-compile --upgrade --verbose --resolver=backtracking requirements.in
	venv/bin/pip-sync requirements.txt

	git commit -m "Update requirements" requirements.txt
	git push
