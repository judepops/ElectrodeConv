# demo

The judging deck. Open `demo/index.html` from disk. It reads `../dashboard/site/pipeline.js`, `harness.js` and the
images in `../dashboard/site/img/`, plus `results.js` in this folder.

Slides: title, the 13 lanes, preprocessing, V1 loss, V2 loss, how V1 and V2 are combined (late fusion, against one network trained with both losses), held-out accuracy, where the calls go (confusion matrices of V1 and V1 + V2) and the test spots, seed ensemble, feature
research, best hand-built features, features to battery outcomes (from `../dashboard/site/pca.js`).

Keys: right arrow or space for next, left arrow for back, `t` theme, `f` full screen. `#4.1` in the URL opens
slide 4, step 1.

To change what is shown, edit `config.js` (model rows, seed rows, test answers, text on the title slide).
After a new model is scored and committed, run `python3.11 demo/make_data.py` from the repo root to rewrite `results.js`.

The confusion matrices on the held-out accuracy slide come from `confusion.js`; rebuild it with
`LOSSLARP_MASKS=harmonise python3.11 demo/make_confusion.py demo/confusion.js` (repo root; needs the supcon fold embeddings).
